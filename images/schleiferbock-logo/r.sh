#!/bin/bash
# render svg -> png via headless chrome: r.sh in.svg out.png [w h]
w=${3:-960}; h=${4:-560}
printf '<html><body style="margin:0;background:#fff"><img src="file://%s" style="width:%spx;height:%spx;object-fit:contain"></body></html>' "$(realpath $1)" $w $h > /tmp/claude-1000/-home-andrey--PROJECTS-watches/cd8f96fd-598b-46a9-85b6-7f9763d6a8a5/scratchpad/sb/_v.html
google-chrome --headless=new --disable-gpu --no-sandbox --allow-file-access-from-files --screenshot=$(realpath -m $2) --window-size=$w,$h file:///tmp/claude-1000/-home-andrey--PROJECTS-watches/cd8f96fd-598b-46a9-85b6-7f9763d6a8a5/scratchpad/sb/_v.html 2>/dev/null >/dev/null
