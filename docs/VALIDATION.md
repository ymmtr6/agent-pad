# AgentPad Rev.1 validation report

KiCad standard DRC result: **PASS**

- KiCad CLI version: 9.0.8
- Lower PCB: 0 violations, 0 unconnected items
- Upper PCB: 0 violations, 0 unconnected items

## Compact breakaway design
- Individual board: 68 x 80 mm
- Manufacturing panel: 152 x 88 mm
- Board tabs: 1 mm solid routed necks; no NPTH drill layer
- Board outline is routed except at the 1 mm solid tabs for hand separation

## RP2040-Zero-M mechanical fit
- Module envelope: 18 x 23.5 mm, entirely within the lower PCB outline
- Pre-soldered side headers use 1.0 mm plated holes on 2.54 mm pitch
- Module is installed above the lower PCB and visible through a 20 x 25 mm upper-plate notch
- Supplied FR4 spacers preserve the nominal 6.0 mm switch-plate gap while the module passes through the notch
- Upper-plate front marking: AGENTPAD REV1 on F.Silkscreen

Generator geometry checks: **PASS**

## Supplemental checks passed
- Board and cutout containment
- Route board containment
- Same-layer route clearance heuristic >= 0.20 mm
- Switch cutout non-overlap
- RP2040-Zero body envelope fit
- Panel drill and route file generation
- No overlapping F.Mask/B.Mask apertures
- No duplicate PTH coordinates; minimum PTH drill-edge spacing 1.400 mm
- Gerber and Excellon X2 file-function attributes present

## Warnings
- EC11 footprint follows KiCad/Alps EC11E geometry; confirm your purchased encoder is EC11E-compatible before soldering.
- Panel is customer-panelized. JLCPCB may apply panelization/special-board charges depending on order options.
