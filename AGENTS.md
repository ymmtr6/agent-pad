# Repository Guidelines

## Project Structure & Module Organization

AgentPad combines PCB, mechanical, and firmware sources. Editable KiCad boards and the local footprint library live in `kicad/`. Generator scripts are in `scripts/`; `generate_agentpad_rev1.py` contains the shared implementation, while `generate_agentpad_rev2.py` selects the Rev2 single-PCB settings. QMK keyboard definitions are under `firmware/qmk/keyboards/agent_pad/<revision>/`. Mechanical models, printable keycaps, and OpenSCAD sources belong in `cad/`.

Treat `gerber/`, `manufacturing/`, `docs/drc/`, manifests, and packaged UF2 files as generated or release artifacts. Keep revision-specific names consistent, for example `agentpad_rev2_single.kicad_pcb` and `VALIDATION_REV2.md`.

## Build, Test, and Development Commands

Create a virtual environment and install the geometry dependency:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Regenerate a revision into a disposable local directory (the default output path is `/mnt/data`):

```sh
AGENTPAD_OUT=/tmp/agentpad_rev2_single_build .venv/bin/python scripts/generate_agentpad_rev2.py
```

Run KiCad 9 design-rule checks:

```sh
scripts/run_kicad_drc.sh rev2
```

For firmware, copy the desired revision directory into an official QMK checkout, then run `make agent_pad/rev2:default` (or `rev2:via`, `rev1:default`). See `firmware/readme.md` for the complete copy and flashing workflow.

## Coding Style & Naming Conventions

Use four-space indentation in Python and C, UTF-8, and POSIX-compatible shell for scripts. Follow existing Python naming: `UPPER_CASE` for geometry constants, `snake_case` for functions and variables, and `Path` objects for filesystem work. Preserve QMK’s conventional `config.h`, `keyboard.json`, `keymap.c`, and `rules.mk` layout. Do not hand-edit generated Gerbers or ZIP archives; change their source or generator instead.

## Testing Guidelines

There is no unit-test suite. A hardware change is complete only when generator geometry checks and KiCad DRC both report `PASS`. Inspect the generated validation report and Gerber layers visually, especially edge cuts, mask openings, drills, and panel profiles. Firmware changes should pass QMK lint and compile for every affected revision.

## Commit & Pull Request Guidelines

Use short, imperative commit subjects such as `Fix Rev2 encoder clearance`. Keep commits scoped to one revision or subsystem. Pull requests should explain the physical or electrical impact, list validation commands and results, link relevant issues, and include KiCad or Gerber screenshots for layout changes. Call out regenerated artifacts and any fabrication-setting changes explicitly.
