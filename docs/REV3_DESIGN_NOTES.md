# AgentPad Rev.3 design notes

## Rev.1 build feedback

- The Kailh CPG151101S11 hot-swap socket footprint is side-specific. A socket
  fitted from the component/top side is reversed and cannot accept the switch
  pins correctly.
- PCB artwork must be reviewed from the actual assembly side, especially when
  a bottom-layer footprint is shown mirrored in a board editor or Gerber
  viewer.
- The 68 x 80 mm Rev.1 board left substantial unused area for an eight-key
  workflow that was larger than needed in practice.

## Rev.3 response

- Product size is 62 x 62 mm, down from Rev.2's 62 x 80 mm. This reduces board
  area by 22.5% while preserving the 19.05 mm MX pitch.
- Six MX switches are arranged as a 3 x 2 grid. The RP2040-Zero-M and EC11
  encoder share the top control row.
- Every MX position has 1.5 mm plated holes for direct soldering from the top.
- Optional Kailh hot-swap pads remain on B.Cu/B.Paste and are bottom-side only.
- The lower PCB explicitly marks `MX DIRECT / TOP SIDE` on F.Silkscreen and
  `KAILH SOCKET / BOTTOM SIDE` on mirrored B.Silkscreen.

## Electrical mapping

- SW1..SW6: GP0..GP5, active low
- Encoder A/B: GP8/GP14
- Encoder push: GP15, active low
- Onboard RGB: GP16, reserved

## Verification status

- KiCad 9.0.8 lower PCB DRC: 0 violations, 0 unconnected items
- KiCad 9.0.8 upper PCB DRC: 0 violations, 0 unconnected items
- Generator geometry checks: PASS
- Rev.1 and Rev.2 generator regression checks: PASS

The Rev.3 electrical and manufacturing data are validated, but the new 62 x
62 mm mechanical arrangement has not yet been physically assembled. Before a
production quantity, order or fabricate one set and confirm switch, socket,
encoder, RP2040 header, USB access, and spacer fit.
