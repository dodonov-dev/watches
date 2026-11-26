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
| Total thickness | **9.30** | glass front → tallest back part (drawing). **Measured 9.15** to the acrylic plate's back face (user, 2026-11-26) |
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

## Back plate (photos 2026-11-26, not in Waveshare's drawing)

- A frosted acrylic plate covers the whole back, screwed to the 4 brass standoffs. Its back face is flat and the
  tallest surface of the board. The screw heads sit ~1 deep in it.
- Cut-outs on the left edge (viewed from the back) at I2C, J5 and UART, ~5 in from the edge; a window over BAT
  (~13 wide, slightly off-centre). The connectors' tops end ~1 below the plate's back face. **UART, J5 and I2C open
  upwards** (towards the back, through the cut-outs): their plugs and wires stand behind the plate. Only RTC opens to
  the side (user, 2026-11-26).
- RTC sits under the plate with no cut-out, its top end 3-4 below the top-left screw: centre ~8 below the screw's
  centre (from a photo), not on the 16.97 pitch.
- Schematics: `vendor/waveshare/ESP32-S3-LCD-3.16-schematic.pdf` (original) and `...-schematic-rev1.1.pdf`. This board
  reports flash manufacturer `20` (XMC) in `esptool.py flash_id`: Rev 1.1's part (the original has Winbond, `ef`).
- RTC socket (both revisions): charges the cell from 3V3, so **rechargeable 3 V cells only** (e.g. ML1220 with an
  SH1.0 2-pin lead). Pin 1 = plus, pin 2 = GND. Rev 1.1 charges through 4.7 k; the original through a diode alone.
  The RTC is fed from 3V3 only: with the slide switch off and no cell, it stops.

## To measure (open, 2026-11-26; for the pebble's board keeper, `cad/desk/concept/board-bracket/`)

Picture: `docs/lcd316-to-measure.png` (same numbers; made by `cad/desk/concept/board-bracket/measure_sheet.py`).
Item 1 is measured (9.15, in the pebble's model as `KEEPER["BOARD_T"]`). Item 4b also touches the shell (the lower plug-side
rib), but there is no RTC plug at hand: left at the assumed 4.0; the rib can be filed back if it turns out tight.

Calipers, board out of the housing:

1. **Total thickness**: glass front to the plate's back face, at all 4 corners. **Done: 9.15** (user, 2026-11-26). The
   other variants still use 9.0 (`hw.BOARD_T`).
2. **Plate thickness** and **standoff height** (PCB back to the plate's underside). Assumed 2.0 and ~2.1.
3. **Connector tops below the plate's back face** (~1 by eye), and the same with a cable plugged in: does the plug or
   its wires stand above the plate anywhere?
4. **Plugs**: (a) UART / J5 / I2C: how far a plug and its wire bend stand above the plate's back face (model: 4.0,
   `KEEPER["PLUG_UP"]`). (b) RTC: how far its plug and wire bend reach beyond the PCB's long edge (model: 4.0,
   `PLUG_PROUD`); sets the lower plug-side rib (it must stay outside it).
5. **Cut-outs**: depth in from the PCB edge (~5) and length along the edge (~7), for one of them; is the plate's edge
   flush with the PCB's?
6. **RTC position**: its centre below the top-left screw's centre (~8 from the photo).
7. **BAT window**: width, and offset of its centre from the board's centre line (~13 wide, ~0.7 off).
8. **Screw recess diameter** in the plate (the pads must be larger than it, or sit beside it).

Multimeter, before a cell goes into the RTC socket:

9. **Revision**: board powered over USB, RTC socket empty, a 1 kΩ resistor across its two pins; measure the voltage
   across the resistor. ~0.5 V = Rev 1.1 (4.7 k charge resistor), ~3 V = original. Do not short the pins.
10. **Polarity**: board powered, socket empty, no resistor: find which pin shows ~+3 V against GND (the USB shell).
    That is plus. Match the cell's lead to it before plugging in.
