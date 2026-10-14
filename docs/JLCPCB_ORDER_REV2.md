# AgentPad Rev2 single-PCB order

Upload **`manufacturing/agentpad_rev2_single_gerber.zip`**.
Do not upload the old Rev2 panel, upper-plate, or complete archives: those contain the superseded split-board design.

- Single PCB: 62 × 80 mm, 2 layers, FR4, 1.6 mm, 1 oz copper.
- No customer panelization, no FR4 switch plate, no breakout spacers.
- Copper clearance: 0.20 mm; minimum track width: 0.20 mm.
- Include both PTH and NPTH drill files; do not convert socket holes to plated holes.
- Four corner mounting holes: Ø2.2 mm NPTH for M2, centres 2.5 mm from each adjacent edge. No countersinks.
- Hand assembly: eight Kailh CPG151101S11 sockets on the bottom, eight MX switches inserted from the top, RP2040-Zero-M and EC11 on top.

Before ordering, inspect both copper layers, both masks, bottom paste, and Edge.Cuts. The outer profile must be one 62 × 80 mm board. Each switch must have two Ø3 mm unplated socket holes, one centre hole, two locating holes, and two bottom SMD pads. There must be no Ø1.5 mm direct-solder switch pads.

See [assembly and enclosure interfaces](REV2_SINGLE_PCB.md) and [validation](VALIDATION_REV2.md). This is an electrically checked prototype; physical socket and printed-enclosure fit still require verification.
