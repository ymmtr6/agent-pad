from pathlib import Path
from math import hypot
from shapely.geometry import Point, LineString, Polygon, box
from shapely.affinity import translate
from shapely.ops import unary_union
import zipfile, json, csv, math, os, shutil, subprocess, textwrap, tempfile, re

REV=int(os.environ.get('AGENTPAD_REV', '1'))
SINGLE_PCB = REV == 2 and os.environ.get('AGENTPAD_SINGLE_PCB', '0') == '1'
if REV not in (1,2,3):
    raise ValueError('AGENTPAD_REV must be 1, 2, or 3')
PANEL_PROFILE_MODE=os.environ.get('AGENTPAD_PANEL_PROFILE_MODE','closed_slots')
if PANEL_PROFILE_MODE not in ('closed_slots','continuous'):
    raise ValueError('AGENTPAD_PANEL_PROFILE_MODE must be closed_slots or continuous')
SLUG=f'agentpad_rev{REV}'
REV_DOTTED=f'Rev.{REV}'
REV_PLAIN=f'Rev{REV}'
MARKING=f'AGENTPAD REV{REV}'
OUT=Path(os.environ.get('AGENTPAD_OUT', f'/mnt/data/{SLUG}_complete')).resolve()
if SINGLE_PCB and OUT.exists() and any(OUT.iterdir()):
    raise ValueError('Rev2 single-PCB output must be an empty directory; existing files are preserved')
if OUT.exists() and not SINGLE_PCB: shutil.rmtree(OUT)
output_dirs = ['kicad', 'docs', 'scripts'] if SINGLE_PCB else ['kicad','gerber/individual_lower','gerber/individual_upper','gerber/panel','docs','firmware','scripts']
for d in output_dirs:
    (OUT/d).mkdir(parents=True, exist_ok=True)

# ---------- Locked geometry ----------
# Rev.3 applies the Rev.1 build feedback: six MX keys occupy two rows, while
# the MCU and encoder share the top row.  This removes 20 mm of unused height
# without changing the proven 19.05 mm key pitch or 62 mm width.
BW,BH=(68.0,80.0) if REV==1 else ((62.0,80.0) if REV==2 else (62.0,62.0))
PITCH=19.05
key_x=[14.50,33.55,52.60] if REV==1 else [11.95,31.00,50.05]
key_y=[34.00,53.05,72.10] if REV in (1,2) else [33.50,52.55]
centers=[(x,y) for y in key_y for x in key_x]
NUM_KEYS=8 if REV in (1,2) else 6
keys=centers[:NUM_KEYS]
enc_center=centers[8] if REV in (1,2) else (50.0,11.75)
DIRECT_SOLDER=REV>=2 and not SINGLE_PCB

# RP2040-Zero official envelope accepted by user
MCU_W,MCU_H=18.0,23.5
MCU_CX,MCU_CY=(33.55,11.75) if REV==1 else (31.00,11.75)
UPPER_NOTCH_X1=MCU_CX-MCU_W/2-1.0
UPPER_NOTCH_X2=MCU_CX+MCU_W/2+1.0
UPPER_NOTCH_Y=25.0
BOARD_CORNER_RADIUS=2.0 if REV>=2 else 0.0

def rounded_board_shape(width,height,radius):
    if radius<=0:
        return box(0,0,width,height)
    # Keep the nominal width/height while replacing only the four exterior
    # corners with tangent circular arcs.
    return box(radius,radius,width-radius,height-radius).buffer(
        radius,quad_segs=16,join_style=1)

LOWER_BOARD_SHAPE=rounded_board_shape(BW,BH,BOARD_CORNER_RADIUS)
# The RP2040 opening remains dimensionally square; only the four exterior board
# corners are rounded.
UPPER_BOARD_SHAPE=LOWER_BOARD_SHAPE.difference(
    box(UPPER_NOTCH_X1,-1.0,UPPER_NOTCH_X2,UPPER_NOTCH_Y))

def shape_rings(shape):
    polygons=[shape] if shape.geom_type=='Polygon' else list(shape.geoms)
    for poly in polygons:
        yield list(poly.exterior.coords)
        for ring in poly.interiors:
            yield list(ring.coords)
# Official Waveshare STEP: 9 header holes per side, 2.54 mm pitch, with the
# two rows 15.24 mm apart.  The STEP hole centres are y=1.69..22.01 mm.
side_y=[-10.06+i*2.54 for i in range(9)]
HEADER_ROW_HALF_SPACING=7.62
right_pins={i+1:(MCU_CX+HEADER_ROW_HALF_SPACING,MCU_CY+y) for i,y in enumerate(side_y)}
bottom_x=[5.08,2.54,0,-2.54,-5.08]
bottom_pads={10+i:(MCU_CX+x,MCU_CY+11.30) for i,x in enumerate(bottom_x)}
left_pins={15+i:(MCU_CX-HEADER_ROW_HALF_SPACING,MCU_CY+y) for i,y in enumerate(reversed(side_y))}
# RP2040-Zero-M has pre-soldered headers on the castellated side rows.  The
# five small pads along the bottom edge are not used as header connections.
MCU_PINS={**right_pins,**left_pins}

# pin mapping from Waveshare schematic used in previous locked package
pin_signal={
1:'K1',2:'K2',3:'K3',4:'K4',5:'K5',6:'K6',7:'K7',8:'K8',9:'ENC_A',
15:'ENC_B',16:'ENC_SW',17:'RGB',18:'GPIO27',19:'GPIO28',20:'GPIO29',21:'3V3',22:'GND',23:'VSYS'}

# Kailh MX hotswap plated anti-shear-like geometry; switch local coords
# Based on established Kailh MX socket footprints: switch pin holes (-3.81,-2.54),(2.54,-5.08), center 3.9878.
# Bottom SMD contacts pad1 (-7.56,-2.54), pad2 (6.29,-5.08).
SW_PAD1=(-7.56,-2.54); SW_PAD2=(6.29,-5.08)
SW_HOLE1=(-3.81,-2.54); SW_HOLE2=(2.54,-5.08)
SW_CENTER=(0,0)
SW_STABS=[(-5.08,0),(5.08,0)]
SWITCH_PTH_DRILL=1.50
SWITCH_PTH_SIZE=2.20
# Rev.1 routed the two electrical-pin openings as non-plated mechanical holes.
# Rev.2 uses KiCad's standard Cherry MX PCB-mount dimensions for those pins;
# only the centre post and optional locating posts remain mechanical cutouts.
SW_ROUTED_HOLES=[(SW_CENTER,3.9878)]+[(p,1.75) for p in SW_STABS]
if REV==1 or SINGLE_PCB:
    SW_ROUTED_HOLES += [(SW_HOLE1,3.0),(SW_HOLE2,3.0)]
# small plated anchors/vias at socket pad edges, one per net for robust routing
# Keep the plated routing anchors outside the SMD solder-mask openings.  This
# avoids via-in-pad solder wicking and lets fabrication DFM analyze each opening
# as a single shape.
SW_VIA1=(-9.80,-2.54); SW_VIA2=(8.55,-5.08)

# EC11 footprint official KiCad geometry; footprint origin chosen so shaft center matches enc_center.
ENC_ORG=(enc_center[0]-7.5, enc_center[1]-2.5)
enc_pads={
'A':(ENC_ORG[0]+0,ENC_ORG[1]+0),
'C':(ENC_ORG[0]+0,ENC_ORG[1]+2.5),
'B':(ENC_ORG[0]+0,ENC_ORG[1]+5.0),
'S2':(ENC_ORG[0]+14.5,ENC_ORG[1]+0),
'S1':(ENC_ORG[0]+14.5,ENC_ORG[1]+5.0),
'MP1':(ENC_ORG[0]+7.5,ENC_ORG[1]-3.1),
'MP2':(ENC_ORG[0]+7.5,ENC_ORG[1]+8.1),
}

# Rookey-like vertical FR4 spacer slots: 4 slots per assembled board, and 4 breakout spacers in panel.
if REV==1:
    slot_centers=[(3.5,4.0),(BW-3.5,4.0),(3.5,BH-4.0),(BW-3.5,BH-4.0)]
    SLOT_W,SLOT_H=3.3,1.9
else:
    slot_centers=[(2.5,4.0),(BW-2.5,4.0),(2.5,BH-4.0),(BW-2.5,BH-4.0)]
    SLOT_W,SLOT_H=1.9,3.3
if SINGLE_PCB:
    slot_centers = []
MOUNT_DRILL = 2.2
MOUNT_HEAD_DIAMETER = 4.0
MOUNT_COPPER_RADIUS = 2.5  # Ø4 mm head/boss plus 0.5 mm copper clearance.
mount_centers = [(2.5, 2.5), (BW-2.5, 2.5),
                 (2.5, BH-2.5), (BW-2.5, BH-2.5)] if SINGLE_PCB else []

# ---------- Nets ----------
nets=['GND']+[f'K{i}' for i in range(1,NUM_KEYS+1)]+['ENC_A','ENC_B','ENC_SW','RGB']
net_id={n:i+1 for i,n in enumerate(nets)}

# ---------- Routing ----------
# Switch pad/anchor global positions
sw={}
for i,(cx,cy) in enumerate(keys,1):
    def g(p): return (cx+p[0],cy+p[1])
    sw[i]={'p1':g(SW_PAD1),'p2':g(SW_PAD2),'h1':g(SW_HOLE1),'h2':g(SW_HOLE2),
           'v1':g(SW_VIA1),'v2':g(SW_VIA2)}

# Two-layer maze router. Signals may change layer through 0.6 mm vias.
# This avoids artificial single-layer crossings while keeping a standard 2-layer JLCPCB process.
from heapq import heappush, heappop
GRID=0.50
TRACE_W=0.30
GROUND_W=0.25
CLEAR=0.50
EDGE_CLEAR=0.52
SLOT_CLEAR=0.70
VIA_DRILL=0.60
VIA_SIZE=1.40
sig_vias={}  # compatibility with file emitters; actual vias are generated by the router
route_vias=[]  # (x,y,net)
routes=[]      # (layer, net, width, [points])

signal_ep={**{f'K{i}':(MCU_PINS[i],sw[i]['p1']) for i in range(1,NUM_KEYS+1)},
           'ENC_A':(MCU_PINS[9],enc_pads['A']),
           'ENC_B':(MCU_PINS[15],enc_pads['B']),
           'ENC_SW':(MCU_PINS[16],enc_pads['S1'])}
# Route difficult / distant nets first.
signal_order=[net for net in
              ['K7','K4','K1','K8','K5','K2','ENC_SW','ENC_B','ENC_A','K6','K3']
              if net in signal_ep]

# Shapes for fixed mechanical obstacles on both layers.
mech=[]
for x,y in mount_centers:
    mech.append(Point(x,y).buffer(MOUNT_COPPER_RADIUS+TRACE_W/2))
for i,(cx,cy) in enumerate(keys,1):
    for p,d in SW_ROUTED_HOLES:
        mech.append(Point(cx+p[0],cy+p[1]).buffer(d/2+EDGE_CLEAR+TRACE_W/2))
for sc in slot_centers:
    mech.append(box(sc[0]-SLOT_W/2-SLOT_CLEAR,sc[1]-SLOT_H/2-SLOT_CLEAR,sc[0]+SLOT_W/2+SLOT_CLEAR,sc[1]+SLOT_H/2+SLOT_CLEAR))
mech_union=unary_union(mech)

