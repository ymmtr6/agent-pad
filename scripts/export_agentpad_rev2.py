"""Export the single-PCB Rev2 using KiCad for all fabrication coordinates."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

from shapely.geometry import LineString, Point, box


def export_single_pcb(design):
    out = design['OUT']
    root = Path(__file__).resolve().parent.parent
    name = 'agentpad_rev2_single'
    pcb = out / f'kicad/{name}.kicad_pcb'
    pcb.write_text(design['lower_board_text'](), encoding='utf-8')
    project = json.loads((root / 'kicad/agentpad_rev2_lower.kicad_pro').read_text())
    project['meta']['filename'] = name + '.kicad_pro'
    project['board']['design_settings']['rules']['min_clearance'] = 0.2
    pcb.with_suffix('.kicad_pro').write_text(json.dumps(project, indent=2) + '\n')
    cli = os.environ.get('KICAD_CLI') or shutil.which('kicad-cli9') or shutil.which('kicad-cli')
    if not cli:
        raise RuntimeError('KiCad CLI is required')

    def run(*args):
        result = subprocess.run([cli, *map(str, args)], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout.strip()

    issues = []
    board = design['LOWER_BOARD_SHAPE']
    for i, (cx, cy) in enumerate(design['keys'], 1):
        for (x, y), diameter in design['SW_ROUTED_HOLES']:
            if not board.covers(Point(cx+x, cy+y).buffer(diameter/2)):
                issues.append(f'SW{i}: mechanical hole outside PCB')
    for layer, net, width, points in design['routes']:
        if not board.covers(LineString(points).buffer(width/2)):
            issues.append(f'{net}: route outside PCB on {layer}')
    mount_clearances = []
    for i, (x, y) in enumerate(design['mount_centers'], 1):
        centre = Point(x, y)
        head = centre.buffer(design['MOUNT_HEAD_DIAMETER']/2)
        if not board.covers(head):
            issues.append(f'H{i}: screw head outside board')
        copper = [LineString(points).buffer(width/2) for _, _, width, points in design['routes']]
        copper += [Point(vx, vy).buffer(design['VIA_SIZE']/2) for vx, vy, _ in design['route_vias']]
        # pad_shapes include the router's inflation; recover nominal pad sizes.
        copper += [shape.buffer(-(design['CLEAR']+design['TRACE_W']/2))
                   for shape, _, _ in design['pad_shapes']]
        gap = min(centre.distance(shape)-design['MOUNT_HEAD_DIAMETER']/2 for shape in copper)
        mount_clearances.append(round(gap, 3))
        if gap < 0.5-0.001:
            issues.append(f'H{i}: head-to-copper gap {gap:.3f} mm < 0.5 mm')
        bodies = [box(cx-7, cy-7, cx+7, cy+7) for cx,cy in design['keys']]
        ex,ey = design['enc_center']
        bodies.append(box(ex-7,ey-7,ex+7,ey+7))
        for body in bodies:
            if head.intersects(body):
                issues.append(f'H{i}: screw head overlaps nominal switch/encoder body')
    # Bottom socket footprint coordinates must match the top-inserted MX pins.
    assert design['SW_HOLE1'] == (-3.81, -2.54)
    assert design['SW_HOLE2'] == (2.54, -5.08)
    assert not design['DIRECT_SOLDER'] and not design['slot_centers']
    report = out / f'docs/drc/{name}-drc.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    run('pcb', 'drc', '--severity-all', '--format', 'json', '--output', report, pcb)
    drc = json.loads(report.read_text())
    counts = {key: len(drc.get(key, [])) for key in ('violations', 'unconnected_items')}
    validation = out / 'docs/VALIDATION_REV2.md'
    validation.write_text(
        '# AgentPad Rev2 single-PCB validation\n\n'
        f'- KiCad: {run("--version")}\n'
        f'- DRC violations: {counts["violations"]}\n'
        f'- Unconnected items: {counts["unconnected_items"]}\n'
        f'- Generator geometry checks: {"FAIL" if issues else "PASS"}\n'
        '- One 62 × 80 mm PCB; no upper FR4 plate, spacer slots, or panel.\n'
        '- Eight bottom-side sockets: 16 B.Cu/B.Paste pads; 16 Ø3 mm NPTH socket holes.\n'
        '- Eight Ø3.9878 mm centre holes and sixteen Ø1.75 mm locating holes.\n'
        '- Four Ø2.2 mm NPTH M2 mounting holes; centres 2.5 mm from adjacent edges.\n'
        f'- Ø4 mm head/boss to copper minimum gaps (H1..H4): {mount_clearances} mm.\n'
        '- Ø5 mm copper keepouts on both sides; nominal 14 mm component bodies do not overlap screw heads.\n'
        '- All fabrication layers and both drill files use the same KiCad export coordinates.\n'
        '- Physical socket fit and enclosure fit have not yet been tested.\n'
        + ''.join(f'- ERROR: {issue}\n' for issue in issues), encoding='utf-8')
    if issues or any(counts.values()):
        raise RuntimeError(f'Release blocked: geometry={issues}, DRC={counts}; see {report}')
    gerber = out / 'gerber/rev2_single'
    gerber.mkdir(parents=True, exist_ok=True)
    run('pcb', 'export', 'gerbers', '--no-protel-ext', '--layers',
        'F.Cu,B.Cu,F.Mask,B.Mask,B.Paste,F.SilkS,B.SilkS,Edge.Cuts',
        '--output', str(gerber) + '/', pcb)
    run('pcb', 'export', 'drill', '--excellon-separate-th', '--output',
        str(gerber) + '/', pcb)
    for side, layers in [('front', 'F.Cu,F.SilkS,Edge.Cuts'),
                         ('back', 'B.Cu,B.SilkS,B.Fab,Edge.Cuts')]:
        options = ['--mirror'] if side == 'back' else []
        run('pcb', 'export', 'svg', '--layers', layers, '--mode-single',
            '--fit-page-to-board', '--exclude-drawing-sheet', *options,
            '--output', out / f'docs/rev2_{side}.svg', pcb)
    manufacturing = out / 'manufacturing'
    manufacturing.mkdir(exist_ok=True)
    archive = manufacturing / f'{name}_gerber.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(gerber.iterdir()):
            bundle.write(path, path.name)
    manifest = {
        'project': 'AgentPad Rev2 single PCB', 'status': 'electrically-validated-prototype',
        'board_count': 1, 'assembled_board_mm': [62, 80], 'pcb_thickness_mm': 1.6,
        'panelized': False, 'keys': 8, 'switch_pitch_mm': 19.05,
        'socket': 'Kailh CPG151101S11', 'socket_side': 'B.Cu',
        'switch_insertion_side': 'F.Cu', 'socket_holes': '3.0 mm NPTH',
        'direct_solder_supported': False,
        'mounting': {'screw': 'M2', 'hole_diameter_mm': design['MOUNT_DRILL'],
                     'plated': False, 'centres_mm': design['mount_centers'],
                     'max_head_or_boss_diameter_mm': design['MOUNT_HEAD_DIAMETER'],
                     'copper_keepout_diameter_mm': 2*design['MOUNT_COPPER_RADIUS'],
                     'minimum_head_to_copper_gaps_mm': mount_clearances},
        'gerber_upload_zip': f'manufacturing/{archive.name}',
        'kicad_drc': {'status': 'PASS', **counts}, 'geometry_checks': 'PASS',
        'physical_fit': 'not tested',
        'enclosure': '3D printed; see docs/REV2_SINGLE_PCB.md',
        'key_centres_mm': design['keys'], 'encoder_centre_mm': design['enc_center'],
    }
    (out / 'manifest_rev2.json').write_text(json.dumps(manifest, indent=2) + '\n')
    # Explicit mechanical drawing: copper-only SVG plots can hide NPTH holes.
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 156 110">',
           '<rect width="156" height="110" fill="white"/>',
           '<g font-family="sans-serif" font-size="3" fill="#172b4d">',
           '<text x="8" y="7">FRONT / switches from above</text>',
           '<text x="85" y="7">BACK / sockets from below</text>']
    for side, offset in [('front', 8), ('back', 85)]:
        def px(x):
            return offset + (62-x if side == 'back' else x)
        svg.append(f'<rect x="{offset}" y="12" width="62" height="80" rx="2" fill="#edf5ee" stroke="#234" stroke-width="0.25"/>')
        for i,(x,y) in enumerate(design['mount_centers'],1):
            svg.append(f'<circle cx="{px(x)}" cy="{y+12}" r="2" fill="none" stroke="#789" stroke-width="0.15" stroke-dasharray="0.5 0.5"/>')
            svg.append(f'<circle cx="{px(x)}" cy="{y+12}" r="1.1" fill="white" stroke="#234" stroke-width="0.2"/>')
        for i, (cx, cy) in enumerate(design['keys'], 1):
            if side == 'front':
                svg.append(f'<rect x="{px(cx)-7}" y="{cy+5}" width="14" height="14" fill="none" stroke="#789" stroke-width="0.2"/>')
            else:
                for key in ('p1', 'p2'):
                    x, y = design['sw'][i][key]
                    svg.append(f'<rect x="{px(x)-1.275}" y="{y+10.75}" width="2.55" height="2.5" fill="#bd761a"/>')
            for (x, y), diameter in design['SW_ROUTED_HOLES']:
                svg.append(f'<circle cx="{px(cx+x)}" cy="{cy+y+12}" r="{diameter/2}" fill="white" stroke="#234" stroke-width="0.15"/>')
            svg.append(f'<text x="{px(cx)}" y="{cy+17}" text-anchor="middle" font-size="2">SW{i}</text>')
        for x, y in design['MCU_PINS'].values():
            svg.append(f'<circle cx="{px(x)}" cy="{y+12}" r="0.5" fill="white" stroke="#bd761a" stroke-width="0.4"/>')
        ex, ey = design['enc_center']
        svg.append(f'<circle cx="{px(ex)}" cy="{ey+12}" r="3" fill="none" stroke="#234" stroke-width="0.25"/>')
    svg += ['<text x="8" y="99">62 x 80 mm PCB / 8 MX keys / 4 corner holes: M2, 2.2 mm NPTH</text>',
            '<text x="8" y="105">Large offset holes: 3.0 mm NPTH. Gold pads: bottom only. Mechanical assembly guide.</text>',
            '</g></svg>']
    (out / 'docs/rev2_assembly.svg').write_text('\n'.join(svg))
    for filename in ('generate_agentpad_rev1.py', 'generate_agentpad_rev2.py',
                     'export_agentpad_rev2.py', 'run_kicad_drc.sh'):
        shutil.copy(root / 'scripts' / filename, out / 'scripts' / filename)
    # Retain the project-settings input required to regenerate this package.
    shutil.copy(root / 'kicad/agentpad_rev2_lower.kicad_pro', out / 'kicad')
    for filename in ('REV2_SINGLE_PCB.md', 'JLCPCB_ORDER_REV2.md'):
        shutil.copy(root / 'docs' / filename, out / 'docs')
    shutil.copy(root / 'requirements.txt', out)
    shutil.copytree(root / 'cad/rev2_case', out / 'cad/rev2_case')
    complete = manufacturing / 'agentpad_rev2_single_complete.zip'
    with zipfile.ZipFile(complete, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(out.rglob('*')):
            if path.is_file() and path != complete:
                bundle.write(path, path.relative_to(out))
    print(f'PASS: {pcb}\nGerbers: {archive}\nDRC: {counts}')
