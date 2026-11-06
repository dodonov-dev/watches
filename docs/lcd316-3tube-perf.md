# LCD-3.16, three tubes 10-8-6 mm: 25 -> 30+ fps

Goal: `lcd316@320w10-8-6+t3` with the user's look `firmware/bench/lcd-1105.json` (read off the board 2026-11-05:
subtle-soda variant, purple, vertical, fizzCount 240) at **>= 30 fps** in use (live IMU), pinned bench above that.
The user allows for this task: memory made dynamic again where needed, free internal heap down to ~0.

**State 2026-11-06 (committed):** 80 MHz, pinned 40.7 / swinging 27.6 fps (baseline 31.5 / 22.9). The user accepts ~27
for now; 120 MHz (48.5 / 31.8) is shelved until its reset wedges are understood (BACKLOG "Firmware / ESP-IDF").

## Baseline (2026-11-05, live `f`, board in use)
fps 25.3, render 37.8 ms (cores h 21.9 / m 24.15, of it seconds 10.6), push 23.55 ms (three strips), frame-p95 43,
phys 1.98 x (0.26 + 0.28), rest 0.95; heap with BLE 96 B.
Schedule (main.cpp renderBoth, staggered): core 0 = fizz h + render h + push h (~31.7); core 1 = push m + s of the last
frame + fizz m + render m + fizz s + render s (~37.8, critical). Work 46 ms render + 23.5 push over two cores: balance
alone caps at ~35 ms (28.5 fps).

## Levers (ideas round: Astra, Sol-6.1, Fable; ranked by agreement)
1. Push: hash each finished tile at render time (internal RAM), push gathers + stores only changed (pair, segment)
   units (KAIZEN structural 2). Exact. All three reviewers; Fable estimates push 23.5 -> 13-15 ms. Effort L.
2. Schedule: swap pushes between cores (core 0: render h, then push m + s; core 1: push h, render m, render s) with
   double-buffered strips (+3 x ~177 KB PSRAM) and the gather lane by pushing core; or push part of seconds on core 0.
   Exact. Enabler for a ~30 / 30 split once 1 lands. Effort M.
3. Config: 32 KB I-cache (+16 KB internal), funded by NimBLE host heap in PSRAM (-DCONFIG_BT_NIMBLE_MEM_ALLOC_MODE_EXTERNAL,
   MAX_CONNECTIONS 1) and/or PushSlots to PSRAM (Fable: strided access, may cost ~1 ms); libs at -O2
   (CONFIG_COMPILER_OPTIMIZATION_PERF). One lib rebuild (~10 min).
4. Seconds Tube internal (~16 KB, hot per-row arrays), once internal RAM is freed.
5. Bounce refill by GDMA instead of the ISR memcpy + D-cache preload (own idea, not in the reviews): frees the refill's
   share of core 0 (measure: `f` scan-isr %, counted since 2026-11-05) and stops 26 KB/ms of fbuf streaming through
   the shared 64 KB D-cache. Needs fbuf written back after each push block (DMA reads PSRAM). Risk: twitch if the DMA
   falls behind (refill monitor).
6. 64-B RX bursts for tile copies (pitched strip rows 1,664 B). Exact. Effort M.
7. Physics on core 0 at frame start (whichever core is lighter after 2).
8. PSRAM 120 MHz: needs flash 120 MHz too (F4R8 table), experimental, temperature-dependent: last, only with a soak.

## Log
### 2026-11-05 A/B, same session (COM7, lcd-1105 pinned + fix-pose, 2 runs; swing = swing.py 30 s '-1,0>0.6,0@3')
| build | pinned fps | render | cores h / m (m incl. s) | push | scan-isr | swing fps | heap (BLE up) |
|---|---|---|---|---|---|---|---|
| b0 HEAD (+ counters) | 31.5 | 30.90 | 19.15 / 22.41 | 14.57 | 8.2 % | 22.9 | 216 B |
| c1 + I-cache 32 KB, NimBLE heap PSRAM (1 conn), libs -O2 | 34.3 | 28.45 | 19.91 / 20.33 | 14.44 | 8.0 % | 24.8 | 3.4 KB |
| c2 c1 + pushes swapped between cores, strips x2 | 34.4 | 28.28 | 19.03 / 21.90 | 14.36 | 8.0 % | 26.0 | 3.6 KB |
| c3 c2 + -DREFILL_DMA=1 (GDMA bounce refill) | 35.5 | 27.45 | 15.94 / 19.21 | 18.24 | 2.3 % | 25.7 | 2.5 KB |
- Refills: all OK (late 0); c3 worst 70 % of the deadline (memcpy refill 5-12 %).
- c3: renders ~-3 ms h / -2.7 ms m (no fbuf streaming through the D-cache), but push +4-5 ms: gather-wait 4.9 -> 8.2 ms
  (the refill DMA at priority 5 ahead of the gathers / tile copies on PSRAM) and ~2 ms of fb_writeback (esp_cache_msync
  walks 64 scan lines a block). Kept as an option (default off) until the push stops gathering unchanged units (lever 1).
