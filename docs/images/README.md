# Rev2 visualization images

- `rev2_kicad_top.png`: actual KiCad 9 rendering, front of the single PCB.
- `rev2_kicad_bottom.png`: actual KiCad rendering, viewed from the back; socket pads are on this side.
- `rev2_kicad_perspective.png`: actual KiCad rendering, angled view.
- `rev2_assembly_case_concept.png`: generated appearance concept showing assembly without a case, an ivory printed case, and a graphite printed case.

The KiCad images use `kicad/agentpad_rev2_single.kicad_pcb`. Component 3D models are not assigned, so these renders show the bare board. The concept uses the board rendering and `docs/rev2_assembly.svg` as layout references. It is not a CAD fit check: component shapes, keycaps, knob, enclosure dimensions and fasteners are illustrative. In particular, incidental holes in the concept image do not add mounting holes to the manufacturing PCB. The full enclosure has not been mechanically designed or fit-tested.

The actual board is 62 × 80 × 1.6 mm, with eight keys in a 3+3+2 arrangement, an encoder at bottom right, and an RP2040-Zero-M at the top. Hot-swap sockets mount underneath; switches insert from above. The KiCad renders are updated for the four Ø2.2 mm M2 corner holes, with centres 2.5 mm from the edges; the appearance concept predates these holes and is not their positional reference.

Example regeneration:

```sh
kicad-cli9 pcb render --width 1600 --height 1600 --quality high --background opaque --side top --output docs/images/rev2_kicad_top.png kicad/agentpad_rev2_single.kicad_pcb
```