# Build all electrical pad shapes with ownership net and layers.
pad_shapes=[]  # (shape, net, layers)
# RP2040-Zero-M header pads are plated through-holes and connect both layers.
for n,p0 in MCU_PINS.items():
    sig=pin_signal.get(n,'')
    owner=sig if sig in net_id else None
    pad_shapes.append((Point(*p0).buffer(0.90+CLEAR+TRACE_W/2),owner,{'F.Cu','B.Cu'}))
# switch socket pads
for i in range(1,NUM_KEYS+1):
    kn=f'K{i}'
    x,y=sw[i]['p1']; pad_shapes.append((box(x-1.275-CLEAR-TRACE_W/2,y-1.25-CLEAR-TRACE_W/2,x+1.275+CLEAR+TRACE_W/2,y+1.25+CLEAR+TRACE_W/2),kn,{'B.Cu'}))
    x,y=sw[i]['p2']; pad_shapes.append((box(x-1.275-CLEAR-TRACE_W/2,y-1.25-CLEAR-TRACE_W/2,x+1.275+CLEAR+TRACE_W/2,y+1.25+CLEAR+TRACE_W/2),'GND',{'B.Cu'}))
    if DIRECT_SOLDER:
        pad_shapes.append((Point(*sw[i]['h1']).buffer(SWITCH_PTH_SIZE/2+CLEAR+TRACE_W/2),kn,{'F.Cu','B.Cu'}))
        pad_shapes.append((Point(*sw[i]['h2']).buffer(SWITCH_PTH_SIZE/2+CLEAR+TRACE_W/2),'GND',{'F.Cu','B.Cu'}))
# encoder pads both layers
for nm,owner in [('A','ENC_A'),('B','ENC_B'),('C','GND'),('S1','ENC_SW'),('S2','GND')]:
    pad_shapes.append((Point(*enc_pads[nm]).buffer(1.0+CLEAR+TRACE_W/2),owner,{'F.Cu','B.Cu'}))
for nm in ['MP1','MP2']:
    pad_shapes.append((Point(*enc_pads[nm]).buffer(1.7+CLEAR+TRACE_W/2),None,{'F.Cu','B.Cu'}))

# A generated routing via must not sit in any fixed pad, including a pad on the
# same net.  Fixed PTH pads already connect both copper layers; SMD via-in-pad
# would create overlapping mask openings and can wick solder from the joint.
fixed_via_obs={}
for layer in ['F.Cu','B.Cu']:
    fixed_via_obs[layer]=unary_union([
        shape for shape,owner,layers in pad_shapes if layer in layers
    ]).buffer((VIA_SIZE-TRACE_W)/2)

existing={'F.Cu':[],'B.Cu':[]}
existing_vias=[]

def snap(p): return (round(p[0]/GRID)*GRID,round(p[1]/GRID)*GRID)

def route_one(net,start,target,existing_local,existing_vias_local,start_layers=('F.Cu','B.Cu'),target_layers=('F.Cu','B.Cu')):
    sxy=snap(start); txy=snap(target)
    # Header and target pads are plated, so the router may start/end on either layer.
    starts=[(sxy[0],sxy[1],layer) for layer in start_layers]
    targets={(txy[0],txy[1],layer) for layer in target_layers}
    obs={}
    for layer in ['F.Cu','B.Cu']:
        shapes=[mech_union]
        for sh,owner,layers in pad_shapes:
            if layer in layers and owner!=net: shapes.append(sh)
        # Existing different-net copper and vias are blocked.
        for ls,nm,w in existing_local[layer]:
            if nm!=net: shapes.append(ls.buffer(w/2+CLEAR+TRACE_W/2,cap_style=2,join_style=2))
        for vx,vy,vn in existing_vias_local:
            if vn!=net: shapes.append(Point(vx,vy).buffer(VIA_SIZE/2+CLEAR+TRACE_W/2))
        obs[layer]=unary_union(shapes)
    via_obs={layer: obs[layer].buffer((VIA_SIZE-TRACE_W)/2) for layer in ['F.Cu','B.Cu']}
    def blocked(state):
        x,y,layer=state
        if x<1.0 or x>BW-1.0 or y<1.0 or y>BH-1.0: return True
        return obs[layer].contains(Point(x,y))
    pq=[]; best={}; parent={}; pdir={}; counter=0
    for st in starts:
        best[st]=0; heappush(pq,(0,counter,st,None))
    endstate=None
    while pq:
        f,_,cur,prevdir=heappop(pq)
        if cur in targets:
            endstate=cur; break
        g=best[cur]; x,y,layer=cur
        moves=[(x+GRID,y,layer),(x-GRID,y,layer),(x,y+GRID,layer),(x,y-GRID,layer),(x,y,'B.Cu' if layer=='F.Cu' else 'F.Cu')]
        for nb in moves:
            via=(nb[2]!=layer)
            if via:
                vp=Point(x,y)
                if (via_obs['F.Cu'].intersects(vp) or via_obs['B.Cu'].intersects(vp)
                        or fixed_via_obs['F.Cu'].intersects(vp) or fixed_via_obs['B.Cu'].intersects(vp)
                        or any(vn==net and vp.distance(Point(vx,vy)) < VIA_SIZE+0.20
                               for vx,vy,vn in existing_vias_local)):
                    continue
            else:
                if blocked(nb) or obs[layer].intersects(LineString([(x,y),(nb[0],nb[1])])): continue
            ndir=('via' if via else (nb[0]-x,nb[1]-y,layer))
            step=(7.0 if via else 1.0)
            if not via and prevdir not in (None,'via') and ndir!=prevdir: step+=0.12
            ng=g+step
            if ng<best.get(nb,1e18):
                best[nb]=ng; parent[nb]=cur; pdir[nb]=ndir
                h=(abs(nb[0]-txy[0])+abs(nb[1]-txy[1]))/GRID + (0 if nb[2]=='F.Cu' else 0.2)
                counter+=1; heappush(pq,(ng+h,counter,nb,ndir))
    if endstate is None: return None
    states=[endstate]; cur=endstate
    while cur in parent:
        cur=parent[cur]; states.append(cur)
    states.reverse()
    # Preserve exact endpoints.
    states[0]=(start[0],start[1],states[0][2]); states[-1]=(target[0],target[1],states[-1][2])
    return states

def states_to_geometry(net,states,width=TRACE_W):
    segs=[]; vias=[]
    cur_layer=states[0][2]; pts=[(states[0][0],states[0][1])]
    for a,b in zip(states,states[1:]):
        if a[2]!=b[2]:
            # close current segment at via coordinate and open on new layer
            vp=(a[0],a[1]);
            if len(pts)>1: segs.append((cur_layer,net,width,pts))
            vias.append((vp[0],vp[1],net)); cur_layer=b[2]; pts=[vp]
        else:
            pts.append((b[0],b[1]))
    if len(pts)>1: segs.append((cur_layer,net,width,pts))
    # compress each segment collinear
    out=[]
    for layer,nm,w,pp in segs:
        comp=[pp[0]]
        for q in pp[1:]:
            if len(comp)>=2:
                a,b=comp[-2],comp[-1]
                v1=(round(b[0]-a[0],6),round(b[1]-a[1],6)); v2=(round(q[0]-b[0],6),round(q[1]-b[1],6))
                if v1==v2: comp[-1]=q; continue
            comp.append(q)
        out.append((layer,nm,w,comp))
    return out,vias

for net in signal_order:
    st,tg=signal_ep[net]
    target_layers=('B.Cu',) if net.startswith('K') else ('F.Cu','B.Cu')
    states=route_one(net,st,tg,existing,existing_vias,target_layers=target_layers)
    if states is None: raise RuntimeError(f'two-layer router failed for {net}')
    segs,vias=states_to_geometry(net,states)
    routes.extend(segs); route_vias.extend(vias)
    for layer,nm,w,pp in segs: existing[layer].append((LineString(pp),nm,w))
    existing_vias.extend(vias)
# Ground endpoints route after signals as a single daisy-chain tree.  This avoids
# overlapping/parallel same-net branches that simple Gerber DFM tools can report
# as self-spacing errors.
ground_eps=[sw[i]['p2'] for i in range(1,NUM_KEYS+1)]+[enc_pads['C'],enc_pads['S2']]
ground_root=MCU_PINS[22]
ground_start=ground_root; ground_start_layers=('F.Cu',)
for ep in ground_eps:
    target_layers=('F.Cu','B.Cu') if ep in (enc_pads['C'],enc_pads['S2']) else ('B.Cu',)
    states=route_one('GND',ground_start,ep,existing,existing_vias,
                     start_layers=ground_start_layers,target_layers=target_layers)
    if states is None: raise RuntimeError(f'two-layer router failed for GND endpoint {ep}')
    segs,vias=states_to_geometry('GND',states,GROUND_W)
    routes.extend(segs); route_vias.extend(vias)
    for layer,nm,w,pp in segs: existing[layer].append((LineString(pp),nm,w))
    existing_vias.extend(vias)
    ground_start=ep; ground_start_layers=(states[-1][2],)
# deduplicate vias by rounded position/net
rv=[]; seen=set()
for x,y,nm in route_vias:
    k=(round(x,3),round(y,3),nm)
    if k not in seen: seen.add(k); rv.append((x,y,nm))
route_vias=rv
# Keep the K3 vertical approach away from the side of its rectangular socket
# mask opening.  Enter the pad horizontally on the final segment so JLCDFM does
# not see an unrelated exposed trace running alongside the opening.
adjusted=[]
for layer,net,width,pts in routes:
    if REV==2 and not SINGLE_PCB and layer=='B.Cu' and net=='K3':
        pts=[(45.0,y) if abs(x-46.5)<1e-9 and 29.0<=y<=31.5 else (x,y)
             for x,y in pts]
    if SINGLE_PCB and layer=='B.Cu' and net=='K3' and (44.0,29.0) in pts:
        # x=44 はパッド右辺とソケット穴の隙間なので、パッド上側から垂直に入る
        pad=pts[-1]
        pts=pts[:pts.index((44.0,29.0))+1]+[(pad[0],29.0),pad]
    adjusted.append((layer,net,width,pts))
routes=adjusted
# Neck down the K1 bottom-layer approach beside its socket mask opening.  The
# 0.20 mm segment remains comfortably above JLCPCB capability while providing
# >=0.15 mm mask-opening-to-trace clearance in their conservative DFM model.
routes=[(layer,net,0.20 if REV==2 and layer=='B.Cu' and net=='K1' else width,pts)
        for layer,net,width,pts in routes]
# Rev.2 supports both direct-solder MX switches and the existing Kailh hot-swap
# sockets. Short bottom-copper links join each new plated switch-pin pad to its
# corresponding socket pad.
if DIRECT_SOLDER:
    for i in range(1,NUM_KEYS+1):
        routes.append(('B.Cu',f'K{i}',0.60,[sw[i]['p1'],sw[i]['h1']]))
        routes.append(('B.Cu','GND',0.60,[sw[i]['p2'],sw[i]['h2']]))
