# ESP32-S3-LCD-3.16 — mechanical data

_Source: Waveshare wiki (https://www.waveshare.com/wiki/ESP32-S3-LCD-3.16), dimension drawing
`vendor/waveshare/ESP32-S3-LCD-3.16-dimensions.jpg`, component map `vendor/waveshare/ESP32-S3-LCD-3.16-onboard.jpg`.
All mm. Waveshare publishes no STEP/DXF. Measure everything marked "verify" with calipers before freezing a
housing._

## Outline

| Item | Value | Note |
|---|---|---|
| PCB | **33.35 × 78.85** | larger than the glass by ~1.1 mm per side |
| Glass (LCD module) | **31.20 ± 0.15 × 76.60 ± 0.15** | |
| Total thickness | **9.30** | glass front → tallest back part |
| Side view, sub-dims | 3.90, 2.40 | probably the LCD module and the PCB/standoff layers. Verify |
| Mounting | 4 × M2 SMD copper nuts on the back (M2 × 3.5 × 3.5 + 2.0 × 1.2) | |
| Hole pitch | **27.35 × 72.75**, centres 3.00 in from each PCB edge | |

## Active area (AA)

| Item | Value |
|---|---|
| AA | **26.40 × 67.65** for 320 × 820 px → **0.0825 mm/px** on both axes |
| AA from the long glass edges | 2.40 each side (centred across) |
| AA from the short glass edges | 2.60 at the far end, 76.60 − 67.65 − 2.60 = **6.35 at the USB-C end** (FPC end) |

`spec/layout.h|ts` take this pitch as `LCD_MM_PER_PX` (0.0825; `PX_SCALE_NARROW` / `PX_PER_MM` follow) since
2026-11-13. Before, they used 0.0912 mm/px (830/912): the nominal 3.16" diagonal (√(29.2² + 74.8²) = 80.3 mm), not the
drawing. The drawing's AA is 72.6 mm diagonal (2.86"). **Confirmed 2026-11-13:** firmware's measuring face (`m`: frame on
the outermost pixels, px rulers white, mm rulers green at the assumed pitch) matched a steel ruler.

Measured 2026-11-13 (ruler, lit `m` face), AA edge → PCB edge:
- **USB-C end ≈ 7.6**: 1.6 black glass, ~5 lighter glass (FPC bond), ~1 PCB beyond the glass. Drawing: 6.35 + 1.1 = 7.45.
- **Far end ≈ 3.6**: 1.6 black, ~1 glass, ~1 PCB. Drawing: 2.60 + 1.1 = 3.7.
So the AA centre sits ~2 mm towards the far end from the PCB centre (78.85/2 − 3.7 − 67.65/2 = +1.9).

## Back side (USB-C at the bottom, viewed from the back)

- **USB-C**: bottom short edge, roughly centred. Flashing, log output and charging. Charge LED "CHG" next to it.
- **Right long edge** (side-actuated): RST and BOOT buttons, 10.77 apart. The power **SWITCH** (slide, ON/OFF) is
  below them, near the USB end. Drawing: 22.72 from BOOT to the bottom hole row.
- **Left long edge**: RTC (SH1.0 2-pin), I2C (SH1.0 4-pin), USB J5 (**MX1.25 4-pin**: VBUS, D−, D+, GND, parallel to the Type-C), UART (SH1.0 4-pin) on a 16.97 pitch. UART sits 19.45 above the bottom
  hole row.
- **BAT**: MX1.25 2-pin, 3.7 V LiPo, on-board charge/discharge, centre-bottom area. Polarity: verify with a meter, as
  for the AMOLED (`docs/hardware-handoff.md`).
- **RTC battery**: SH1.0 slot (item 7).
- **TF card** slot: upper half, card inserts from the board's top-right area.
- IPEX antenna connector (item 3) at the top edge.
