# AgentPad QMK firmware

The QMK keyboard definition for the hand-soldered AgentPad Rev1 is located at
`firmware/qmk/keyboards/agent_pad/rev1`.

## Rev1 wiring

- Direct GPIOs: GP0..GP7 = SW1..SW8
- Encoder: GP8 = A, GP14 = B, GP15 = push
- All switch inputs are active-low with internal pull-ups
- On-board RP2040-Zero RGB is GPIO16 (not enabled in the initial test firmware)

## Initial test keymap

| Row | Left | Centre | Right |
| --- | --- | --- | --- |
| Top | SW1 / F13 | SW2 / F14 | SW3 / F15 |
| Middle | SW4 / F16 | SW5 / F17 | SW6 / F18 |
| Bottom | SW7 / F19 | SW8 / F20 | Encoder push / Mute |

Encoder rotation sends volume down counter-clockwise and volume up clockwise.

## Build

Copy the keyboard folder into an official QMK Firmware checkout, then build:

```sh
rsync -a firmware/qmk/keyboards/agent_pad/rev1/ \
  /path/to/qmk_firmware/keyboards/agent_pad/rev1/
cd /path/to/qmk_firmware
make agent_pad/rev1:default
```

The checked-in build is `firmware/build/agent_pad_rev1_default.uf2`.

Validated on 2026-09-02 with QMK 0.34.0 and arm-none-eabi-gcc 15.2.0:

- QMK lint: PASS
- Compile, link, and UF2 creation: PASS
- UF2 family: Raspberry Pi RP2040
- Size: 53 KiB / 106 UF2 blocks
- SHA-256: `2c22a893fb3af80ee74dcc6596df1a106e9559bc31c3eabb5c4f08920287cf3a`

## Flash

1. Connect the RP2040-Zero with a data-capable USB-C cable.
2. Press BOOT and RESET together, release RESET, then release BOOT.
3. Confirm that the `RPI-RP2` volume appears.
4. Copy `agent_pad_rev1_default.uf2` to that volume.
5. The volume disappears and the board restarts as `AgentPad Rev1`.

The firmware also enables RP2040 double-tap reset, so two quick presses of the
physical RESET button can reopen the UF2 bootloader for later updates.

The first physical flash was verified on macOS as USB VID/PID `0xFEED/0xA901`
with both keyboard and consumer-control HID interfaces registered.

## Rev2

Rev2 (single PCB, bottom-side Kailh hot-swap sockets) keeps the Rev1 wiring and
key layout. Its definition is `firmware/qmk/keyboards/agent_pad/rev2` and the
checked-in build is `firmware/build/agent_pad_rev2_default.uf2`.

Validated on 2026-10-09 with the `ghcr.io/qmk/qmk_cli` Docker image and QMK
master:

- QMK lint: PASS
- Compile, link, and UF2 creation: PASS
- SHA-256: `81f3bcbb91c6349296e8e57d9f81971c2d2ad7daab77aa22dd03fb3ad4fa56be`
- Physical flash on macOS: enumerates as `AgentPad Rev2`, VID/PID `0x4150/0xA902` (VIA rejects `0xFEED`)
- All 8 keys, encoder push, and encoder rotation verified on the assembled board

macOS maps F14/F15 to display brightness by default. Disable those shortcuts in
System Settings > Keyboard > Keyboard Shortcuts > Display, or remap the keys.

### Rev2 VIA

`keymaps/via` enables VIA and Mouse Keys (`firmware/build/agent_pad_rev2_via.uf2`,
SHA-256 `9393e35c63271723038eaf9c6ea85537d72f1e23804396a3553942a368292ba6`,
built on 2026-10-15 with QMK master `7a1bbf37`). QMK lint
rejects keymaps named `via` in the upstream tree; lint the keyboard with
`-km default` and build with `make agent_pad/rev2:via`.

1. Open https://usevia.app in Chrome or Edge.
2. Settings: enable "Show Design tab".
3. Design: "Load Draft Definition" and select `firmware/via/agentpad_rev2.json`.
4. Configure: "Authorize device" and select `AgentPad Rev2`.
