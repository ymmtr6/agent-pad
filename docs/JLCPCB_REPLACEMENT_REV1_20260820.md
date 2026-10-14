# JLCPCB Rev.1 replacement data

Target engineer question: `13307549A-Y2`

Upload this file as the replacement Gerber archive:

`manufacturing/agentpad_rev1_JLCPCB_panel_replacement_20260820.zip`

## Scope of the correction

- Kept the ordered copper, solder-mask, paste, silkscreen, and plated-drill files byte-for-byte unchanged.
- Kept the 152 x 88 mm panel and the 68 x 80 mm functional-board dimensions unchanged.
- Replaced only `agentpad_rev1_panel-Edge_Cuts.gbr`.
- Replaced open profile gaps with explicitly closed 1.0 mm non-plated routing-slot contours.
- Retained 1.0 mm solid breakaway necks at the functional-board rails and spacer attachments.
- Kept all switch, encoder, spacer, and RP2040-Zero mechanical openings unchanged.

## Validation

- KiCad 9.0.8 standard DRC: lower PCB 0 violations / 0 unconnected; upper PCB 0 violations / 0 unconnected.
- Generator geometry checks: PASS.
- Edge-Cuts graph: 3,190 segments, 69 closed components, 0 odd-degree vertices, 0 duplicate segments.
- ZIP integrity test: PASS (8 files).
- SHA-256: `a05b737931f7c2b2b91be26eb0f3565407490a50452d79c1d24d802aeec00f14`

JLCPCB must still perform the final CAM/manufacturability approval after replacement upload.
