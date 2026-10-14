#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
revision=${1:-rev1}
case "$revision" in
    rev1|rev2|rev3) ;;
    *) echo "usage: $0 [rev1|rev2|rev3]" >&2; exit 2 ;;
esac
slug="agentpad_${revision}"
if [ -n "${KICAD_CLI:-}" ]; then
    kicad_cli=$KICAD_CLI
elif command -v kicad-cli9 >/dev/null 2>&1; then
    kicad_cli=$(command -v kicad-cli9)
else
    kicad_cli=$(command -v kicad-cli)
fi

mkdir -p "$project_root/docs/drc"
board_names='lower upper'
if [ "$revision" = rev2 ] && [ -f "$project_root/kicad/agentpad_rev2_single.kicad_pcb" ]; then
    board_names='single'
fi
for board_name in $board_names; do
    "$kicad_cli" pcb drc \
        --severity-all \
        --units mm \
        --format json \
        --exit-code-violations \
        --output "$project_root/docs/drc/${slug}_${board_name}-drc.json" \
        "$project_root/kicad/${slug}_${board_name}.kicad_pcb"
done
