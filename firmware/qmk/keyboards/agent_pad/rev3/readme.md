# AgentPad Rev3

QMK definition for the compact six-key AgentPad Rev3 with a Waveshare
RP2040-Zero-M and push encoder.

## Default test keymap

| Row | Left | Centre | Right |
| --- | --- | --- | --- |
| Top controls | RP2040-Zero-M | — | Encoder push: Mute |
| Key row 1 | F13 | F14 | F15 |
| Key row 2 | F16 | F17 | F18 |

The encoder sends volume down counter-clockwise and volume up clockwise.

## Wiring

- SW1..SW6: GP0..GP5, active-low direct pins
- Encoder A/B: GP8/GP14
- Encoder push: GP15, active-low direct pin
- RP2040-Zero onboard RGB: GP16 (not enabled in the initial test firmware)

Kailh hot-swap sockets are installed on the PCB bottom side only. The bottom
silkscreen reads `KAILH SOCKET / BOTTOM SIDE`; direct-solder switches enter
from the top side marked `MX DIRECT / TOP SIDE`.
