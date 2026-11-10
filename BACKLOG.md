# BACKLOG
*todos and nice-to-haves*

## Power Management

- find out levels of sleep and how much they differ
- create extra playground firmware for measuring power consumption
- measure components in various conditions (e.g. display by itself without updates, with max/min brightness)

## BLE
- review/polish (was one-shoted)
- ensure webpage works even when we are already connected
- tests
- running BLE symbol when connecting, fixed when connected -
probably another "digit" in the same font

## UX
- taps for control: turning ble/wifi on
- taps for control: setting time?

## UI
- if we are ever able to measure pulse - end of liquid pumping as pulse
- different warping of glass and of liquid from glass for digits/ticks lying at the bottom
- work on bubble(s) realism, useless now
- surface lean on tilt should depend on the tube's inner width (narrow 6 mm vs wide 8 mm lens): keep capillarity
stronger than real life, but the curvature / angle a tilt gives should scale with the width, not be one preset
number (now angleTiltGain / angleMax; vertical mode uses the real tilt up to 45°)

## General
- Connection over Wi-Fi? How? Strich/QR displayed?
- App? Or just BLE/Wi-Fi?
- Softened metall ball to fill weight shift when tilting
- Trim presets and bench looks heavily: store only what differs from the defaults, so a behaviour change stays
  code-only (removing digitParallax touched 103 preset / bench files)
- Rear-digit view-angle parallax (live 2026-11-06, latched swinging gate; swings within 0.4 fps of no motion): the sub-pixel cost
  while it glides on a slow tilt is left (ramp bench 25.5 vs 33.8 fps: render cores +7-14 ms), plus ~0.7 fps pinned (code layout)

## Firmware / ESP-IDF
- LCD flash + PSRAM 120 MHz: +25 % fps (3 tubes swinging 27.6 -> 31.8), but the chip wedged at resets (esp_restart,
  esptool reset, one boot): reproduce with reboot loops, halt the wedged chip over USB-JTAG (OpenOCD) to see where it
  hangs; fix or report upstream (docs/lcd316-3tube-perf.md "Wedges at 120 MHz", KAIZEN 2026-11-05)
- Hang 1 (rear-parallax round-2, 80 MHz, 2026-11-06) **parked: not reproduced** (H1.4 2026-11-09: reconstructed round-2 tree + DIGIT_VERIFY, bench + 60 s swing, render0 492 B free, digit-verify 0 bad of 109 M px, the closing esptool reset clean; no coredump from it, E0). The hang diagnostics (src/diag.cpp: RTC boot record, panic breadcrumb, cached coredump summary, `v` / `C`) are in the production LCD build and will record it if it recurs; -DLOOP_WDT and -DSTACK_GUARD=1152 stay opt-in (docs/hang-investigation-plan.md).
- ESP-IDF upstream issue: esp_restart_noos (IDF 5.5.5) does not wait for a running D-cache preload before the MSPI
  reset (hang until the RTC WDT; worked around here by a shutdown handler); the stock RGB LCD driver's bounce refill
  preloads the same way (KAIZEN "Robustness / parity")
- ESP-IDF upstream issue: the RGB LCD driver with CONFIG_LCD_RGB_RESTART_IN_VSYNC=y (Arduino's default) restarts at
  every VSYNC without resetting its bounce-buffer EOF count: one EOF the refill ISR misses (an NVS write holds it off
  ~14 ms) swaps the buffer it refills for good, and the picture stays shifted sideways by a bounce buffer; worked around
  with =n (firmware/platformio.ini, env lcd316 comment)
- LCD 3 tubes swinging at 80 MHz: ~3 ms a frame short of 30 fps (27.6); levers in KAIZEN (render-side hash, 64-B tile
  bursts, residue / palette leftovers)
