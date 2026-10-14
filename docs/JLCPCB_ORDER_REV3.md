# JLCPCB order settings

Use `manufacturing/agentpad_rev3_JLCPCB_panel.zip` as the upload file.

Recommended settings:
- Base material: FR-4
- Layers: 2
- PCB thickness: 1.6 mm
- Copper weight: 1 oz
- Surface finish: Lead-free HASL
- Min track/spacing used by design: 0.20 mm / KiCad DRC clearance 0.20 mm
- Board size: 62 x 62 mm
- Panel size: 140 x 80 mm
- Customer panelization: Yes (two functional boards + four breakout spacer parts)
- Cutting lines: fully connected closed profiles; fabricator CAM to add temporary retention tabs if required
- Different design count: expect JLCPCB to classify the upper/lower/spacer panel as multiple designs; accept the quoted surcharge if shown.
- Remove order number: optional

Assembly is intended to be hand-soldered. Do not order PCBA for Rev.3.

## Parts
- Waveshare RP2040-Zero-M (pre-soldered header) x1
- Kailh CPG151101S11 hot-swap sockets x6 (optional; bottom-side only; omit for direct solder)
- MX-compatible switches x6
- Alps EC11E-compatible push encoder x1

## Before payment
Inspect every layer in JLCPCB Gerber Viewer, especially:
1. Upper-plate 14x14 mm switch cutouts
2. Encoder 14 x 14 mm Rookey-style body opening
3. RP2040-Zero-M header holes and USB-C at top edge
4. Hotswap pads on B.Cu/B.Paste
5. Fully closed cutting lines in panel

## Mechanical fit and marking
- Install the RP2040-Zero-M above the lower PCB, with USB-C facing the top edge.
- Its pre-soldered 2.54 mm-pitch side headers fit the 1.0 mm plated holes.
- The module body and USB-C pass through the 20 x 25 mm top-edge notch and remain visible from above.
- Supplied FR4 spacers retain the nominal 6 mm MX switch-plate gap.
- `AGENTPAD REV3` is printed on the visible upper-plate F.Silkscreen.

## Silkscreen orientation and labels
- F.Silkscreen text reads normally from the front side.
- B.Silkscreen text is mirrored in the design data so it reads normally from the back side after fabrication.
- Minimum label height/stroke is 1 mm / 0.15 mm.
- The lower PCB identifies U1 header signals, SW1..SW6 nets/GND, and ENC1 terminals A/C/B/G/S.
- The upper plate identifies every switch opening and the encoder opening.
- In JLCPCB Gerber Viewer, inspect both `F_Silkscreen` and `B_Silkscreen` from their respective viewing sides before payment.

## MX switch mounting
- Each switch has two 1.5 mm plated through-holes connected to its input net and GND for direct soldering.
- Kailh hot-swap sockets must be placed on the B.Cu/B.Paste side. The footprint is not reversible.
- The board silkscreen identifies the direct-solder top side and Kailh-socket bottom side.
- Verify that all 12 switch electrical holes show annular copper rings and appear in the plated drill layer before ordering.

## Rounded exterior corners
- The lower circuit PCB and upper switch plate both use R2 mm exterior corners.
- The 14 x 14 mm switch and encoder openings remain dimensionally unchanged.
- The rectangular manufacturing-panel outer frame remains square.