GND_VIA=(26.0,6.0)  # legacy placeholder; not used by routing
# ---------- KiCad helpers ----------
def kicad_header(title):
    return f'''(kicad_pcb (version 20240108) (generator pcbnew)\n  (general (thickness 1.6))\n  (paper "A4")\n  (title_block (title "{title}") (rev "1.0"))\n  (layers\n    (0 "F.Cu" signal)\n    (31 "B.Cu" signal)\n    (32 "B.Adhes" user "b.adhesive")\n    (33 "F.Adhes" user "f.adhesive")\n    (34 "B.Paste" user)\n    (35 "F.Paste" user)\n    (36 "B.SilkS" user "b.silkscreen")\n    (37 "F.SilkS" user "f.silkscreen")\n    (38 "B.Mask" user)\n    (39 "F.Mask" user)\n    (40 "Dwgs.User" user "user.drawings")\n    (41 "Cmts.User" user "user.comments")\n    (42 "Eco1.User" user "user.eco1")\n    (43 "Eco2.User" user "user.eco2")\n    (44 "Edge.Cuts" user)\n    (45 "Margin" user)\n    (46 "B.CrtYd" user "b.courtyard")\n    (47 "F.CrtYd" user "f.courtyard")\n    (48 "B.Fab" user)\n    (49 "F.Fab" user)\n  )\n  (setup (pad_to_mask_clearance 0))\n'''

def net_defs():
    s='  (net 0 "")\n'
    for n in nets: s+=f'  (net {net_id[n]} "{n}")\n'
    return s

def fp_text(kind,text,x,y,layer='F.SilkS',hide=False):
    h=' hide' if hide else ''
    return f'    (fp_text {kind} "{text}" (at {x:.3f} {y:.3f}) (layer "{layer}"){h} (effects (font (size 1 1) (thickness 0.15))))\n'

def pad_smd(num,x,y,sx,sy,layers,net=None,shape='roundrect'):
    rr=' (roundrect_rratio 0.20)' if shape=='roundrect' else ''
    ns=f' (net {net_id[net]} "{net}")' if net else ''
    return f'    (pad "{num}" smd {shape} (at {x:.3f} {y:.3f}) (size {sx:.3f} {sy:.3f}) (layers {layers}){rr}{ns} (solder_mask_margin 0.01))\n'

def pad_th(num,x,y,size,drill,net=None,shape='circle',plated=True,oval=None):
    typ='thru_hole' if plated else 'np_thru_hole'
    ns=f' (net {net_id[net]} "{net}")' if net else ''
    if oval:
        d=f'(drill oval {oval[0]} {oval[1]})'
    else: d=f'(drill {drill})'
    # NPTH は穴径と同値にし、丸めで銅パッドが残らないようにする
    sz=f'{size:.3f}' if plated else f'{drill}'
    return f'    (pad "{num}" {typ} {shape} (at {x:.3f} {y:.3f}) (size {sz} {sz}) {d} (layers "*.Cu" "*.Mask"){ns} (solder_mask_margin 0.05))\n'

def u1_footprint():
    s='  (footprint "RP2040-Zero-M_Header_Top" (layer "F.Cu") (at 0 0)\n'
    s+=fp_text('reference','U1',MCU_CX,MCU_CY,'F.Fab',True)
    s+=fp_text('value','RP2040-Zero-M (visible top)',MCU_CX,MCU_CY+13,'F.Fab',True)
    s+=f'    (fp_rect (start {MCU_CX-9:.3f} {MCU_CY-11.75:.3f}) (end {MCU_CX+9:.3f} {MCU_CY+11.75:.3f}) (stroke (width 0.20) (type default)) (fill none) (layer "F.Fab"))\n'
    s+=f'    (fp_rect (start {MCU_CX-4.5:.3f} {-2.0:.3f}) (end {MCU_CX+4.5:.3f} {4.0:.3f}) (stroke (width 0.15) (type default)) (fill none) (layer "F.Fab"))\n'
    for n,(x,y) in MCU_PINS.items():
        net=None
        sig=pin_signal.get(n,'')
        if sig in net_id: net=sig
        s+=pad_th(str(n),x,y,1.8,1.0,net)
    s+= '  )\n'
    return s

def switch_fp(i,cx,cy):
    s=f'  (footprint "Kailh_MX_Hotswap_1U" (layer "F.Cu") (at 0 0)\n'
    s+=fp_text('reference',f'SW{i}',cx,cy-8.2,'F.Fab',True)
    s+=fp_text('value','Kailh MX Hotswap',cx,cy+8.2,'F.Fab',True)
    # 14x14 switch outline on fabrication layer
    s+=f'    (fp_rect (start {cx-7:.3f} {cy-7:.3f}) (end {cx+7:.3f} {cy+7:.3f}) (stroke (width 0.15) (type default)) (fill none) (layer "F.Fab"))\n'
    # SMD socket pads bottom
    p1=sw[i]['p1']; p2=sw[i]['p2']
    s+=pad_smd('1',*p1,2.55,2.50,'"B.Cu" "B.Paste" "B.Mask"',f'K{i}',shape='rect')
    s+=pad_smd('2',*p2,2.55,2.50,'"B.Cu" "B.Paste" "B.Mask"','GND',shape='rect')
    if DIRECT_SOLDER:
        # Direct-solder pins: 1.5 mm finished holes with 2.2 mm annular pads,
        # matching KiCad's standard SW_Cherry_MX_1.00u_PCB footprint.
        s+=pad_th('1',*sw[i]['h1'],SWITCH_PTH_SIZE,SWITCH_PTH_DRILL,f'K{i}')
        s+=pad_th('2',*sw[i]['h2'],SWITCH_PTH_SIZE,SWITCH_PTH_DRILL,'GND')
    if SINGLE_PCB:
        for p,d in SW_ROUTED_HOLES:
            s+=pad_th('',cx+p[0],cy+p[1],d,d,plated=False)
        # Socket body reference, viewed through the PCB from the front.
        s+=f'    (fp_rect (start {cx-6.35:.3f} {cy-6.985:.3f}) (end {cx+5.08:.3f} {cy-0.635:.3f}) (stroke (width 0.12) (type default)) (fill none) (layer "B.Fab"))\n'
    # Mechanical switch holes are emitted as routed Edge.Cuts in the board,
    # not as a second drill file.  This prevents fabrication tools from
    # misclassifying NPTH holes as zero-annular-ring plated holes.
    s+='  )\n'
    return s

def encoder_fp():
    s='  (footprint "RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm" (layer "F.Cu") (at 0 0)\n'
    s+=fp_text('reference','ENC1',enc_center[0],enc_center[1]-8,'F.Fab',True)
    s+=fp_text('value','EC11E push encoder',enc_center[0],enc_center[1]+8,'F.Fab',True)
    # body and shaft
    s+=f'    (fp_circle (center {enc_center[0]:.3f} {enc_center[1]:.3f}) (end {enc_center[0]+3:.3f} {enc_center[1]:.3f}) (stroke (width 0.15) (type default)) (fill none) (layer "F.SilkS"))\n'
    for name,net in [('A','ENC_A'),('B','ENC_B'),('C','GND'),('S1','ENC_SW'),('S2','GND')]:
        x,y=enc_pads[name]
        s+=pad_th(name,x,y,2.0,1.0,net,'circle',True)
    # mounting slots (plated mechanical pads)
    for name in ['MP1','MP2']:
        x,y=enc_pads[name]
        # circle simplification for broad EC11 compatibility; 2.8mm drill
        s+=pad_th('MP',x,y,3.4,2.8,None,'circle',True)
    s+='  )\n'
    return s

def add_mount_slots():
    s=''
    for idx,(cx,cy) in enumerate(slot_centers,1):
        # Represent slot as routed Edge.Cuts rounded rectangle simplified as rect here.
        x1,x2=cx-SLOT_W/2,cx+SLOT_W/2; y1,y2=cy-SLOT_H/2,cy+SLOT_H/2
        s+=f'  (gr_rect (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) (stroke (width 0.10) (type default)) (fill none) (layer "Edge.Cuts"))\n'
    return s

SILK_TEXT_SIZE=1.0
SILK_TEXT_THICKNESS=0.15

def silk_text(text,x,y,layer,size=SILK_TEXT_SIZE,thickness=SILK_TEXT_THICKNESS):
    # Bottom-side text is mirrored in board coordinates so it reads normally
    # when the manufactured PCB is viewed from the bottom.
    justify=' (justify mirror)' if layer=='B.SilkS' else ''
    return (f'  (gr_text "{text}" (at {x:.3f} {y:.3f}) (layer "{layer}") '
            f'(effects (font (size {size:.3f} {size:.3f}) (thickness {thickness:.3f})){justify}))\n')

def lower_silkscreen_text(layer,dx=0.0,dy=0.0):
    s=''
    if SINGLE_PCB:
        note = 'SWITCH TOP' if layer == 'F.SilkS' else 'SOCKET BOTTOM'
        s+=silk_text('REV2 '+note,10+dx,14+dy,layer,0.8,0.13)
    u1_y=2.5 if REV==3 else 23.8
    s+=silk_text('U1',MCU_CX+dx,u1_y+dy,layer,1.0,0.15)
    # RP2040 header labels. Short aliases keep 0.15 mm clearance from pads.
    right_names=['K1','K2','K3','K4','K5','K6','K7','K8','E-A']
    left_names={15:'E-B',16:'E-SW',17:'RGB',18:'GP27',19:'GP28',20:'GP29',21:'3V3',22:'GND',23:'VSYS'}
    right_label_x=MCU_CX+5.0 if REV==3 else MCU_CX+12.8
    # 単一基板では GND ラベルが (21, 4) の GND ビアに重なるため左へ寄せる
    left_label_x=MCU_CX-12.0 if SINGLE_PCB else MCU_CX-10.8
    for n,name in zip(range(1,10),right_names):
        _,y=MCU_PINS[n]; s+=silk_text(name,right_label_x+dx,y+dy,layer)
    for n in range(15,24):
        _,y=MCU_PINS[n]; s+=silk_text(left_names[n],left_label_x+dx,y+dy,layer)
    # Each switch label states both electrical destinations. Put the front
    # legend above the switch and the back legend below its socket footprint.
    for i,(cx,cy) in enumerate(keys,1):
        ly=cy-8.2 if layer=='F.SilkS' or REV==3 else cy+5.8
        s+=silk_text(f'SW{i} K{i}/GND',cx+dx,ly+dy,layer)
    s+=silk_text('ENC1',enc_center[0]+dx,enc_center[1]-9.0+dy,layer)
    for label,p,xoff in [('A',enc_pads['A'],-2.1),('C',enc_pads['C'],-2.1),('B',enc_pads['B'],-2.1),
                         ('G',enc_pads['S2'],-2.2),('S',enc_pads['S1'],-2.2)]:
        s+=silk_text(label,p[0]+xoff+dx,p[1]+dy,layer)
    if REV==3:
        side_notes=('KAILH SOCKET','BOTTOM SIDE') if layer=='B.SilkS' else ('MX DIRECT','TOP SIDE')
        s+=silk_text(side_notes[0],50.0+dx,22.2+dy,layer,0.80,0.13)
        s+=silk_text(side_notes[1],50.0+dx,23.5+dy,layer,0.80,0.13)
    return s

def upper_silkscreen_text(layer,dx=0.0,dy=0.0):
    s=''
    mark_x,mark_size=(12.0,1.6) if REV==1 else (10.5,1.4)
    s+=silk_text(MARKING,mark_x+dx,16+dy,layer,mark_size,0.20)
    label_y=[25.9,44.0,63.0]
    if REV!=3:
        for i,(cx,cy) in enumerate(keys,1):
            row=(i-1)//3
            s+=silk_text(f'SW{i}',cx+dx,label_y[row]+dy,layer)
    enc_label_y=label_y[2] if REV in (1,2) else enc_center[1]+9.0
    s+=silk_text('ENC1',enc_center[0]+dx,enc_label_y+dy,layer)
    return s

