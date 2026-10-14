# AgentPad Rev.3 validation report

KiCad standard DRC result: **PASS**

- KiCad CLI version: 9.0.8
- Lower PCB: 0 violations, 0 unconnected items
- Upper PCB: 0 violations, 0 unconnected items

## Panel profile design
- Individual board: 62 x 62 mm
- Manufacturing panel: 140 x 80 mm
- Fabricator replacement mode: every board/spacer cutting line is a fully connected closed loop
- No intentional cutting-line gaps remain; production retention is left to fabricator CAM

## RP2040-Zero-M mechanical fit
- Module envelope: 18 x 23.5 mm, entirely within the lower PCB outline
- Pre-soldered side headers use 1.0 mm plated holes on 2.54 mm pitch
- Module is installed above the lower PCB and visible through a 20 x 25 mm upper-plate notch
- Supplied FR4 spacers preserve the nominal 6.0 mm switch-plate gap while the module passes through the notch
- Upper-plate front marking: AGENTPAD REV3 on F.Silkscreen

## Rev.3 compact six-key layout
- Six MX switches use a 3 x 2 grid at the unchanged 19.05 mm pitch
- The RP2040-Zero-M and EC11 share the top row
- Assembled height reduced from 80 mm to 62 mm (22.5%); width remains 62 mm
- Lower and upper functional-board exterior corners use R2 mm
- Encoder opening remains a Rookey-style 14 x 14 mm square

## Rev.3 MX switch mounting and side identification
- Two electrical pins per switch use 1.5 mm plated holes with 2.2 mm pads
- PTH pad 1 connects to K1..K6; PTH pad 2 connects to GND
- Kailh hot-swap sockets mount on the bottom side only
- F.Silkscreen says MX DIRECT / TOP SIDE; B.Silkscreen says KAILH SOCKET / BOTTOM SIDE
- Direct-solder MX switches may instead be installed from the top side

Generator geometry checks: **PASS**

## Supplemental checks passed
- Board and cutout containment
- Route board containment
- Same-layer route clearance heuristic >= 0.20 mm
- Switch cutout non-overlap
- RP2040-Zero body envelope fit
- Panel drill and route file generation
- No overlapping F.Mask/B.Mask apertures
- No duplicate PTH coordinates; minimum PTH drill-edge spacing 1.203 mm
- Gerber and Excellon X2 file-function attributes present

## Warnings
- EC11 footprint follows KiCad/Alps EC11E geometry; confirm your purchased encoder is EC11E-compatible before soldering.
- Panel is customer-panelized. JLCPCB may apply panelization/special-board charges depending on order options.
