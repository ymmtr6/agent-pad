# Cherry MX compatible 1U keycap

This folder contains a parametric, FDM-oriented 1U keycap for Cherry MX
compatible switches. The default cap is 18.1 x 18.1 mm at its base, with a
15.4 mm square, flat top and gentle side taper. The source dimensions are in
millimetres.

## Files

- `cherry_mx_1u_keycap.scad`: editable OpenSCAD source
- `cherry_mx_1u_agentpad.stl`: AgentPad circuit-A engraving, ready to slice
- `cherry_mx_1u_blank.stl`: unmarked version of the same keycap
- `agentpad_top_pattern.svg`: exact 2D artwork used for the relief
- `cherry_mx_fit_test.stl`: three socket clearances (0.00, 0.05, 0.10 mm)
- `agentpad_keyset_8.stl`: all eight workflow keys on one print bed
- `agentpad_keymap.svg`: top-view placement and legend reference
- `agentpad_sw1_task1.stl` ... `agentpad_sw6_task6.stl`: six task slots
- `agentpad_sw7_refactor.stl`: branching/refactor operation
- `agentpad_sw8_test.stl`: checked-test operation

The AgentPad mark uses 0.60 mm PCB-like traces, three annular pads, and a square
node that echoes the Rev.2 switch openings. It is recessed 0.45 mm into the
flat top so the caps can be printed face-down. Set `surface_pattern = "none"`
for a blank cap.

## Agent workflow layout

The eight-key set adapts the public AgentPad13 workflow to this board's physical
3 x 3 layout. The six numbered keys represent its six agent/task slots. The next
two official actions, Refactor and Test, occupy SW7 and SW8; the encoder remains
in the lower-right position.

| Physical row | Left | Centre | Right |
| --- | --- | --- | --- |
| Top | SW1 / Task 1 | SW2 / Task 2 | SW3 / Task 3 |
| Middle | SW4 / Task 4 | SW5 / Task 5 | SW6 / Task 6 |
| Bottom | SW7 / Refactor | SW8 / Test | Encoder |

The legends identify workflow roles, while the actual keycodes remain freely
assignable in QMK. In the source, use `surface_pattern = "task"` with
`task_number = 1..6`, or select `"refactor"`, `"test"`, `"agentpad"`, or
`"none"`.

## Recommended workflow

1. Print `cherry_mx_fit_test.stl` first with the same material, nozzle, layer
   height, and wall settings intended for the cap.
2. Let the part cool, then test each socket gently on a spare switch. Do not
   force it: an undersized socket can damage or pull apart a switch.
3. In the SCAD source, set `stem_clearance` to the best result. The default is
   0.05 mm per side.
4. Render with F6 and export STL from OpenSCAD.

## Creality / FDM starting settings

- Material: PLA or PLA+ for the first test; PETG also works but usually needs
  a little more clearance.
- Nozzle: 0.4 mm
- Layer height: 0.12-0.16 mm
- Line width: 0.4 mm
- Walls: 3 or 4
- Top/bottom layers: 5 or 6
- Infill: 15-25% (the model is mostly shell)
- Speed: 25-35 mm/s for the stem area
- Elephant-foot compensation: 0.15-0.25 mm if available

Print the keycaps face-down (`rotate X = 180 degrees`) without support. The flat
finger surface sits directly on the build plate; the shell and stem then grow
upward without internal supports. Avoid scaling the STL in the slicer because
that changes the MX socket fit; change the SCAD parameters instead.

The model is intended as a practical FDM starting point, not an injection-mould
drawing. Printer flow, material shrinkage, and first-layer squish can easily
shift a friction fit by 0.1 mm, which is why the fit coupon is included.

The stem boss outside diameter is 5.5 mm. This was reduced from the original
6.4 mm after the first physical Ender-3 V3 SE test: the cross fit was correct,
but the larger cylinder contacted the recessed switch housing before seating.
The boss starts at the skirt plane; when the cap is printed face-down it grows
from the top shell without support. Its smaller diameter provides clearance
inside the switch housing recess.

After the second physical test, the exterior wall was increased from 1.2 to
1.6 mm (four 0.4 mm lines) and the top from 1.6 to 2.0 mm. The top was changed
to a flat, engraved face specifically for build-plate-down surface quality.

After the eight-key physical print, the socket fitted but did not retain the
switch when inverted. The default per-side socket clearance was therefore
reduced from 0.10 to 0.05 mm. This makes both the total cross length and total
cross thickness 0.10 mm smaller while retaining the proven 5.5 mm boss outside
diameter.

For the verified `rmm4.local` USB connection, G-code transfer, monitoring, and
safety procedure, see [`docs/ENDER3_V3_SE_USB_PRINTING.md`](../../docs/ENDER3_V3_SE_USB_PRINTING.md).
