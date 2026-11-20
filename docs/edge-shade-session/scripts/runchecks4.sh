#!/usr/bin/env bash
# runchecks.sh <dir> : check_board_render over the look dir on every path
D=$(realpath "$1")
cd /home/andrey/_PROJECTS/watches-edge-shade/firmware
for cfg in "--board lcd316 --res 320w8-8" "--board lcd316 --res 320w8-8 --tiles" "--board lcd316 --res 320w8-8 --tiles --push-lens" "--board lcd316 --res 320w8-8 --push-lens" "--board lcd316 --res 240f" "--board lcd316 --res 240f --push-lens" "--board amoled191"; do
  echo "== $cfg"; python3 tools/check_board_render.py $cfg $D/*.json 2>&1 | grep -v " 0 px off" | sed "s|.*/shade4/||"
done
