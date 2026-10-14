# AgentPad Rev1

QMK definition for the hand-soldered AgentPad Rev1 with a Waveshare
RP2040-Zero-M.

## Default test keymap

| Row | Left | Centre | Right |
| --- | --- | --- | --- |
| Top | F13 | F14 | F15 |
| Middle | F16 | F17 | F18 |
| Bottom | F19 | F20 | Encoder push: Mute |

The encoder sends volume down counter-clockwise and volume up clockwise.

## Wiring

- SW1..SW8: GP0..GP7, active-low direct pins
- Encoder A/B: GP8/GP14
- Encoder push: GP15, active-low direct pin
- RP2040-Zero onboard RGB: GP16 (not enabled in the initial test firmware)

To enter the ROM UF2 bootloader, press BOOT and RESET together, release RESET,
then release BOOT. Copy the compiled UF2 to the `RPI-RP2` drive.