- Profile, pinned (c1, TUBE_PROF + PUSH_PROF): hours 18.5 ms = digits 4.5, body 2.6, fizz 2.5, labels 2.2, band 1.9, ticks
  1.7, back 0.8, tile 0.8, trrows 0.7; minutes 10.5; seconds 9.8 (digits 2.5, labels 1.4). Push 13.9 = gather-wait 6.2,
  hash 3.7, store 2.5 (+ setup).
- Profile, swinging (c2): frame ~40 ms; render h 21.5-22.5, m 15, s 14.2; push ~17 (hash 3.8, store 6.5-9, gather 3.7-4.8;
  changed segments 25-30 %, i.e. ~70 % still skippable); physics 2 steps x 1.1-1.3 ms tube step (serial before the
  renders); residue rows (trrows) h 3.6 / m 4.2 / s 2.3 ms; palette rebuilds 1.4 / 0.75 / 0.8; fizz 3-4 / 1.1 / 2.5-2.9.
  Work ~71 ms over two cores: 30 fps swinging needs ~10 ms less work plus balance.
### 2026-11-05 BLE window + fast mode (user's design)
- Every boot opens a BLE window (ble.h BLE_WINDOW_S 180 without a central, BLE_GRACE_S 15 after a disconnect), then the
  board reboots into fast mode: BLE off, Arduino releases the BT controller memory at boot (strong bleInUse() from a
  one-shot RTC flag). Serial: `B0` fast now, `B1` window now, `B` the mode; `s` ends with `temp <C> ble on|off`.