def lower_board_text():
    s=kicad_header(f'AgentPad {REV_DOTTED} Lower Circuit PCB')+net_defs()+u1_footprint()
    for i,(cx,cy) in enumerate(keys,1): s+=switch_fp(i,cx,cy)
    s+=encoder_fp()
    for i,(x,y) in enumerate(mount_centers,1):
        s+=f'  (footprint "MountingHole_2.2mm_M2" (layer "F.Cu") (at 0 0) (attr exclude_from_pos_files exclude_from_bom)\n'
        s+=fp_text('reference',f'H{i}',x,y,'F.Fab',True)
        s+=fp_text('value','M2 NPTH / head max 4mm',x,y,'F.Fab',True)
        s+=pad_th('',x,y,MOUNT_DRILL,MOUNT_DRILL,plated=False)
        for layer in ['F.Fab','B.Fab']:
            s+=f'    (fp_circle (center {x} {y}) (end {x+MOUNT_HEAD_DIAMETER/2} {y}) (stroke (width 0.1) (type default)) (fill none) (layer "{layer}"))\n'
        # KiCad includes NPTH in its pad prohibition, so permit pads here.
        # The exporter separately checks all actual copper pads against heads.
        points=' '.join(f'(xy {x+MOUNT_COPPER_RADIUS*math.cos(a*math.pi/32):.4f} {y+MOUNT_COPPER_RADIUS*math.sin(a*math.pi/32):.4f})' for a in range(64))
        s+=f'  (zone (net 0) (net_name "") (layers "F.Cu" "B.Cu") (hatch edge 0.5) (connect_pads (clearance 0)) (min_thickness 0.25) (keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) (fill (thermal_gap 0.3) (thermal_bridge_width 0.3)) (polygon (pts {points})))\n'
        s+='  )\n'
    # True routing vias (not component through-hole pads) preserve correct
    # ViaPad/ViaDrill classification in Gerber X2 and Excellon metadata.
    for x,y,net in route_vias:
        s+=f'  (via (at {x:.3f} {y:.3f}) (size {VIA_SIZE:.3f}) (drill {VIA_DRILL:.3f}) (layers "F.Cu" "B.Cu") (net {net_id[net]}))\n'
    # Board outline
    for ring in shape_rings(LOWER_BOARD_SHAPE):
        for a,b in zip(ring,ring[1:]):
            s+=f'  (gr_line (start {a[0]:.4f} {a[1]:.4f}) (end {b[0]:.4f} {b[1]:.4f}) (stroke (width 0.10) (type default)) (layer "Edge.Cuts"))\n'
    s+=add_mount_slots()
    for cx,cy in ([] if SINGLE_PCB else keys):
        for p,d in SW_ROUTED_HOLES:
            x,y=cx+p[0],cy+p[1]
            s+=f'  (gr_circle (center {x:.3f} {y:.3f}) (end {x+d/2:.3f} {y:.3f}) (stroke (width 0.10) (type default)) (fill none) (layer "Edge.Cuts"))\n'
    # labels
    # tracks
    for layer,net,w,pts in routes:
        for a,b in zip(pts,pts[1:]):
            if a==b: continue
            s+=f'  (segment (start {a[0]:.3f} {a[1]:.3f}) (end {b[0]:.3f} {b[1]:.3f}) (width {w:.3f}) (layer "{layer}") (net {net_id[net]}))\n'
    for layer in ['F.SilkS','B.SilkS']:
        s+=lower_silkscreen_text(layer)
    s+=')\n'
    return s

def upper_board_text():
    s=kicad_header(f'AgentPad {REV_DOTTED} Upper Switch Plate')
    # Open top-edge notch exposes the top-mounted RP2040-Zero-M and USB-C.
    for ring in shape_rings(UPPER_BOARD_SHAPE):
        for a,b in zip(ring,ring[1:]):
            s+=f'  (gr_line (start {a[0]:.4f} {a[1]:.4f}) (end {b[0]:.4f} {b[1]:.4f}) (stroke (width 0.10) (type default)) (layer "Edge.Cuts"))\n'
    s+=add_mount_slots()
    # Square MX openings
    for i,(cx,cy) in enumerate(keys,1):
        s+=f'  (gr_rect (start {cx-7:.3f} {cy-7:.3f}) (end {cx+7:.3f} {cy+7:.3f}) (stroke (width 0.10) (type default)) (fill none) (layer "Edge.Cuts"))\n'
    if REV==1:
        # Rev.1 used shaft-only clearance.
        s+=f'  (gr_circle (center {enc_center[0]:.3f} {enc_center[1]:.3f}) (end {enc_center[0]+3.75:.3f} {enc_center[1]:.3f}) (stroke (width 0.10) (type default)) (fill none) (layer "Edge.Cuts"))\n'
    else:
        # Rookey-style opening lets the complete EC11 body pass through the plate.
        s+=f'  (gr_rect (start {enc_center[0]-7:.3f} {enc_center[1]-7:.3f}) (end {enc_center[0]+7:.3f} {enc_center[1]+7:.3f}) (stroke (width 0.10) (type default)) (fill none) (layer "Edge.Cuts"))\n'
    for layer in ['F.SilkS','B.SilkS']:
        s+=upper_silkscreen_text(layer)
    s+=')\n'
    return s

def panel_silkscreen_board_text():
    s=kicad_header(f'AgentPad {REV_DOTTED} Panel Silkscreen')
    s+=f'  (gr_rect (start 0 0) (end {PW} {PH}) (stroke (width 0.10) (type default)) (fill none) (layer "Edge.Cuts"))\n'
    for layer in ['F.SilkS','B.SilkS']:
        s+=lower_silkscreen_text(layer,*LO)
        s+=upper_silkscreen_text(layer,*UO)
    return s+')\n'

if SINGLE_PCB:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from export_agentpad_rev2 import export_single_pcb
    export_single_pcb(globals())
    raise SystemExit(0)

(OUT/f'kicad/{SLUG}_lower.kicad_pcb').write_text(lower_board_text(),encoding='utf-8')
(OUT/f'kicad/{SLUG}_upper.kicad_pcb').write_text(upper_board_text(),encoding='utf-8')

# Footprint libraries saved separately too
fpdir=OUT/'kicad/AgentPad.pretty'; fpdir.mkdir(exist_ok=True)
# Extract a simple standalone footprint; useful for later editing.
# RP2040-Zero-M is visible above the carrier PCB through the upper-plate notch.
fp='''(footprint "RP2040-Zero-M_Header_Top" (version 20240108) (generator pcbnew) (layer "F.Cu")\n  (attr through_hole)\n  (fp_rect (start -9 -11.75) (end 9 11.75) (stroke (width 0.2) (type default)) (fill none) (layer "F.SilkS"))\n  (fp_text reference "U1" (at 0 0 90) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n  (fp_text value "RP2040-Zero-M" (at 0 13.5) (layer "F.Fab") hide (effects (font (size 1 1) (thickness 0.15))))\n'''
for n,(x,y) in {**{i+1:(HEADER_ROW_HALF_SPACING,y) for i,y in enumerate(side_y)},**{15+i:(-HEADER_ROW_HALF_SPACING,y) for i,y in enumerate(reversed(side_y))}}.items():
    fp+=f'  (pad "{n}" thru_hole circle (at {x:.3f} {y:.3f}) (size 1.8 1.8) (drill 1.0) (layers "*.Cu" "*.Mask"))\n'
fp+=')\n'
(fpdir/'RP2040-Zero-M_Header_Top.kicad_mod').write_text(fp,encoding='utf-8')

# ---------- Gerber writer ----------
# RS-274X helper using 4.6 format mm
def gcoord(v): return f'{int(round(v*1_000_000)):010d}'
def gerber_header(name):
    return [f'G04 {name}*','%FSLAX46Y46*%','%MOMM*%','%ADD10C,0.250*%','%ADD11C,0.300*%','%ADD12C,0.450*%','%ADD13C,0.600*%','%ADD14C,0.700*%','%ADD20R,2.550X2.500*%','%ADD21R,2.200X1.700*%','%ADD22C,1.200*%','%ADD23C,2.000*%','%ADD24C,3.400*%','%ADD25C,1.800*%','%ADD26C,1.900*%','%LPD*%','G01*']
def gerber_footer(): return ['M02*']
def draw_line(g,a,b,ap=10):
    g += [f'D{ap}*',f'X{gcoord(a[0])}Y{gcoord(a[1])}D02*',f'X{gcoord(b[0])}Y{gcoord(b[1])}D01*']
def flash(g,p,ap): g += [f'D{ap}*',f'X{gcoord(p[0])}Y{gcoord(p[1])}D03*']
def rect_outline(g,x1,y1,x2,y2,ap=10):
    draw_line(g,(x1,y1),(x2,y1),ap); draw_line(g,(x2,y1),(x2,y2),ap); draw_line(g,(x2,y2),(x1,y2),ap); draw_line(g,(x1,y2),(x1,y1),ap)

def circle_poly(g,c,r,ap=10,n=72):
    pts=[(c[0]+r*math.cos(2*math.pi*i/n),c[1]+r*math.sin(2*math.pi*i/n)) for i in range(n+1)]
    for a,b in zip(pts,pts[1:]): draw_line(g,a,b,ap)

def polygon_outline(g,poly,ap=10):
    """Emit every boundary of a Shapely polygon as an explicitly closed path."""
    rings=[poly.exterior,*poly.interiors]
    for ring in rings:
        pts=list(ring.coords)
        for a,b in zip(pts,pts[1:]): draw_line(g,a,b,ap)

def geometry_outlines(g,geom,ap=10):
    """Emit Polygon/MultiPolygon boundaries without any open Gerber contours."""
    if geom.geom_type=='Polygon':
        polygon_outline(g,geom,ap)
    elif geom.geom_type=='MultiPolygon':
        for poly in geom.geoms: polygon_outline(g,poly,ap)
    else:
        for child in geom.geoms: geometry_outlines(g,child,ap)

GERBER_FILE_FUNCTIONS={
    'F_Cu':'Copper,L1,Top', 'B_Cu':'Copper,L2,Bot',
    'F_Mask':'Soldermask,Top', 'B_Mask':'Soldermask,Bot',
    'F_Paste':'Paste,Top', 'B_Paste':'Paste,Bot',
    'F_Silkscreen':'Legend,Top', 'B_Silkscreen':'Legend,Bot',
    'Edge_Cuts':'Profile,NP',
}
def write_layer(path, lines):
    layer=next((name for name in GERBER_FILE_FUNCTIONS if f'-{name}.gbr' in path.name),None)
    if layer:
        part='Array' if path.parent.name=='panel' else 'Single'
        attrs=[
            '%TF.GenerationSoftware,AgentPad,generator,1.0*%',
            f'%TF.FileFunction,{GERBER_FILE_FUNCTIONS[layer]}*%',
            f'%TF.Part,{part}*%',
        ]
        lines=lines[:1]+attrs+lines[1:]
    path.write_text('\n'.join(lines)+'\n',encoding='ascii')

