---
name: run-sim
description: Launch the Liquid Watch sim (Vite) headless and screenshot the panel in a given param state to verify a visual change. Use whenever a rendering question needs an actual frame rather than reasoning about code.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Running & screenshotting the sim

## 1. Dev server (port 5190, strictPort)

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5190/   # 200 → up, reuse
```
If not 200, from `sim/`: `npx vite > <scratchpad>/vite.log 2>&1 &` and wait for `Local:` in the log.
Leave it running.

## 2. State via URL params (`sim/src/main.ts`, "URL params" block)

`board=lcd316&res=320` canvas of another board (amoled191 default; lcd316 res 240/256/288/320; remembered in
localStorage, so pass `board=amoled191` to go back) · `fresh=1` ignore saved session · `preset=<id>` (ids in `PRESETS`, `sim/src/params.ts`; `<id>-big` = wide-rod twin) · `t=HH:MM` · `demo=N` · `settle=1` springs at rest ·
`along=` `across=` tilt · `scale=` · `cuff=0` no leather · `lens=` `leather=black` · `grid=1` ·
`p.<paramKey>=<value>` any param from `sim/src/params.ts` (colours URL-encoded: `%23ff0000`; bools `1`/`0`).

`window.sim = { params, hours, minutes, fb, overlay }` for `page.evaluate`.

## 3. Shoot

```bash
cd sim && node ../.claude/skills/run-sim/shot.mjs <scratchpad>/a.png "p.ticksOnTop=1&p.tickColorH=%23ff0000"
```
Screenshots `#viewport` (panel + cuff). Then Read the PNG and look at it. For pixel checks use
`page.evaluate(() => window.sim.fb[y*PANEL_W+x])` (RGB565; PANEL_W 536 on the AMOLED, 820 on lcd316@320) instead of eyeballing.

Headless render without a browser (exact framebuffer, used by compare-device.py): `sim/tools/render-ref.ts`.
