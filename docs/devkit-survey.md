# Dev-kit survey: faster boards for the bar face

Web research, 2026-11-05. Prices are 1-unit list prices on the day; US listings now often add a 38-40 % tariff
note. A ppi value without a source is my own arithmetic (diagonal px / inches). "(unv)" = not verified, "(inf)" =
inferred. Speed estimates are models built from CoreMark and memory figures, not measurements. Builds on
`lcd316-3tube-perf.md` and `h573-bench-plan.md` (the H573I-DK is owned; its bench has not been run yet).

## Baseline: what a new board has to beat
- LCD-3.16, 3 tubes 10-8-6, lcd-1105 look:
  - Pinned: 34-35.5 fps.
  - Swinging: ~26 fps, with ~71 ms of work per frame over two cores. That splits into render ~52 (h 22 / m 15 / s 14),
    push ~17 (gather wait, hash, store into the scanned fbuf) and physics ~2.5.
- AMOLED-1.91: 61 fps with two tubes; 35.5 fps with three, because they run serialized (KAIZEN). The panel's GRAM
  means nothing is scanned out of PSRAM.
- Pixel budget: ~240 k px rendered per frame (820 x 293 rows).
  - At the same physical tube size, work grows with ppi². A 360 ppi panel costs ~1.5x the work of today's 278 ppi.
  - A denser panel therefore eats part of any speed-up. Lower canvases were already rejected by eye.
- What would actually help:
  1. CPU throughput: two cores, or one much faster core.
  2. Memory: either ≥ ~1 MB of on-chip SRAM, or external RAM several times faster than the S3's. The full set is
     ~375 KB of render state, 3 strips of ~177 KB and a 525 KB fbuf.
  3. A 2D/DMA engine that rotates by 90°, for the transposed scan.
  4. BLE that does not take render RAM.