# Gerbers for lower board individual
ld=OUT/'gerber/individual_lower'
# F.Cu
G=gerber_header(f'AgentPad {REV_PLAIN} Lower F.Cu')
# RP2040-Zero-M plated header pads
for n,p in MCU_PINS.items(): flash(G,p,25)
# PTH annuli / routing vias / encoder
for x,y,nm in route_vias: flash(G,(x,y),22)
for name in ['A','B','C','S1','S2']: flash(G,enc_pads[name],23)
for name in ['MP1','MP2']: flash(G,enc_pads[name],24)
for layer,net,w,pts in routes:
    if layer!='F.Cu': continue
    ap={0.30:11,0.45:12,0.50:12,0.60:13,0.70:14}.get(round(w,2),11)
    for a,b in zip(pts,pts[1:]):
        if a!=b: draw_line(G,a,b,ap)
G+=gerber_footer(); write_layer(ld/f'{SLUG}_lower-F_Cu.gbr',G)
# B.Cu
G=gerber_header(f'AgentPad {REV_PLAIN} Lower B.Cu')
for n,p in MCU_PINS.items(): flash(G,p,25)
for i in range(1,NUM_KEYS+1):
    flash(G,sw[i]['p1'],20); flash(G,sw[i]['p2'],20)
for x,y,nm in route_vias: flash(G,(x,y),22)
for name in ['A','B','C','S1','S2']: flash(G,enc_pads[name],23)
for name in ['MP1','MP2']: flash(G,enc_pads[name],24)
for layer,net,w,pts in routes:
    if layer!='B.Cu': continue
    ap={0.30:11,0.45:12,0.50:12,0.60:13,0.70:14}.get(round(w,2),12)
    for a,b in zip(pts,pts[1:]):
        if a!=b: draw_line(G,a,b,ap)
G+=gerber_footer(); write_layer(ld/f'{SLUG}_lower-B_Cu.gbr',G)
# masks/paste approximate
for name,side in [('F_Mask','F'),('B_Mask','B'),('B_Paste','P')]:
    G=gerber_header(f'AgentPad {REV_PLAIN} Lower {name}')
    if side=='F':
        for p in MCU_PINS.values(): flash(G,p,26)
        for x,y,nm2 in route_vias: flash(G,(x,y),22)
        for nm in ['A','B','C','S1','S2']: flash(G,enc_pads[nm],23)
        for nm in ['MP1','MP2']: flash(G,enc_pads[nm],24)
    else:
        if side=='B':
            for p in MCU_PINS.values(): flash(G,p,26)
        for i in range(1,NUM_KEYS+1): flash(G,sw[i]['p1'],20); flash(G,sw[i]['p2'],20)
        if side=='B':
            for x,y,nm2 in route_vias: flash(G,(x,y),22)
            for nm in ['A','B','C','S1','S2']: flash(G,enc_pads[nm],23)
            for nm in ['MP1','MP2']: flash(G,enc_pads[nm],24)
    G+=gerber_footer(); write_layer(ld/f'{SLUG}_lower-{name}.gbr',G)
# Silkscreen (simple outlines/labels omitted text because Gerber text vectorization not implemented; outline marks only)
G=gerber_header(f'AgentPad {REV_PLAIN} Lower F.SilkS')
rect_outline(G,MCU_CX-9,MCU_CY-11.75,MCU_CX+9,MCU_CY+11.75,10)
for cx,cy in keys: rect_outline(G,cx-7,cy-7,cx+7,cy+7,10)
circle_poly(G,enc_center,3.0,10)
G+=gerber_footer(); write_layer(ld/f'{SLUG}_lower-F_Silkscreen.gbr',G)
# Edge cuts individual
G=gerber_header(f'AgentPad {REV_PLAIN} Lower Edge Cuts')
geometry_outlines(G,LOWER_BOARD_SHAPE,10)
for cx,cy in slot_centers: rect_outline(G,cx-SLOT_W/2,cy-SLOT_H/2,cx+SLOT_W/2,cy+SLOT_H/2,10)
for cx,cy in keys:
    for p,d in SW_ROUTED_HOLES:
        circle_poly(G,(cx+p[0],cy+p[1]),d/2,10)
G+=gerber_footer(); write_layer(ld/f'{SLUG}_lower-Edge_Cuts.gbr',G)

# Upper individual layers: edge cuts + top silk reference
ud=OUT/'gerber/individual_upper'
G=gerber_header(f'AgentPad {REV_PLAIN} Upper Edge Cuts')
geometry_outlines(G,UPPER_BOARD_SHAPE,10)
for cx,cy in slot_centers: rect_outline(G,cx-SLOT_W/2,cy-SLOT_H/2,cx+SLOT_W/2,cy+SLOT_H/2,10)
for cx,cy in keys: rect_outline(G,cx-7,cy-7,cx+7,cy+7,10)
if REV==1: circle_poly(G,enc_center,3.75,10)
else: rect_outline(G,enc_center[0]-7,enc_center[1]-7,enc_center[0]+7,enc_center[1]+7,10)
G+=gerber_footer(); write_layer(ud/f'{SLUG}_upper-Edge_Cuts.gbr',G)
G=gerber_header(f'AgentPad {REV_PLAIN} Upper F.SilkS')
for cx,cy in keys: rect_outline(G,cx-7.5,cy-7.5,cx+7.5,cy+7.5,10)
circle_poly(G,enc_center,5.5,10)
G+=gerber_footer(); write_layer(ud/f'{SLUG}_upper-F_Silkscreen.gbr',G)
# blank copper/mask to keep fab systems happy
for nm in ['F_Cu','B_Cu','F_Mask','B_Mask']:
    G=gerber_header(f'AgentPad {REV_PLAIN} Upper {nm}')+gerber_footer(); write_layer(ud/f'{SLUG}_upper-{nm}.gbr',G)

# Excellon drills individual lower
# format metric 3:3-ish decimal explicit to maximize compatibility
def write_excellon(path, holes):
    # holes list diameter,x,y,plated
    diams=sorted(set(round(h[0],4) for h in holes))
    tool={d:i+1 for i,d in enumerate(diams)}
    is_npth='NPTH' in path.stem
    function='NonPlated,1,2,NPTH' if is_npth else 'Plated,1,2,PTH'
    part='Array' if path.parent.name=='panel' else 'Single'
    lines=['M48',f'; AgentPad {REV_PLAIN} Drill',
           '; #@! TF.GenerationSoftware,AgentPad,generator,1.0',
           f'; #@! TF.FileFunction,{function}',f'; #@! TF.Part,{part}','FMAT,2','METRIC']
    for d in diams:
        if is_npth:
            aper='NonPlated,NPTH,ComponentDrill'
        else:
            aper='Plated,PTH,ViaDrill' if abs(d-VIA_DRILL)<1e-6 else 'Plated,PTH,ComponentDrill'
        lines.append(f'; #@! TA.AperFunction,{aper}')
        lines.append(f'T{tool[d]:02d}C{d:.4f}')
    lines+=['%','G90']
    current=None
    for d,x,y in holes:
        d=round(d,4)
        if current!=d: lines.append(f'T{tool[d]:02d}'); current=d
        lines.append(f'X{x:.3f}Y{y:.3f}')
    lines.append('M30')
    path.write_text('\n'.join(lines)+'\n',encoding='ascii')

pth=[(1.0,x,y) for x,y in MCU_PINS.values()]
pth += [(VIA_DRILL,x,y) for x,y,nm in route_vias]; npth=[]
if DIRECT_SOLDER:
    for i in range(1,NUM_KEYS+1):
        pth += [(SWITCH_PTH_DRILL,*sw[i]['h1']),(SWITCH_PTH_DRILL,*sw[i]['h2'])]
for i,(cx,cy) in enumerate(keys,1):
    npth += [(d,cx+p[0],cy+p[1]) for p,d in SW_ROUTED_HOLES]
for nm in ['A','B','C','S1','S2']: pth.append((1.0,*enc_pads[nm]))
for nm in ['MP1','MP2']: pth.append((2.8,*enc_pads[nm]))
write_excellon(ld/f'{SLUG}_lower-PTH.drl',pth)
# All non-plated mechanical holes are routed on Edge.Cuts; only the plated
# drill file is required.

# ---------- Panel Gerbers ----------
# Compact panel: 4 mm rails, two boards, and an 8 mm spacer gutter.
PW,PH=2*BW+16.0,max(BH+8.0,80.0)
LO=(4.0,4.0)
GUTTER_LEFT,GUTTER_RIGHT=LO[0]+BW,LO[0]+BW+8.0
UO=(GUTTER_RIGHT,4.0)
(OUT/f'kicad/{SLUG}_panel_silkscreen.kicad_pcb').write_text(panel_silkscreen_board_text(),encoding='utf-8')
BOARD_TAB_XS=(20.0,48.0) if REV==1 else (12.0,50.0)
BOARD_TAB_W=1.0
ROUTING_SLOT_W=1.0
# Four 18 x 6 mm spacer pieces in the gutter.  After assembly they provide a
# nominal 6 mm switch-plate gap; the top-mounted RP2040-Zero-M passes through
# the dedicated opening in the upper plate.
# tabs at each plate.
spacer_y=[5.0,24.0,43.0,62.0] if REV in (1,2) else [4.0,23.0,42.0,61.0]
# local polygon in panel coords with tabs left/right representing 1.5mm insertion tabs
# Rotated in actual assembly: piece long dimension vertical in panel = 18mm, narrow dimension horizontal=5mm plus tabs to 8mm.
def spacer_poly(cy):
    # 6 mm body inside the gutter; insertion tabs reach both gutter edges.
    ym=cy+9
    xl,xr=GUTTER_LEFT+1.0,GUTTER_RIGHT-1.0
    return [(xl,cy),(xr,cy),(xr,ym-1.5),(GUTTER_RIGHT,ym-1.5),(GUTTER_RIGHT,ym+1.5),(xr,ym+1.5),(xr,cy+18),(xl,cy+18),(xl,ym+1.5),(GUTTER_LEFT,ym+1.5),(GUTTER_LEFT,ym-1.5),(xl,ym-1.5),(xl,cy)]

# map local lower content to panel

def off(p,o): return (p[0]+o[0],p[1]+o[1])

# Panel copper from lower only
pd=OUT/'gerber/panel'
for layername,srcside in [('F_Cu','F.Cu'),('B_Cu','B.Cu')]:
    G=gerber_header(f'AgentPad {REV_PLAIN} Panel {layername}')
    # flashes offset
    if srcside=='F.Cu':
        for p in MCU_PINS.values(): flash(G,off(p,LO),25)
    if srcside=='B.Cu':
        for p in MCU_PINS.values(): flash(G,off(p,LO),25)
    for p in sig_vias.values(): flash(G,off(p,LO),22)
    for i in range(1,NUM_KEYS+1):
        if srcside=='B.Cu': flash(G,off(sw[i]['p1'],LO),20); flash(G,off(sw[i]['p2'],LO),20)
    for x,y,nm2 in route_vias: flash(G,off((x,y),LO),22)
    for nm in ['A','B','C','S1','S2']: flash(G,off(enc_pads[nm],LO),23)
    for nm in ['MP1','MP2']: flash(G,off(enc_pads[nm],LO),24)
    for layer,net,w,pts in routes:
        if layer!=srcside: continue
        ap={0.30:11,0.45:12,0.50:12,0.60:13,0.70:14}.get(round(w,2),11)
        for a,b in zip(pts,pts[1:]):
            if a!=b: draw_line(G,off(a,LO),off(b,LO),ap)
    G+=gerber_footer(); write_layer(pd/f'{SLUG}_panel-{layername}.gbr',G)

