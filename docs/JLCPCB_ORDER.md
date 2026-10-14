# JLCPCB order settings

Use `manufacturing/agentpad_rev1_JLCPCB_panel.zip` as the upload file.

Recommended settings:
- Base material: FR-4
- Layers: 2
- PCB thickness: 1.6 mm
- Copper weight: 1 oz
- Surface finish: Lead-free HASL
- Min track/spacing used by design: 0.20 mm / KiCad DRC clearance 0.20 mm
- Board size: 68 x 80 mm
- Panel size: 152 x 88 mm
- Customer panelization: Yes (two functional boards + four breakout spacer parts)
- Breakaway tabs: 1 mm solid routed tabs (no mouse-bite drill file)
- Different design count: expect JLCPCB to classify the upper/lower/spacer panel as multiple designs; accept the quoted surcharge if shown.
- Remove order number: optional

Assembly is intended to be hand-soldered. Do not order PCBA for Rev.1.

## Parts
- Waveshare RP2040-Zero-M (pre-soldered header) x1
- Kailh CPG151101S11 MX hot-swap socket x8
- MX-compatible switches x8
- Alps EC11E-compatible push encoder x1

## Before payment
Inspect every layer in JLCPCB Gerber Viewer, especially:
1. Upper-plate 14x14 mm switch cutouts
2. Encoder 7.5 mm shaft opening
3. RP2040-Zero-M header holes and USB-C at top edge
4. Hotswap pads on B.Cu/B.Paste
5. Solid routed breakaway tabs in panel

## Mechanical fit and marking
- Install the RP2040-Zero-M above the lower PCB, with USB-C facing the top edge.
- Its pre-soldered 2.54 mm-pitch side headers fit the 1.0 mm plated holes.
- The module body and USB-C pass through the 20 x 25 mm top-edge notch and remain visible from above.
- Supplied FR4 spacers retain the nominal 6 mm MX switch-plate gap.
- `AGENTPAD REV1` is printed to the left of the module on the visible upper-plate F.Silkscreen.