- Static RAM without BLE: -10.4 KB (NimBLE statics) + the controller's ~36 KB + BLE's runtime allocations (to measure).
- Fast mode puts the shared fizz masks (8 KB) and the seconds Tube (~16 KB) in internal RAM (render_init(true)); the
  window keeps both in PSRAM (frees 8 KB vs before: the PSRAM timing task's 5 KB stack must fit with BLE up).
- bench.py switches a board in its window to fast mode first (`B0`; --ble-window benches the window).
- 120 MHz retuning (CONFIG_SPIRAM_TIMING_TUNING_POINT_VIA_TEMPERATURE_SENSOR) only starts for flash vendors 0xC8 / 0x20;
  any other aborts the boot (ESP_SYSTEM_INIT_FN error): read the flash ID first (esptool flash-id).
- Host: check_render_frames.py needs TMPDIR inside the scratchpad here (sandbox /tmp loses dirs); vs HEAD byte-identical.

### 2026-11-05 lever 1: push by the render's change records (worktree watches-wt-l1)
- Render (render.cpp): per finished tile, per column pair, a 32-bit hash of its 4 words (x K1, ^ >> 16, x K2 per word)
  against the tube's last render (table 31 x 410 per tube, PSRAM); changed pairs -> TileDirty bits[tile][13] per strip
  buffer (PSRAM), with tube, renderSeq, rows, valid (= last render hashed the same rows; stripLens renders: none).
- Push (display_lcd316.cpp turn_segs_rec): when the slot last pushed renderSeq - 1 of the same tube, known, same rows
  and the same strip offsets (lens map), a unit (64 columns x segment) is gathered only if a pair of it is marked in a
  tile its rows read (narrowed to first..last marked pair), and only marked pairs are stored; one rotating unit a push
  is compared whole (collision repair, ~2 s). Else the hash push as before (forced after a by-record push).
- Host: check_render_frames --tiles and check_fizz_steps --tiles (amoled, lcd 3-tube --fma) identical; records ==
  changed units over 13,136 scenes and 80 presets x 1,050 frames (0 missed, 0 extra). Board -DPUSH_VERIFY: bad 0 of
  478 M px (pinned, swinging, tubeHeight 60 and back, `x`).

Builds: rec = the above; rec2 = tighter hash loop; rec3 = + gathered / stored rows narrowed to the tiles with marks.
Same session, alternating (bench.py --preset lcd-1105 --fix-pose --runs 2; swing.py 60 s '-1,0>0.6,0@3'):

| build | pinned fps | render | cores h / m | push | swing fps | swing push |
|---|---|---|---|---|---|---|
| base (worktree before) | 44.0 44.2 44.0 44.5 44.3 | 22.5 | 15.3 / 17.4 | 10.1-10.4 | 29.9 29.9 29.2 29.3 29.3 | 11.6-11.9 |
| rec | 46.2 46.0 | 21.6 | 16.9 / 19.7 | 3.7-3.9 | 29.4 29.6 | 7.3-7.5 |
| rec2 | 46.5 46.0 46.2 | 21.5 | 16.6 / 19.8 | 3.7-4.0 | 29.5 29.0 29.0 | 7.3-7.6 |
| rec3 | 46.4 46.5 | 21.4 | 16.8 / 20.1 | 2.86 | 29.3 29.1 | 6.6-6.8 |

PUSH_PROF, us a frame summed over the 3 strips (pinned / steady swing): base hash 3650 / 3650, gather-wait 3300 / 1700,
store 2100 / 5600; rec3 pick 180 / 190, gather-wait 380 / 600, store 1900 / 5800 (units 32 / 66 of ~150). Swinging the
renders cost h 19.4 -> 21.6, m + s 27.0 -> 29.9 ms (pinned +1.5 / +2.5): the tile hashes take what the push saves.
Heap (`s`) boot 440-600 B vs 504-668, after a swing 190-360 vs 256-400; static +64 B. X sequence identical (350 frames).

### 2026-11-05 merged (BLE window + fast mode, lever B, lever 1), 120 MHz, same session
| build | pinned fps | render | cores h / m | push | swing fps (60 s) | swing push | heap |
|---|---|---|---|---|---|---|---|
| d2 (swap + physics on core 0) | 44.3 | 22.44 | 15.12 / 17.46 | 10.25 | 29.2 | 11.64 | 504 B (BLE up) |
| f0 merged, fast mode | 48.8 | 20.41 | 16.18 / 19.21 | 2.65 | 32.3 | 6.31 | window 9.3 KB |
- The window's boot heap is 9.3 KB (fizz masks in PSRAM there); bench.py switched to fast mode via B0 (`s`: `ble off`).
- f1 (all three pushes on core 0: physics + hours + pushes vs minutes + seconds) loses swinging: same session f0 32.8 /
  f1 30.8 fps (cores h 21.8 / m 26.0 both; core 0 becomes the long side). Kept f0's swap. Retuning task (g1) 31.4, then
  the chip wedged (KAIZEN): left off.
- Lever B alone (worktree base vs base + lever B, alternating twice): pinned 44.25 -> 45.2, swing 29.85 -> 31.45.
  -DTUBE_VERIFY of the final tree through a 60 s swing: tube-verify bad 0 (zone 332 M px, palette, band rows, trace
  memo, ramps). Host: check_render_frames (plain, --tiles) and check_fizz_steps (lcd316 320w10-8-6, 3 tubes, --tiles
  --fma, 80 presets) identical to HEAD.
- BLE on the board: window -> bleak connect (MTU 247, heap 9.0 KB connected) -> disconnect -> fast mode 15 s later; fast
  mode heap 24.9 KB with the seconds tube + fizz masks internal.

### Wedges at 120 MHz (open; investigate before any further 120 MHz A/B)
- Three hangs, all at flash + PSRAM 120 MHz, all around a reset: the GDMA-refill build at boot; g1 (retuning task) after a
  bench; h1-120 at bench.py's `B0` (esp_restart into fast mode). Never in steady running (h1 ran for hours); none at
  80 MHz so far. Symptom: no serial at all, esptool's USB-JTAG reset into download fails ("No serial data received");
  BOOT + RST reaches download mode (flashing works), the app only starts after a power-on (replug).
- Plan: (1) reboot loops (tools/rloop.py `r` x N, `B0` / `B1` loops, esptool resets) at 80 vs 120 MHz to get a rate;
  (2) when wedged, attach OpenOCD over the S3's built-in USB-JTAG (pio tool-openocd-esp32; Windows needs the WinUSB
  driver on the JTAG interface, or usbipd into WSL + udev rules) and halt both cores: PC / backtrace says where it
  hangs (ROM flash boot, 2nd-stage bootloader, app MSPI timing tuning, esp_restart_noos with a cache / GDMA access);
  (3) suspects: flash HPM (CONFIG_SPI_FLASH_HPM_ON) left on across a reset, MSPI 120 MHz timing tuning at boot,
  GDMA PSRAM traffic during esp_restart (tile channels have no shutdown handler, only the refill preload has).
- Final tree (h1) at 80 MHz (libs rebuilt: board_build.f_flash alone does not trigger the libs' rebuild, a
  custom_sdkconfig change does): pinned 40.7 fps (render 24.45, cores h 18.6 / m 22.3), swing 27.6 (push 9.1); 30 / 30
  `r` reboots kept (rloop.py). At 120 MHz: 48.5 / 31.8, but the reset wedges above.