# Panel masks/paste
for nm in ['F_Mask','B_Mask','B_Paste']:
    G=gerber_header(f'AgentPad {REV_PLAIN} Panel {nm}')
    if nm=='F_Mask':
        for p in MCU_PINS.values(): flash(G,off(p,LO),26)
        for p in sig_vias.values(): flash(G,off(p,LO),22)
        for x,y,nm2 in route_vias: flash(G,off((x,y),LO),22)
        for x in ['A','B','C','S1','S2']: flash(G,off(enc_pads[x],LO),23)
        for x in ['MP1','MP2']: flash(G,off(enc_pads[x],LO),24)
    else:
        for i in range(1,NUM_KEYS+1): flash(G,off(sw[i]['p1'],LO),20); flash(G,off(sw[i]['p2'],LO),20)
        if nm=='B_Mask':
            for p in MCU_PINS.values(): flash(G,off(p,LO),26)
            for p in sig_vias.values(): flash(G,off(p,LO),22)
            for x,y,nm2 in route_vias: flash(G,off((x,y),LO),22)
            for x in ['A','B','C','S1','S2']: flash(G,off(enc_pads[x],LO),23)
            for x in ['MP1','MP2']: flash(G,off(enc_pads[x],LO),24)
    G+=gerber_footer(); write_layer(pd/f'{SLUG}_panel-{nm}.gbr',G)
# The production panel intentionally has no silkscreen.  Reference graphics are
# kept in the editable individual KiCad boards, while the panel avoids all
# silkscreen-to-pad and silkscreen-to-hole DFM findings.
G=gerber_header(f'AgentPad {REV_PLAIN} Panel F.SilkS')
G+=gerber_footer(); write_layer(pd/f'{SLUG}_panel-F_Silkscreen.gbr',G)

# Panel edge cuts.  Every internal route is represented by the boundary of a
# closed 1.0 mm non-plated routing slot.  The routing-slot polygons are locally
# removed at the solid breakaway necks.  This keeps the mechanical result of
# the original panel while avoiding the open/incomplete profile segments that
# fabrication CAM systems reject.
G=gerber_header(f'AgentPad {REV_PLAIN} Panel Edge Cuts')
rect_outline(G,0,0,PW,PH,10)

lower_panel_shape=translate(LOWER_BOARD_SHAPE,xoff=LO[0],yoff=LO[1])
upper_panel_shape=translate(UPPER_BOARD_SHAPE,xoff=UO[0],yoff=UO[1])
spacer_panel_shapes=[Polygon(spacer_poly(sy)) for sy in spacer_y]

def outside_slot(shape):
    # A mitred outside buffer leaves the finished board edge at the exact
    # original coordinate; only panel/rail material is consumed by the slot.
    return shape.buffer(ROUTING_SLOT_W,join_style=2).difference(shape)

panel_routing=None
if PANEL_PROFILE_MODE=='continuous':
    # Fabricator-requested replacement form: every requested cut is one fully
    # connected closed centreline.  CAM may add temporary production retention
    # tabs as needed; no intentional gap remains in the customer profile data.
    polygon_outline(G,lower_panel_shape,10)
    polygon_outline(G,upper_panel_shape,10)
    for shape in spacer_panel_shapes: polygon_outline(G,shape,10)
else:
    panel_routing=outside_slot(lower_panel_shape).union(outside_slot(upper_panel_shape))
    for shape in spacer_panel_shapes:
        panel_routing=panel_routing.union(outside_slot(shape))

    # Four rail tabs per functional board (two at the top and two at the bottom).
    bridge_windows=[]
    for ox,oy in [LO,UO]:
        for tx in BOARD_TAB_XS:
            x=ox+tx
            bridge_windows += [
                box(x-BOARD_TAB_W/2,oy-ROUTING_SLOT_W-0.1,
                    x+BOARD_TAB_W/2,oy+0.1),
                box(x-BOARD_TAB_W/2,oy+BH-0.1,
                    x+BOARD_TAB_W/2,oy+BH+ROUTING_SLOT_W+0.1),
            ]

    # Each removable spacer remains connected to both functional boards by a
    # centred 1.0 mm neck.  Remove both the board-side and spacer-side slot bands
    # across the neck so no hidden cut crosses the intended connection.
    for sy in spacer_y:
        ym=sy+9.0
        for x in [GUTTER_LEFT,GUTTER_RIGHT]:
            bridge_windows.append(box(x-ROUTING_SLOT_W-0.1,ym-BOARD_TAB_W/2,
                                      x+ROUTING_SLOT_W+0.1,ym+BOARD_TAB_W/2))

    panel_routing=panel_routing.difference(unary_union(bridge_windows))
    panel_routing=unary_union(panel_routing)
    geometry_outlines(G,panel_routing,10)
# lower/upper slots and cutouts
for o in [LO,UO]:
    for cx,cy in slot_centers: rect_outline(G,o[0]+cx-SLOT_W/2,o[1]+cy-SLOT_H/2,o[0]+cx+SLOT_W/2,o[1]+cy+SLOT_H/2,10)
for cx,cy in keys:
    for p,d in SW_ROUTED_HOLES:
        circle_poly(G,off((cx+p[0],cy+p[1]),LO),d/2,10)
for cx,cy in keys: rect_outline(G,UO[0]+cx-7,UO[1]+cy-7,UO[0]+cx+7,UO[1]+cy+7,10)
if REV==1: circle_poly(G,off(enc_center,UO),3.75,10)
else: rect_outline(G,UO[0]+enc_center[0]-7,UO[1]+enc_center[1]-7,UO[0]+enc_center[0]+7,UO[1]+enc_center[1]+7,10)
G+=gerber_footer(); write_layer(pd/f'{SLUG}_panel-Edge_Cuts.gbr',G)

# Panel plated drill file.  Mechanical holes and solid breakaway tabs are all
# represented on Edge.Cuts, so no ambiguous second drill layer is uploaded.
ppth=[(d,x+LO[0],y+LO[1]) for d,x,y in pth]
write_excellon(pd/f'{SLUG}_panel-PTH.drl',ppth)

# ---------- Custom DRC ----------
issues=[]; warnings=[]
board=LOWER_BOARD_SHAPE
# DFM guards for the two failure modes reported by JLCPCB: overlapping mask
# apertures and duplicate/too-close plated drill hits.
fmask=[]; bmask=[]
for p in MCU_PINS.values():
    fmask.append(Point(*p).buffer(0.95)); bmask.append(Point(*p).buffer(0.95))
for i in range(1,NUM_KEYS+1):
    for p in [sw[i]['p1'],sw[i]['p2']]:
        bmask.append(box(p[0]-1.275,p[1]-1.25,p[0]+1.275,p[1]+1.25))
    if DIRECT_SOLDER:
        for p in [sw[i]['h1'],sw[i]['h2']]:
            fmask.append(Point(*p).buffer(SWITCH_PTH_SIZE/2+0.05))
            bmask.append(Point(*p).buffer(SWITCH_PTH_SIZE/2+0.05))
for nm in ['A','B','C','S1','S2']:
    fmask.append(Point(*enc_pads[nm]).buffer(1.0)); bmask.append(Point(*enc_pads[nm]).buffer(1.0))
for nm in ['MP1','MP2']:
    fmask.append(Point(*enc_pads[nm]).buffer(1.7)); bmask.append(Point(*enc_pads[nm]).buffer(1.7))
for x,y,nm in route_vias:
    fmask.append(Point(x,y).buffer(VIA_SIZE/2)); bmask.append(Point(x,y).buffer(VIA_SIZE/2))
for layer,apertures in [('F.Mask',fmask),('B.Mask',bmask)]:
    overlaps=sum(a.intersection(b).area>1e-9 for i,a in enumerate(apertures) for b in apertures[i+1:])
    if overlaps: issues.append(f'{layer} has {overlaps} overlapping solder-mask aperture pairs')
if len({(round(x,4),round(y,4)) for d,x,y in ppth}) != len(ppth):
    issues.append('Panel PTH drill file has duplicate coordinates')
min_pth_gap=min(math.hypot(a[1]-b[1],a[2]-b[2])-(a[0]+b[0])/2
                for i,a in enumerate(ppth) for b in ppth[i+1:])
if min_pth_gap < 0.20-1e-9:
    issues.append(f'Panel PTH drill-edge spacing is only {min_pth_gap:.3f} mm')
# CAM-facing panel checks.  All internal routed areas must be valid closed
# polygons, at least JLCPCB's 1.0 mm non-plated-slot minimum, and remain inside
# the single closed outer panel outline.
if PANEL_PROFILE_MODE=='closed_slots':
    if not panel_routing.is_valid or panel_routing.is_empty:
        issues.append('Panel routing-slot geometry is invalid or empty')
    if not box(0,0,PW,PH).covers(panel_routing):
        issues.append('Panel routing-slot geometry extends outside the panel outline')
    slot_clearance=panel_routing.buffer(-ROUTING_SLOT_W/2+0.001)
    if slot_clearance.is_empty:
        issues.append(f'Panel routing slots do not retain the required {ROUTING_SLOT_W:.1f} mm width')
else:
    for name,shape in [('lower',lower_panel_shape),('upper',upper_panel_shape)]+[(f'spacer{i+1}',s) for i,s in enumerate(spacer_panel_shapes)]:
        if not shape.is_valid or not shape.exterior.is_ring:
            issues.append(f'Panel {name} profile is not a valid closed ring')
# Component/hole containment
for i,(cx,cy) in enumerate(keys,1):
    for label,p in [('pad1',sw[i]['p1']),('pad2',sw[i]['p2'])]:
        if not board.buffer(-0.2).contains(Point(*p)): issues.append(f'SW{i} {label} outside board')
for nm,p in enc_pads.items():
    if nm.startswith('MP'): margin=0
    if not board.buffer(-0.2).contains(Point(*p)): issues.append(f'Encoder {nm} outside board')
# MCU body fits, USB intended to overhang top; body must fit board
mcu_body=box(MCU_CX-MCU_W/2,MCU_CY-MCU_H/2,MCU_CX+MCU_W/2,MCU_CY+MCU_H/2)
if not board.contains(mcu_body): issues.append('RP2040-Zero body does not fit lower board')
# upper cutouts non-overlap and within board
cuts=[]
for i,(cx,cy) in enumerate(keys,1):
    p=box(cx-7,cy-7,cx+7,cy+7); cuts.append(p)
    if not board.contains(p): issues.append(f'Upper MX cutout {i} outside board')
enc_cut=Point(*enc_center).buffer(3.75) if REV==1 else box(enc_center[0]-7,enc_center[1]-7,enc_center[0]+7,enc_center[1]+7)
if not board.contains(enc_cut): issues.append('Encoder cutout outside board')
upper_notch=box(UPPER_NOTCH_X1,0,UPPER_NOTCH_X2,UPPER_NOTCH_Y)
if not upper_notch.covers(mcu_body): issues.append('Upper RP2040 notch does not contain module envelope')
if upper_notch.distance(cuts[1]) < 1.5:
    issues.append(f'Upper RP2040 notch to center MX cutout web is only {upper_notch.distance(cuts[1]):.3f} mm')
for i in range(len(cuts)):
    for j in range(i+1,len(cuts)):
        if cuts[i].intersects(cuts[j]): issues.append(f'MX cutouts {i+1}/{j+1} overlap')
