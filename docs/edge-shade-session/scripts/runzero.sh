#!/usr/bin/env bash
# edgeShade 0 (every preset) on each path, vs the n2_* files of the previous round
S=/tmp/claude-1000/-home-andrey--PROJECTS-watches/6b36e029-86b5-44da-bf6a-b636a5744698/scratchpad
cd /home/andrey/_PROJECTS/watches-edge-shade/firmware
run() { python3 tools/check_board_render.py $2 > $S/z_$1.txt 2>&1; if diff -q <(grep -v "^\s*$" $S/n2_$1.txt) $S/z_$1.txt >/dev/null; then echo "$1: identical to HEAD ($(tail -n 1 $S/z_$1.txt))"; else echo "$1: DIFFERS"; diff $S/n2_$1.txt $S/z_$1.txt | head -5; fi; }
run lcd "--board lcd316 --res 320w8-8"
run lcd_tiles "--board lcd316 --res 320w8-8 --tiles"
run lcd_tiles_push "--board lcd316 --res 320w8-8 --tiles --push-lens"
run 240f "--board lcd316 --res 240f"
run 240f_push "--board lcd316 --res 240f --push-lens"
run amoled "--board amoled191"
