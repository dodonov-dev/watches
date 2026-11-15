#!/usr/bin/env bash
# One photoreal concept render with the Codex CLI's image generation.
#   codex-render.sh <out.png> <prompt.txt> <image> [<image> ...]
# The images are copied into a scratch folder (Codex's workspace) and attached; the prompt refers to them by file
# name. One image per call. A render takes 1-3 min: run it in the background, several in parallel are fine.
set -uo pipefail
out=$(realpath -m "$1"); prompt_file=$2; shift 2
work=$(mktemp -d "${TMPDIR:-/tmp}/codex-render.XXXXXX")
args=()
for f in "$@"; do cp "$f" "$work/"; args+=(-i "$work/$(basename "$f")"); done
prompt="$(cat "$prompt_file")

Use your image generation tool. Save the image as $work/render.png. Do not create any other files and do not run anything else. Reply with the saved path and, in two lines at most, anything that deviates from the brief."
codex exec -s workspace-write --skip-git-repo-check -C "$work" -c 'model_reasoning_effort="medium"' \
  -o "$work/last.txt" "${args[@]}" -- "$prompt" </dev/null >"$work/run.log" 2>&1
code=$?
[ -f "$work/render.png" ] && mkdir -p "$(dirname "$out")" && cp "$work/render.png" "$out"
echo "exit=$code"; cat "$work/last.txt" 2>/dev/null; echo; ls -la "$out" 2>&1; echo "log: $work/run.log"