# track endpoints should start/end on expected pads for each net; check gross containment
for layer,net,w,pts in routes:
    ls=LineString(pts)
    if not board.buffer(0.1).contains(ls): issues.append(f'{layer} {net} route outside board')
# copper clearance heuristic: only compare route LineStrings of different nets same layer; endpoint pads not modeled fully.
for idx,(layer,net,w,pts) in enumerate(routes):
    a=LineString(pts)
    for layer2,net2,w2,pts2 in routes[idx+1:]:
        if layer!=layer2 or net==net2: continue
        b=LineString(pts2)
        d=a.distance(b)-(w+w2)/2
        if d < 0.20:
            issues.append(f'Copper clearance <0.20mm: {layer} {net} vs {net2}: {d:.3f} mm')
# slot/cutout distances from components
for sc in slot_centers:
    sr=box(sc[0]-SLOT_W/2,sc[1]-SLOT_H/2,sc[0]+SLOT_W/2,sc[1]+SLOT_H/2)
    if not board.contains(sr): issues.append(f'Spacer slot at {sc} extends outside rounded board outline')
    if sr.intersects(mcu_body): issues.append('Spacer slot collides with MCU')
    for cut_name,cut in [(f'MX{i}',p) for i,p in enumerate(cuts,1)]+[('encoder',enc_cut)]:
        if sr.distance(cut) < 1.0-1e-9:
            issues.append(f'Spacer slot to {cut_name} material web is only {sr.distance(cut):.3f} mm')
# KiCad's official DRC is the release gate. The geometric checks above remain
# as generator-level assertions for conditions outside KiCad's electrical DRC.
kicad_cli=os.environ.get('KICAD_CLI') or shutil.which('kicad-cli9') or shutil.which('kicad-cli')
if not kicad_cli:
    raise RuntimeError('kicad-cli is required to generate validated production data')
drc_dir=OUT/'docs/drc'; drc_dir.mkdir(parents=True,exist_ok=True)
kicad_version=subprocess.run([kicad_cli,'--version'],check=True,capture_output=True,text=True).stdout.strip()
kicad_results={}
for board_name in ['lower','upper']:
    board_path=OUT/f'kicad/{SLUG}_{board_name}.kicad_pcb'
    report_path=drc_dir/f'{SLUG}_{board_name}-drc.json'
    run=subprocess.run([
        kicad_cli,'pcb','drc','--severity-all','--units','mm','--format','json',
        '--output',str(report_path),str(board_path)
    ],capture_output=True,text=True)
    if run.returncode:
        raise RuntimeError(f'KiCad DRC failed for {board_name}: {run.stderr or run.stdout}')
    data=json.loads(report_path.read_text(encoding='utf-8'))
    kicad_results[board_name]={
        'violations':len(data.get('violations',[])),
        'unconnected_items':len(data.get('unconnected_items',[])),
    }
kicad_pass=all(not result['violations'] and not result['unconnected_items'] for result in kicad_results.values())

# Release copper/mask/paste comes from KiCad itself so that every pad and trace
# carries standard X2 aperture, component-pin, and net attributes.  JLCPCB uses
# these attributes to distinguish intentional same-net joins from clearances.
def translate_kicad_gerber(src,dst,dx,dy):
    xoff=int(round(dx*1_000_000)); yoff=int(round(dy*1_000_000))
    out=[]
    for line in src.read_text(encoding='ascii').splitlines():
        if line.startswith('%TF.SameCoordinates,'): continue
        # Translate only plotted operation coordinates.  X/Y tokens inside
        # aperture macro definitions are dimensions and must remain untouched.
        if not line.startswith('%'):
            line=re.sub(r'X(-?\d+)',lambda m:f'X{int(m.group(1))+xoff}',line)
            # KiCad plots board Y downward as negative Gerber coordinates;
            # mirror it back to the positive panel coordinate system.
            line=re.sub(r'Y(-?\d+)',lambda m:f'Y{-int(m.group(1))+yoff}',line)
        out.append(line)
        if line.startswith('%TF.FileFunction,'):
            out.append('%TF.Part,Array*%')
    dst.write_text('\n'.join(out)+'\n',encoding='ascii')

with tempfile.TemporaryDirectory(prefix='agentpad_kicad_gerber_') as td:
    official=Path(td)
    run=subprocess.run([
        kicad_cli,'pcb','export','gerbers','--no-protel-ext',
        '--layers','F.Cu,B.Cu,F.Mask,B.Mask,B.Paste,F.SilkS,B.SilkS',
        '--output',str(official)+'/',str(OUT/f'kicad/{SLUG}_lower.kicad_pcb')
    ],capture_output=True,text=True)
    if run.returncode:
        raise RuntimeError(f'KiCad Gerber export failed: {run.stderr or run.stdout}')
    for layer in ['F_Cu','B_Cu','F_Mask','B_Mask','B_Paste','F_Silkscreen','B_Silkscreen']:
        src=official/f'{SLUG}_lower-{layer}.gbr'
        if not src.exists(): raise RuntimeError(f'KiCad did not export {src.name}')
        shutil.copy(src,ld/f'{SLUG}_lower-{layer}.gbr')
        if layer not in ('F_Silkscreen','B_Silkscreen'):
            translate_kicad_gerber(src,pd/f'{SLUG}_panel-{layer}.gbr',*LO)
    run=subprocess.run([
        kicad_cli,'pcb','export','gerbers','--no-protel-ext',
        '--layers','F.SilkS,B.SilkS','--output',str(official)+'/',
        str(OUT/f'kicad/{SLUG}_upper.kicad_pcb')
    ],capture_output=True,text=True)
    if run.returncode:
        raise RuntimeError(f'KiCad upper silkscreen export failed: {run.stderr or run.stdout}')
    for layer in ['F_Silkscreen','B_Silkscreen']:
        upper_silk=official/f'{SLUG}_upper-{layer}.gbr'
        if not upper_silk.exists(): raise RuntimeError(f'KiCad did not export {upper_silk.name}')
        shutil.copy(upper_silk,ud/f'{SLUG}_upper-{layer}.gbr')
    run=subprocess.run([
        kicad_cli,'pcb','export','gerbers','--no-protel-ext',
        '--layers','F.SilkS,B.SilkS','--output',str(official)+'/',
        str(OUT/f'kicad/{SLUG}_panel_silkscreen.kicad_pcb')
    ],capture_output=True,text=True)
    if run.returncode:
        raise RuntimeError(f'KiCad panel silkscreen export failed: {run.stderr or run.stdout}')
    for layer in ['F_Silkscreen','B_Silkscreen']:
        panel_silk=official/f'{SLUG}_panel_silkscreen-{layer}.gbr'
        if not panel_silk.exists(): raise RuntimeError(f'KiCad did not export {panel_silk.name}')
        translate_kicad_gerber(panel_silk,pd/f'{SLUG}_panel-{layer}.gbr',0,0)

warnings.append('EC11 footprint follows KiCad/Alps EC11E geometry; confirm your purchased encoder is EC11E-compatible before soldering.')
warnings.append('Panel is customer-panelized. JLCPCB may apply panelization/special-board charges depending on order options.')

report=[f'# AgentPad {REV_DOTTED} validation report','',f'KiCad standard DRC result: **{"PASS" if kicad_pass else "FAIL"}**','',f'- KiCad CLI version: {kicad_version}']
for board_name,result in kicad_results.items():
    report.append(f'- {board_name.capitalize()} PCB: {result["violations"]} violations, {result["unconnected_items"]} unconnected items')
report+=['','## Panel profile design',
         f'- Individual board: {BW:g} x {BH:g} mm',
         f'- Manufacturing panel: {PW:g} x {PH:g} mm']
if PANEL_PROFILE_MODE=='continuous':
    report += ['- Fabricator replacement mode: every board/spacer cutting line is a fully connected closed loop',
               '- No intentional cutting-line gaps remain; production retention is left to fabricator CAM']
else:
    report += [f'- Board tabs: {BOARD_TAB_W:g} mm solid routed necks; no NPTH drill layer',
               f'- Internal separation uses explicitly closed {ROUTING_SLOT_W:g} mm non-plated routing-slot contours',
               '- Functional-board and spacer outlines retain solid tabs for hand separation']
report+=['','## RP2040-Zero-M mechanical fit',
         f'- Module envelope: {MCU_W:g} x {MCU_H:g} mm, entirely within the lower PCB outline',
         '- Pre-soldered side headers use 1.0 mm plated holes on 2.54 mm pitch',
         f'- Module is installed above the lower PCB and visible through a {UPPER_NOTCH_X2-UPPER_NOTCH_X1:g} x {UPPER_NOTCH_Y:g} mm upper-plate notch',
         '- Supplied FR4 spacers preserve the nominal 6.0 mm switch-plate gap while the module passes through the notch',
         f'- Upper-plate front marking: {MARKING} on F.Silkscreen']
if REV==2:
    report+=['','## Rev.2 size reduction',
             '- Width reduced from 68 mm to 62 mm while retaining 19.05 mm key pitch',
             '- Height remains 80 mm because the bottom 14 mm openings already end 0.9 mm from the board edge',
             f'- Lower and upper functional-board exterior corners use R{BOARD_CORNER_RADIUS:g} mm',
             '- Corner spacer slots rotated 90 degrees; minimum slot-to-opening material web is 1.5 mm',
             '- Encoder opening changed from 7.5 mm round to Rookey-style 14 x 14 mm square']
    report+=['','## Rev.2 MX switch mounting',
             f'- Two electrical pins per switch use {SWITCH_PTH_DRILL:g} mm plated holes with {SWITCH_PTH_SIZE:g} mm pads',
             '- PTH pad 1 connects to K1..K8; PTH pad 2 connects to GND',
             '- Existing bottom-side Kailh hot-swap SMD pads remain connected for dual mounting compatibility']
    report+=['','## Rev.2 silkscreen markings',
             f'- Text height / stroke: {SILK_TEXT_SIZE:g} mm / {SILK_TEXT_THICKNESS:g} mm',
             '- F.Silkscreen text reads normally when viewed from the front; B.Silkscreen text is mirrored in the design and reads normally when viewed from the back',
             '- Lower PCB labels: U1 header signals, SW1..SW8 with K1..K8/GND, and ENC1 terminals A/C/B/G/S',
             '- Upper plate labels: AGENTPAD REV2, SW1..SW8, and ENC1',
             '- Panel upload contains separate F_Silkscreen and B_Silkscreen Gerber files']
elif REV==3:
    report+=['','## Rev.3 compact six-key layout',
             '- Six MX switches use a 3 x 2 grid at the unchanged 19.05 mm pitch',
             '- The RP2040-Zero-M and EC11 share the top row',
             '- Assembled height reduced from 80 mm to 62 mm (22.5%); width remains 62 mm',
             f'- Lower and upper functional-board exterior corners use R{BOARD_CORNER_RADIUS:g} mm',
             '- Encoder opening remains a Rookey-style 14 x 14 mm square']
    report+=['','## Rev.3 MX switch mounting and side identification',
             f'- Two electrical pins per switch use {SWITCH_PTH_DRILL:g} mm plated holes with {SWITCH_PTH_SIZE:g} mm pads',
             '- PTH pad 1 connects to K1..K6; PTH pad 2 connects to GND',
             '- Kailh hot-swap sockets mount on the bottom side only',
             '- F.Silkscreen says MX DIRECT / TOP SIDE; B.Silkscreen says KAILH SOCKET / BOTTOM SIDE',
             '- Direct-solder MX switches may instead be installed from the top side']