## Short answer
- No kit on sale combines a bar display (≥ 250 ppi, 2.5-4") with a faster chip. Every option means a kit plus a
  separate panel, or a not-quite-bar panel.
- The cheapest real speed-up at low porting cost is the **ESP32-P4 (v3 silicon)**:
  - Same ESP-IDF/Arduino code base, ~2x the CPU and ~5x the PSRAM bandwidth.
  - Its PPA does the 90° rotate in hardware; BLE runs on a separate C6.
  - Expected ~45-55 fps swinging at today's pixel count (inf).
- The fastest MCU class is the **Renesas RA8P1/RA8D2 (Cortex-M85, 1 GHz, 2 MB SRAM)**:
  - Expected ~2.5-3.5x (inf), with the fbuf in SRAM.
  - Porting cost is high: new SDK, one fast core instead of two equal ones.
- Recommended order:
  1. Buy #1 below (~$50) and port the renderer to measure the P4 for real.
  2. Run the planned H573 bench. It calibrates the Cortex-M estimates.
  3. If ≥ 2x holds, build the product path, #3: a P4 board plus an ST7701 bar panel.

## Top 5

| # | Kit | Price | Chip / memory | Display | Accel | Radio / sensors | SDK | Speed vs today (inf) | Port |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Waveshare ESP32-P4-WIFI6-Touch-LCD-5 | $45-53 | P4NRW32X (v3, 400 MHz), 768 KB L2MEM, 32 MB PSRAM (16-bit DDR, 200-250 MHz) | 5" 720x1280 IPS, 294 ppi, HX8394, 2-lane DSI (video mode, no GRAM used) | PPA (rotate 90/180/270, blend, fill, scale), 2D-DMA | C6 (Wi-Fi 6, BLE 5); LiPo header + charging; no IMU/RTC | ESP-IDF / Arduino | ~1.8-2.2x: 45-55 fps swinging, 60 pinned (vsync) | low-medium |
| 2 | LilyGO T-Display-P4 (AMOLED) | $119 (sold out at LilyGO), $136-160 resellers | P4 (listed 360 MHz, likely v1.x), 32 MB PSRAM | 4.1" 568x1232 AMOLED, 331 ppi, 2.17:1, DSI | PPA | C6 BLE, ICM20948, PCF8563 RTC, charger + gauge, LoRa, GPS | ESP-IDF / Arduino | ~1.1-1.3x at full res (1.8x the pixels); ~1.6x over an 820 px span | low-medium |
| 3 | DIY: a P4 v3 board + ST7701 RGB bar panel | board $30-55 + panel $11-30 | as #1 | Adafruit 5797 3.2" 320x820 (today's grid) / 2.86-2.9" 376x960 (360 ppi) / 3.4" 412x960 (307 ppi) | PPA | C6 BLE; IMU/RTC as breakouts | ESP-IDF / Arduino | 320x820 ~2x; 376x960 ~1.3x; 412x960 ~1.5x | medium (wiring, RGB timing) |
| 4 | RT-Thread RA8P1 Titan (~$50) or EK-RA8D2 ($184, 7" RGB panel in box) | $50 / $184 | M85 1 GHz + Helium, M33 250 MHz; 2 MB SRAM (256 KB TCM); Titan 32 MB HyperRAM, EK 64 MB SDRAM | Titan: none (DSI + RGB out); EK: 7" 1024x600 RGB. GLCDC drives ST7701 bar panels | 2D drawing engine (DRW/Dave2D: blend, rotate) | Titan: Wi-Fi/BT module (unv: BT 4.1?); EK: none | FSP, Zephyr, RT-Thread | ~2.5-3.5x: ≥ 60 fps at 320x820 | high |
| 5 | STM32N6570-DK ($219), or NUCLEO-N657X0-Q (~$69) for a CPU bench | $69-219 | M55 800 MHz + Helium, CoreMark 3360; 4.2 MB SRAM; 32 MB hexa PSRAM | DK: 5" 800x480 RGB (LTDC) | NeoChrom GPU2D (rotate, blend, scale), DMA2D | none | STM32Cube / Zephyr (same flow as the H573 plan) | ~2-2.5x | high (bench port low: H573 harness) |

### 1. Waveshare ESP32-P4-WIFI6-Touch-LCD-5: measure the P4 first
- **Board:** ESP32-P4NRW32X (the "X" marks v3 silicon), 32 MB PSRAM, 32 MB flash; 5" IPS 720x1280 HX8394 over 2-lane
  DSI; C6-MINI-1 over SDIO (Wi-Fi 6 / BLE 5); MX1.25 LiPo header with charging; 40-pin 2.54 mm header; no IMU and
  no RTC chip. https://www.waveshare.com/esp32-p4-wifi6-touch-lcd-5.htm
- **Why this one:** the cheapest v3 board. v3 runs at 400 MHz (v1.x at 360) with 250 MHz PSRAM.
  - Our 820-px face fits along the 1280 axis at 294 ppi: 70.8 mm long, against 75 mm today.
  - The panel scans 720-px lines, so the transpose stays, but the PPA does it.
  - Revisions: https://www.espressif.com/en/node/10681, https://documentation.espressif.com/esp32-p4_datasheet_en.html
- **P4 versus S3:**
  - CPU: CoreMark 2489.62 for both cores at 360 MHz (datasheet), about 2.1x the S3 per core at 400 MHz.
    FP32 FMA per core 0.716 vs 0.478 GFLOPS (Tab5 vs CoreS3, https://github.com/nnn112358/ESP32-TOPS-BenchMark).
  - Memory bandwidth:
    - PSRAM is 16-bit DDR at 200-250 MHz: 800 MB/s-1 GB/s theoretical, against the S3's 160.
    - Measured at 200 MHz: PSRAM→SRAM 184 MB/s (https://github.com/espressif/developer-portal/discussions/353).
    - PSRAM copy 61 vs 9.5 MB/s (TOPS bench).
    - 64 KB L1 D-cache plus a 128-512 KB L2 cache.
  - Fbuf scan-out: a 320x820 panel at 60 Hz streams 31.5 MB/s, a few % of the P4's PSRAM. Today it is the
    contended resource.
  - BLE lives on the C6, which frees the S3's ~36 KB controller plus the NimBLE heap.
  - LVGL 800x480 benchmark: 60 fps on the P4 vs 25 on the S3
    (https://docs.espressif.com/projects/esp-techpedia/zh_CN/latest/esp-friends/advanced-development/lcd-application-note/overview.html).
- **Estimate (inf):**
  - Render at 1.7-2.0x: integer blends gain more than floats; the PIE digit path falls back to scalar.
  - Push at 3-5x, with the PPA rotate and the faster PSRAM.
  - Work: 71 → ~34 ms·core over two cores, plus imbalance, gives ~20 ms a frame: 45-55 fps swinging. Pinned hits
    the 60 Hz vsync.
- **Port (low-medium):** renderer, physics, presets and tools stay. Rewritten or swapped:
  - `display_lcd316.cpp`: the RGB bounce-buffer scan becomes the esp_lcd DPI/DSI panel, or RGB on #3.
  - `tile_dma.cpp`: GDMA becomes AXI-GDMA / 2D-DMA / PPA.
  - The S3 PIE asm in `render.cpp`: 85 `ee.*` lines; the scalar path exists, or port to the P4's `esp.*` PIE, which
    is not source-compatible (https://developer.espressif.com/blog/2024/12/pie-introduction/).
  - The Xtensa `sqrt0.s` asm (render.cpp:380): becomes `fsqrt.s`.
  - BLE: NimBLE-Arduino 2.x does not list the P4. Use ESP-IDF NimBLE over ESP-Hosted, or Arduino 3.3.1+
    (https://github.com/espressif/arduino-esp32/pull/11804).
  - Toolchain: v3 needs IDF ≥ 5.5.3, so check pioarduino's IDF
    (https://documentation.espressif.com/esp32-p4-chip-revision-v3.x_user_guide_en.html). The IMU (QMI8658 class)
    goes on the 40-pin header.
- **Alternative with sensors:** M5Stack Tab5, $55-60.
  - Has: 5" 1280x720 (294 ppi), BMI270, RX8130CE RTC, battery and a C6 (https://docs.m5stack.com/en/core/Tab5).
  - Against it: the part is P4NRW32 without the "X", so likely v1.x at 360 MHz (inf). It is 128x80 mm, and v1 and
    v3 images are not interchangeable.

### 2. LilyGO T-Display-P4 (AMOLED): the closest thing to "faster chip + bar-ish AMOLED + sensors"
- **Board:** 4.1" AMOLED 568x1232 (331 ppi, 2.17:1) over DSI; 4.05" TFT 540x1168 variant. ICM20948 9-axis IMU,
  PCF8563 RTC, LGS4056H charger + BQ27220 gauge, C6, LoRa, GPS; 63x109x22 mm; controller RM69A10 / HI8561 (unv).
  - https://lilygo.cc/products/t-display-p4, https://wiki.lilygo.cc/products/t-display-series/t-display-p4/
  - Ameridroid $159.95, low stock: https://ameridroid.com/products/lilygo-t-display-p4
- **Against:**
  - The P4's DSI is video mode only, so the AMOLED's GRAM goes unused and the fbuf is scanned from PSRAM (84 MB/s
    at 60 Hz; fine on the P4) (https://docs.espressif.com/projects/esp-iot-solution/en/latest/display/lcd/mipi_dsi_lcd.html).
  - At full length the tubes are 1.8x today's pixels, which eats most of the gain. An 820-px span (63 mm) keeps ~1.6x.
  - Listed at 360 MHz (likely v1.x).
  - Over budget, phone-sized, mostly sold out.

### 3. DIY P4 + ST7701 bar panel: the product path once #1 proves the speed-up
- **Interface:** the P4's LCD_CAM drives 8/16/24-bit RGB panels like the S3's. IDF note: keep the 16-bit pclk
  under 40 MHz; LCD DMA and CPU share PSRAM (https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-reference/peripherals/lcd/rgb_lcd.html).
  Our panel runs at 16 MHz.
- **Panels:**
  - Adafruit 5797, 3.2" 320x820 TL032FWV01 with touch, $29.95: today's grid, a 1:1 A/B
    (https://adafruit.com/product/5797). 5828 is the no-touch version.
  - 2.86-2.9" 376x960 ST7701S (360 ppi):
    - BuyDisplay ER-TFT2.86-1, ~$11 (https://www.buydisplay.com/bar-type-2-86-inch-376x960-ips-tft-lcd-display-spi-rgb-interface).
    - Newhaven NHD-2.9-376960AF-ASXP, €23.75, 1050 nits, in stock (https://newhavendisplay.com/2-9-bar-type-tft-376x960px-ips-display/).
  - 3.4" 412x960 ER-TFT034-1 (307 ppi), price n/a (https://www.buydisplay.com/bar-type-3-4-inch-412x960-ips-tft-lcd-display-spi-rgb-interface).
- **Board:** needs a P4 v3 board with ≥ ~22 free GPIOs plus a 40-pin RGB FPC breakout. Candidates: Espressif
  Function-EV-Board (P4X version), Waveshare ESP32-P4-Module-DEV-KIT / P4-Nano. Free pins unverified.
- **DSI variant:** MIPI versions of the 2.86" bar exist (Mango MTB286001B0-T, Tailor TTL286XVS-01; price, stock and
  lane count unv) for the P4's DSI connector through a custom FPC adapter.

### 4. Renesas RA8P1 Titan / EK-RA8D2: the raw-speed MCU
- **RA8D2:** M85 at 1 GHz with Helium, plus an M33 at 250 MHz; "7300+" CoreMark for both; 2 MB SRAM with 256 KB M85
  TCM; 1 MB MRAM; GLCDC with RGB + 2-lane DSI; 2D drawing engine.
  - https://www.cnx-software.com/2025/10/27/1ghz-renesas-ra8d2-and-ra8m2-cortex-m85-mcus-feature-up-to-1mb-mram-2mb-sram/
- **EK-RA8D2 (https://www.renesas.com/en/design-resources/boards-kits/ek-ra8d2):** $183.92; 7" 1024x600 RGB in the
  box; 64 MB SDRAM; no radio or IMU.
- **RA8P1 Titan:** same CPU plus an NPU; 32 MB HyperRAM, 64 MB NOR; DSI/RGB; Wi-Fi/BT; ~$50 on AliExpress; Zephyr
  board `ra8p1_titan`.
  - https://www.cnx-software.com/2025/11/12/ra8p1-titan-board-features-1-ghz-cortex-m85-mcu-for-aiot-applications-rt-thread-development/
  - Titan Mini ~$44: https://www.cnx-software.com/2026/07/02/titan-mini-smaller-renesas-ra8p1-based-edge-ai-board-for-rt-thread-rtos-development/
- **Estimate (inf):**
  - CoreMark per core is ~9.5x one S3 core. I discount that to 5-7x for SRAM beyond the TCM, 32-64 KB caches and
    floats, which gives ~2.5-3.5x the S3 pair.
  - The fbuf (525 KB) and render state (375 KB) fit in SRAM, so the push becomes an SRAM blit with the 2D engine
    rotating.
  - The sprites (712 KB) have to sit in MRAM, OSPI XIP or HyperRAM.
  - Helium has C intrinsics (`arm_mve.h`), so the digit blend's SIMD port is easier than PIE asm.
- **Risks:**
  - The product page says the GLCDC goes "up to 1280x800", while the FSP limits read up to ~2038x2043. 820 lines
    needs checking (https://renesas.github.io/fsp/group___g_l_c_d_c.html).
  - Single fast core: today's two-core split becomes M85 render + M33 physics/BLE.
  - New SDK.
- **Bench path:** the `h573-bench-plan.md` harness (render.cpp + physics.cpp + two shims, serial protocol for
  bench.py) carries over to any Cortex-M. Only startup, clock, UART and the linker script change.

### 5. STM32N6570-DK / NUCLEO-N657X0-Q: if staying with ST tools
- **Chip:** M55 at 800 MHz with Helium, CoreMark 3360, 4.2 MB SRAM: fbuf, strips, state and even the sprites fit
  on-chip. 32 MB hexa PSRAM; NeoChrom (rotate, blend, scale) plus DMA2D; LTDC RGB (the DK has a 5" 800x480).
  - https://www.mouser.com/ProductDetail/STMicroelectronics/STM32N6570-DK?qs=%2BXxaIXUDbq0LuvUu20SpPg%3D%3D
  - https://www.futureelectronics.com/ftm/ai-edge-solutions/stmicroelectronics-stm32n6-microcontroller
- **Price:** DK $219; Nucleo ~$69 with a long lead time, and whether its LTDC pins reach a header is unv
  (https://www.avnet.com/americas/product/stmicroelectronics/nucleo-n657x0-q/evolve-117383084/).
- **Fit:** ~2-2.5x (inf). No radio. Same STM32Cube flow as the H573 bench, so it is the cheapest second data point
  after the H573.

## Bar panels a faster board could drive

| Panel | Res / ppi | Tech, controller, interface | GRAM | Price / source |
|---|---|---|---|---|
| 3.16" (today) | 320x820 / 278 | IPS ST7701S, RGB (+SPI init) | no | Tailor TTC316XVS-01, quote only (https://tailorpixels.com/?p=27334) |
| 3.2" Adafruit 5797 | 320x820 / 275 | IPS ST7701S, RGB-666 40-pin, touch | no | $29.95 (https://adafruit.com/product/5797) |
| 2.86-2.9" | 376x960 / 355-360 | IPS ST7701S, RGB; MIPI variants exist | no | $11 BuyDisplay; €23.75 Newhaven (links in #3) |
| 3.4" ER-TFT034-1 | 412x960 / 307 | IPS ST7701S, RGB | no | n/a (link in #3) |
| 3.18" Tailor | 288x960 / 315 | IPS, MIPI | no | quote (https://directindustry.com/prod/tailor-pixels-technology-co-ltd/product-245050-2563418.html) |
| 3.7" Adafruit 5799 | 240x960 / 267 | IPS ST7701S, RGB | no | $21.95 (https://www.adafruit.com/product/5799) |
| 3.99" Tailor TTH399BVS-01 | 400x960 / 261 | IPS ST7701, MIPI or RGB | no | quote (https://www.directindustry.com/prod/tailor-pixels-technology-co-ltd/product-245050-2577750.html) |
| 1.91" RM67162 | 240x536 / 307 | AMOLED, QSPI (MIPI 1-lane variant) | yes | Gesight $17.85 (https://gesight.com/product/1-91-inch-240x536-amoled-smart-phone-display); our AMOLED board |
| 1.4" ICNA3306 | 128x400 / 300 | AMOLED, QSPI | yes | sourcing unv (https://cdn.shopify.com/s/files/1/0829/9960/7616/files/1.4_INCH_AMOLED_DISPLAY_MODULE.pdf) |
| 3.49" / 3.4" AXS15231B | 172x640 / 190, 180x640 / 196 | IPS, QSPI | yes | on Waveshare / LilyGO S3 boards; below 250 ppi |

- **GRAM vs scan-out:**
  - Panels with GRAM (QSPI) skip host scan-out, but QSPI at 80 MHz is ~40 MB/s. A full 240x536 frame then needs
    ~6.5 ms, which is fine; 320x820-class over QSPI would be ~13 ms.
  - No ≥ 250 ppi bar with GRAM exists at 3"+.
  - The P4's DSI cannot use panel GRAM (video mode only), so on the P4 the fbuf lives in PSRAM. That is cheap there.
- **Bigger strips (too big for a wrist):** Waveshare DSI 6.25" 720x1560 (275 ppi, ~$60, P4-Nano BSP v3 only),
  7.9" 400x1280, 8.8" 480x1920, 11.9" 320x1480
  (https://components.espressif.com/components/waveshare/esp32_p4_nano/versions/3.0.0/readme).

## Watch list (not buyable as a fitting kit yet)
- **ESP32-S31:** in mass production since 2026-07-27 (https://www.espressif.com/en/news/ESP32_S31_Mass_Production).
  - Dual RISC-V at 320 MHz, 6.86 CoreMark/MHz, SIMD on one core only; 512 KB SRAM; PSRAM 8-bit DDR at 250 MHz
    (~3x the S3).
  - RGB/i80 LCD, PPA, 2D-DMA; BLE 5.4 and Wi-Fi 6 on chip (https://www.espressif.com/en/products/socs/esp32-s31).
  - It is the natural single-chip successor for exactly this RGB bar panel: ~1.5x (inf), same IDF.
  - Against: the same 512 KB SRAM squeeze, no DSI, and no board with a small display.
- **STM32V8:** M85 at 800 MHz, Chrom-ART (DMA2D) only; DK and Nucleo still "coming soon" in the last reports
  (https://www.cnx-software.com/2025/11/19/st-stm32v8-arm-cortex-m85-800-mhz-high-performance-mcu-18nm-fd-soi-process/).
- **PineTime Pro:** M33 at 200 MHz, 2.13" 410x502 AMOLED; not released.

## Tempting but wrong

| Kit | Why not |
|---|---|
| LilyGO T-Watch Ultra ($90), Waveshare ESP32-S3-Touch-AMOLED-2.06 / 1.8 / 2.41, M5Stack StopWatch, LilyGO T4-S3 | Same S3; GRAM AMOLEDs, but 1.2-1.3:1, not bars. Only good as wearable-integration references |
| Waveshare ESP32-S3-Touch-LCD-3.49, LilyGO T-Display-S3 Long | True bar with GRAM, but 190-196 ppi and the same chip. The AXS15231B forces full-frame writes and software rotation (https://github.com/espressif/esp-iot-solution/issues/579) |
| Waveshare ESP32-P4-Knob-Touch-AMOLED-1.75 ($49) | v3 P4 with IMU, RTC and PMU, but a round 466x466: tubes too short |
| Waveshare P4 3.4C / 4C round, 4B, 7"-10.1", Guition JC-series, Elecrow CrowPanel, Espressif Function-EV | P4, but round or ≤ 217 ppi or tablet-sized; #1 is the better P4 bench |
| STM32H7S78-DK ($157) | 600 MHz M7, but 620 KB SRAM puts the fbuf back in PSRAM, and code runs from external flash (CoreMark 3324 → 2278) |
| STM32U5G9J-DK1 / DK2 ($123-165) | 3 MB SRAM and NeoChrom, but a 160 MHz M33 is about one S3 core |
| STM32H747I-DISCO, H7B3I-DK | DMA2D cannot rotate; older parts; out of stock |
| MIMXRT1170-EVKB ($200 + $91 panel) | Fast (M7 at 1 GHz, PXP rotate, 2 MB SRAM), but ~$290, a DSI-only kit panel and a new SDK; RA8 is cheaper for the same class |
| MIMXRT595 / RT700 EVK ($148-187) | M33 at 200-325 MHz is about the S3 pair; no display in the box |
| EK-RA8D1 ($326) | Half the RA8D2's speed, 1 MB SRAM, dearer |
| Ambiq Apollo510 EVB + display ($262 + $105) | M55 at 250 MHz is S3-class; DSI capped at 640x480 (820 rows risky); BLE only on the pricier B variant |
| Alif E7 AppKit ($249) | 13.5 MB SRAM, BLE and IMU, but 400 / 160 MHz M55 |
| Infineon PSoC Edge E84 AI kit ($64-73) | Cheap, with BLE, IMU, 5 MB SRAM and a GPU, but an M55 at 400 MHz is ~1.3x the S3 pair; DSI only, 1024x768 max |
| SiFli SF32LB52 kits, LilyGO T-Display SF32 ($22-59) | Real watch silicon (BLE, charger, GPU, AMOLED), but CoreMark 984 is below the S3 pair, and ePicasso stops at 512 px |
| RP2350 (Pimoroni Presto, Waveshare RP2350 AMOLED / 3.49) | Slower CPU; a 525 KB fbuf does not fit 520 KB SRAM; QSPI PSRAM is slow |
| Bouffalo BL616 / 618 / 808 (Sipeed M0P, M1s, Ox64) | Immature SDK, spotty stock, small SPI screens; DSI doubtful |
| Luckfox Pico / Lyra, T113 boards, Pi Zero 2 W, Radxa Zero 3W | Plenty of compute (A7/A53 + DDR), but 6-30 s boot, ≥ 0.3 W idle, no watch PMIC / IMU / RTC. Desk prototypes only |
| PineTime, Bangle.js 2, Watchy, ZSWatch, XIAO Round Display | 64-256 KB RAM or low-res screens |

## Estimation method and gaps
- **Speed model:** frame work = render (compute-bound, with some PSRAM stalls) + push (memory-bound) + physics.
  - Compute scales with CoreMark per core times core count, discounted for float and memory effects.
  - Push scales with external-RAM bandwidth, or vanishes into SRAM blits.
  - Then multiply by panel pixels relative to 240 k.
  - All "(inf)" until benched. The H573 bench (owned DK) is the first real Cortex-M data point; #1 is the first P4 one.
- **Not found:**
  - Any LVGL or software-render benchmark at our resolution on these chips.
  - The P4's fdiv/fsqrt latencies.
  - Which P4 boards expose enough GPIOs for a 16-bit RGB panel.
  - The RA8D2 GLCDC's real vertical limit.
  - The T-Display-P4's panel controller.
  - Whether the Titan's radio is BLE 4.1 or 5.
- **Power (not ranked):** P4 at 400 MHz dual-core draws 69-112 mA (datasheet) vs the S3's 66-108 mA, plus the C6.
  None of the faster options is single-chip with BLE except the S31.