report+=['',f'Generator geometry checks: **{"PASS" if not issues else "FAIL"}**','']
if issues:
    report+=['## Errors']+[f'- {x}' for x in issues]
else: report+=['## Supplemental checks passed','- Board and cutout containment','- Route board containment','- Same-layer route clearance heuristic >= 0.20 mm','- Switch cutout non-overlap','- RP2040-Zero body envelope fit','- Panel drill and route file generation']
if not issues:
    report+=['- No overlapping F.Mask/B.Mask apertures',
             f'- No duplicate PTH coordinates; minimum PTH drill-edge spacing {min_pth_gap:.3f} mm',
             '- Gerber and Excellon X2 file-function attributes present']
report+=['','## Warnings']+[f'- {x}' for x in warnings]
(OUT/'docs/VALIDATION.md').write_text('\n'.join(report)+'\n',encoding='utf-8')

# ---------- QMK skeleton ----------
(OUT/'firmware/readme.md').write_text(f'''# QMK wiring\n\nDirect GPIOs: GP0..GP{NUM_KEYS-1} = K1..K{NUM_KEYS}, GP8 = encoder A, GP14 = encoder B, GP15 = encoder push.\nAll inputs active-low with internal pull-ups.\nOn-board RP2040-Zero RGB is GPIO16.\n''',encoding='utf-8')

# ---------- Manufacturing docs ----------
manifest={
'project':f'AgentPad {REV_DOTTED}','status':'production-data-generated','assembled_board_mm':[BW,BH],'panel_mm':[PW,PH],
'mcu':'Waveshare RP2040-Zero-M visible top through-hole header mount',
'layout':f'{"3x2" if REV==3 else "3x3"} / {NUM_KEYS}x MX {"direct-solder PTH + bottom-side hot-swap" if DIRECT_SOLDER else "hot-swap"} + 1x EC11',
'gerber_upload_zip':f'manufacturing/{SLUG}_JLCPCB_panel.zip',
'kicad_drc':{'status':'PASS' if kicad_pass else 'FAIL','version':kicad_version,'boards':kicad_results},
'panel_profile':{'mode':PANEL_PROFILE_MODE,'all_cutting_lines_closed':True,
                 'board_tab_width_mm':None if PANEL_PROFILE_MODE=='continuous' else BOARD_TAB_W,
                 'routing_slot_width_mm':None if PANEL_PROFILE_MODE=='continuous' else ROUTING_SLOT_W,
                 'npth_drill_file':False},
'fabrication':{'gerber_x2_attributes':True,'via_in_pad':False,
               'minimum_pth_drill_edge_spacing_mm':round(min_pth_gap,3),
               'silkscreen':{'front_and_back':True,
                             'text_height_mm':SILK_TEXT_SIZE,
                             'stroke_width_mm':SILK_TEXT_THICKNESS,
                             'back_text_mirrored_in_source':True}},
'mechanical':{'rp2040_zero_envelope_mm':[MCU_W,MCU_H],
              'usb_c_overhang_mm':2.0,'board_to_board_gap_mm':6.0,
              'functional_board_corner_radius_mm':BOARD_CORNER_RADIUS,
              'rp2040_mount_side':'lower PCB top, visible through upper plate',
              'header_pitch_mm':2.54,'header_row_spacing_mm':15.24,'header_drill_mm':1.0,
              'upper_rp2040_notch_mm':[round(UPPER_NOTCH_X2-UPPER_NOTCH_X1,2),UPPER_NOTCH_Y],
              'encoder_opening_mm':[14.0,14.0] if DIRECT_SOLDER else [7.5,7.5],
              'encoder_opening_shape':'square' if DIRECT_SOLDER else 'round',
              'mx_switch_electrical_mount':'1.5 mm plated through-hole plus bottom-side Kailh hot-swap SMD' if DIRECT_SOLDER else 'Kailh hot-swap SMD only',
              'kailh_socket_mount_side':'bottom',
              'upper_marking':MARKING},
'geometry_checks':'PASS' if not issues else 'FAIL'}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

(OUT/'docs/JLCPCB_ORDER.md').write_text(f'''# JLCPCB order settings\n\nUse `manufacturing/{SLUG}_JLCPCB_panel.zip` as the upload file.\n\nRecommended settings:\n- Base material: FR-4\n- Layers: 2\n- PCB thickness: 1.6 mm\n- Copper weight: 1 oz\n- Surface finish: Lead-free HASL\n- Min track/spacing used by design: 0.30 mm / KiCad DRC clearance 0.20 mm\n- Board size: {BW:g} x {BH:g} mm\n- Panel size: {PW:g} x {PH:g} mm\n- Customer panelization: Yes (two functional boards + four breakout spacer parts)\n- Breakaway tabs: 2.4 mm, four 0.5 mm mouse-bites per tab\n- Different design count: expect JLCPCB to classify the upper/lower/spacer panel as multiple designs; accept the quoted surcharge if shown.\n- Remove order number: optional\n\nAssembly is intended to be hand-soldered. Do not order PCBA for {REV_DOTTED}.\n\n## Parts\n- Waveshare RP2040-Zero x1\n- Kailh CPG151101S11 MX hot-swap socket x8\n- MX-compatible switches x8\n- Alps EC11E-compatible push encoder x1\n\n## Before payment\nInspect every layer in JLCPCB Gerber Viewer, especially:\n1. Upper-plate 14x14 mm switch cutouts\n2. Encoder {"14 x 14 mm Rookey-style body opening" if REV==2 else "7.5 mm shaft opening"}\n3. RP2040-Zero USB-C at top edge\n4. Hotswap pads on B.Cu/B.Paste\n5. Mouse-bite tabs in panel\n''',encoding='utf-8')

# Keep the human-readable order notes synchronized with the generated geometry.
order_path=OUT/'docs/JLCPCB_ORDER.md'
order_text=order_path.read_text(encoding='utf-8')
if NUM_KEYS != 8:
    order_text=order_text.replace('hot-swap socket x8',f'hot-swap socket x{NUM_KEYS}')
    order_text=order_text.replace('MX-compatible switches x8',f'MX-compatible switches x{NUM_KEYS}')
order_text=order_text.replace('Min track/spacing used by design: 0.30 mm',
                              'Min track/spacing used by design: 0.20 mm')
if PANEL_PROFILE_MODE=='continuous':
    order_text=order_text.replace('Breakaway tabs: 2.4 mm, four 0.5 mm mouse-bites per tab',
                                  'Cutting lines: fully connected closed profiles; fabricator CAM to add temporary retention tabs if required')
    order_text=order_text.replace('Mouse-bite tabs in panel','Fully closed cutting lines in panel')
else:
    order_text=order_text.replace('Breakaway tabs: 2.4 mm, four 0.5 mm mouse-bites per tab',
                                  f'Breakaway tabs: {BOARD_TAB_W:g} mm solid routed tabs (no mouse-bite drill file)')
    order_text=order_text.replace('Mouse-bite tabs in panel','Solid routed breakaway tabs in panel')
order_text=order_text.replace('- Waveshare RP2040-Zero x1',
                              '- Waveshare RP2040-Zero-M (pre-soldered header) x1')
order_text=order_text.replace('RP2040-Zero USB-C at top edge',
                              'RP2040-Zero-M header holes and USB-C at top edge')
if DIRECT_SOLDER:
    order_text=order_text.replace(f'- Kailh CPG151101S11 MX hot-swap socket x{NUM_KEYS}',
                                  f'- Kailh CPG151101S11 hot-swap sockets x{NUM_KEYS} (optional; bottom-side only; omit for direct solder)')
    order_text=order_text.replace('Encoder 7.5 mm shaft opening',
                                  'Encoder 14 x 14 mm Rookey-style body opening')
order_text+=f'''\n## Mechanical fit and marking\n- Install the RP2040-Zero-M above the lower PCB, with USB-C facing the top edge.\n- Its pre-soldered 2.54 mm-pitch side headers fit the 1.0 mm plated holes.\n- The module body and USB-C pass through the 20 x 25 mm top-edge notch and remain visible from above.\n- Supplied FR4 spacers retain the nominal 6 mm MX switch-plate gap.\n- `{MARKING}` is printed on the visible upper-plate F.Silkscreen.\n'''
if DIRECT_SOLDER:
    order_text+=f'''\n## Silkscreen orientation and labels\n- F.Silkscreen text reads normally from the front side.\n- B.Silkscreen text is mirrored in the design data so it reads normally from the back side after fabrication.\n- Minimum label height/stroke is {SILK_TEXT_SIZE:g} mm / {SILK_TEXT_THICKNESS:g} mm.\n- The lower PCB identifies U1 header signals, SW1..SW{NUM_KEYS} nets/GND, and ENC1 terminals A/C/B/G/S.\n- The upper plate identifies every switch opening and the encoder opening.\n- In JLCPCB Gerber Viewer, inspect both `F_Silkscreen` and `B_Silkscreen` from their respective viewing sides before payment.\n'''
    order_text+=f'''\n## MX switch mounting\n- Each switch has two 1.5 mm plated through-holes connected to its input net and GND for direct soldering.\n- Kailh hot-swap sockets must be placed on the B.Cu/B.Paste side. The footprint is not reversible.\n- The board silkscreen identifies the direct-solder top side and Kailh-socket bottom side.\n- Verify that all {NUM_KEYS*2} switch electrical holes show annular copper rings and appear in the plated drill layer before ordering.\n'''
    order_text+=f'''\n## Rounded exterior corners\n- The lower circuit PCB and upper switch plate both use R{BOARD_CORNER_RADIUS:g} mm exterior corners.\n- The 14 x 14 mm switch and encoder openings remain dimensionally unchanged.\n- The rectangular manufacturing-panel outer frame remains square.\n'''
order_path.write_text(order_text,encoding='utf-8')

# copy generator for reproducibility
source_script=Path(__file__).resolve()
target_script=(OUT/f'scripts/generate_agentpad_rev{REV}.py').resolve()
if source_script != target_script:
    shutil.copy(source_script,target_script)
runner_script=source_script.with_name('run_kicad_drc.sh')
if runner_script.exists():
    shutil.copy(runner_script,OUT/'scripts/run_kicad_drc.sh')

# Zip panel Gerbers only for JLC upload
mfg=OUT/'manufacturing'; mfg.mkdir(exist_ok=True)
with zipfile.ZipFile(mfg/f'{SLUG}_JLCPCB_panel.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(pd.iterdir()): z.write(p,p.name)
# individual board zips
for src,name in [(ld,f'{SLUG}_lower_gerber.zip'),(ud,f'{SLUG}_upper_gerber.zip')]:
    with zipfile.ZipFile(mfg/name,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.iterdir()): z.write(p,p.name)
# Complete project zip
zipall=OUT.parent/f'{OUT.name}.zip'
with zipfile.ZipFile(zipall,'w',zipfile.ZIP_DEFLATED) as z:
    for p in OUT.rglob('*'):
        if p.is_file(): z.write(p,p.relative_to(OUT.parent))

print('OUT',OUT)
print('ZIP',zipall)
print('KICAD_DRC', 'PASS' if kicad_pass else 'FAIL', kicad_results)
print('GEOMETRY_CHECKS', 'PASS' if not issues else 'FAIL')
if issues:
    for x in issues: print('ERROR',x)
print('FILES',sum(1 for p in OUT.rglob('*') if p.is_file()))
