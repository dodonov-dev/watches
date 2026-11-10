# Development Kit & Display Module Survey for Liquid Watch (`agy`)

_Survey Date: 2026-11-09 | Scope: Independent web hardware survey for upgrading the Liquid Watch hardware platform beyond the Waveshare ESP32-S3-LCD-3.16 (`SKU 28608`) and ESP32-S3-AMOLED-1.91 (`SKU 28872`)._

---

## 1. Executive Diagnosis: What Actually Bottlenecks Our Renderer?

Before evaluating replacement hardware, we map the measured bottlenecks from `docs/lcd316-3tube-perf.md`, `STATUS.md`, and `docs/h573-bench-plan.md` onto specific hardware subsystem requirements:

| Bottleneck on Waveshare ESP32-S3-LCD-3.16 (`lcd316@320w10-8-6+t3`) | Measured Impact (80 MHz PSRAM) | Hardware Fix Required |
|---|---|---|
| **1. RAMless Panel + Octal PSRAM Contention** | ST7701S in RGB565 video mode has **0 B internal GRAM**. Continuous 16 MHz DMA scan-out drains **~32 MB/s** from an 80 MHz Octal PSRAM bus (~55–65 MB/s usable), starving both CPU cores (`render` slows ~1.4× when strips move from SRAM to PSRAM; 18 MHz PCLK tears/jumps). | **(A)** Panel with **internal GRAM** (QSPI or MIPI-DSI Command Mode) so scan-out is handled inside the display IC (0 MB/s host bus drain), **OR**<br>**(B)** Wider/faster external RAM (**16-bit Hexadeca-SPI PSRAM @ 200 MHz DDR** on ESP32-P4/STM32H7S7 = 400 MB/s peak) or **multi-MB internal SRAM** (STM32U5G9 3 MB, STM32N6 4.2 MB, i.MX RT595 5 MB, RT700 7.5 MB). |
| **2. 512 KB Internal SRAM Exhaustion** | Static allocations + NimBLE leave **96–504 B free**; requires the "BLE window + fast mode" reboot workaround to free ~46 KB so the 16 KB seconds `Tube` and 8 KB fizz masks fit internally. Native strips (3 × 195 KB × 2 buffers = ~1.17 MB) and glyph pools (3 × 92 KB = 276 KB) are forced into PSRAM. | **≥ 768 KB to 4+ MB internal SRAM** so all three `Tube` contexts (~48 KB), LUTs/masks, NimBLE, and either full strips or large L2 caches stay in zero-wait/low-latency on-chip SRAM permanently without rebooting to disable BLE. |
| **3. Quarter-Turn `push` Stage (820×320 → 320×820)** | Even with Lever 1's tile-hash change records (`turn_segs_rec`), hashing + gathering + 90° rotating changed 64-col segments into the portrait PSRAM framebuffer costs **2.9 ms pinned / 6.6–9.1 ms swinging** plus ~1.5–2.5 ms of hash overhead inside `renderTube`. | **(A)** **Hardware 2D Rotation Engine** (ESP32-P4 **PPA SRM**, NXP **PXP**, STM32 **NeoChrom GPU2D**, Renesas **Dave2D**) to DMA-rotate strips 90° in < 1.5 ms with zero CPU/cache pollution, **OR**<br>**(B)** Panel driver IC that supports hardware **MADCTL XY-swap (`MV=1`)** into internal GRAM over QSPI/MIPI Command Mode. |
| **4. Dual-Core CPU & 16–32 KB I-Cache Saturation** | Swinging 3-tube frame takes **~71 ms of total CPU work** across 2 cores (`render` h ~21.6 ms, m+s ~29.9 ms, physics ~2.5 ms) = **27.6 fps swinging / 40.7 fps pinned**. Shared 32 KB I-cache and 64 KB D-cache thrash across `drawSpriteGlyph`, `bandRow`, `discRow`, and `traceFillRow`. | Higher-clock dual-core MCU (**ESP32-P4 @ 360–400 MHz** = ~2,490 CoreMark vs S3's 1,330; **i.MX RT1170 @ 1 GHz M7 + 400 MHz M4**) or **SIMD/Helium MVE** cores (**Cortex-M85 @ 480 MHz / Cortex-M55 @ 800 MHz**) with **≥ 64–256 KB caches**. |
| **5. 16-bit RGB565 Gradient Hue Banding** | On `ESP32-S3-LCD-3.16`, the ST7701S is hardwired to 16 GPIO data lines (**RGB565**). Because Green has 64 steps and Red/Blue have 32 steps, smooth near-grey tube backs and meniscus glows exhibit alternating green/magenta hue steps. | Display link carrying **24-bit RGB888** (or 18-bit RGB666 where R=G=B=6 bits) over **MIPI-DSI** or **QSPI**, allowing true 8-bit neutral greys (or ordered-dithered/LUT-expanded RGB888 output during the push pass). |

### Why 2D GPUs Help Our `push` & Blending, But Not Every Inner Loop
Our renderer (`firmware/src/render.cpp`) is not a standard retained-mode widget tree: it computes per-pixel Beer–Lambert annular residue (`FILM_PHI[(A*K + 32768) >> 16]`), 3-layer premultiplied meniscus dishes (`bandMark`), per-column `wetShare` meniscus refraction ramps (`drawRampColumn`), and depth-tinted fizz rings (`discRow`). Fixed-function 2D blitters (STM32 DMA2D, ESP32-P4 PPA BLEND, NXP PXP) **cannot** execute those procedural inner loops.
However:
1. **Hardware 90° Rotation + Format Conversion (RGB565 → RGB888):** ESP32-P4's **PPA SRM** (Scaling, Rotation, Mirroring), NXP's **PXP**, and STM32's **NeoChrom GPU2D** offload the entire 90° strip-to-framebuffer rotation and RGB565→RGB888 expansion into a background DMA pass, eliminating the tile-hash bookkeeping and freeing **7–11 ms of wall time per swinging frame**.
2. **SIMD Vector Instructions (ARM Helium MVE / RISC-V PIE `Xespv2`):** Unlike fixed 2D blitters, Helium MVE (on STM32N6, Renesas RA8D1, Ambiq Apollo510) and Espressif PIE 128-bit SIMD (on ESP32-P4) accelerate our **exact C++ per-pixel loops** (`spriteRunInt`, `spriteRunFrac`, `bandRow`, `traceFillRow`) by 2–4× once vectorized.

---

## 2. Comprehensive Candidate Survey

### Category A: ESP32-P4 Devkits & Modular Display Platforms (Lowest Porting Effort, Massive Bandwidth Jump)

All ESP32-P4 boards below share the **ESP32-P4** SoC ([Espressif Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-p4_datasheet_en.pdf)):
- **Cores:** 2× 32-bit RISC-V HP cores @ **360 MHz** (400 MHz on newer silicon revisions) with single-precision FPU + 128-bit PIE SIMD extensions (**~2,490 CoreMark** at 360 MHz, **1.87×** ESP32-S3's 1,330 CoreMark) + 1× RISC-V LP core @ 40 MHz.
- **Internal Memory:** **768 KB HP L2MEM SRAM** (configurable with 128 KB / 256 KB L2 cache) + **96 KB L1 cache** (32 KB I-cache + 64 KB D-cache) + **8 KB zero-wait TCM** + 32 KB LP SRAM.
- **External PSRAM:** **32 MB Hexadeca-SPI (16-line) PSRAM @ 200 MHz DDR** (400 MB/s theoretical; measured `memcpy` **~104–118 MB/s** SRAM↔PSRAM, **~365–758 MB/s** internal SRAM, vs ~35–45 MB/s on ESP32-S3 @ 80 MHz).
- **2D / Display Engine:** **MIPI-DSI** (2-lane up to 1.5 Gbps/lane = 375 MB/s, supports RGB565, RGB666, and **24-bit RGB888** in both Video Mode and Command Mode) + **PPA (Pixel Processing Accelerator)** (hardware 0/90/180/270° rotation, scaling, ARGB8888/RGB888/RGB565 blending & block fill) + **2D-DMA** (pitched 2D stride transfers).
- **SDK:** **ESP-IDF ≥ v5.3 / v5.5** (`esp_lcd`, FreeRTOS, `esp_heap_caps`) and `pioarduino`. Our `render.cpp`, `physics.cpp`, dual-core task notifications, and Python host tools port with **near-zero architectural changes**.

---

#### A1. Tailor Pixels `TBX175EMD-01` (ESP32-P4 AMOLED Eval Board) + `TOH323XVT-01C` (3.23" 262×928 Bar AMOLED) or `TOH240XVT-03CG` (2.4" 450×600 AMOLED)
- **Vendor Links:**
  - Eval Board (`TBX175EMD-01`): [tailorpixels.com — TBX175EMD-01 ESP32-P4 Display Board](https://tailorpixels.com/product/tbx175emd-01-esp32p4-display-board-eval-kit-for-amoled/)
  - 3.23" Bar AMOLED (`TOH323XVT-01C`): [tailorpixels.com — 3.23" Bar AMOLED 262×928 MIPI](https://tailorpixels.com/3-23-inch-bar-amoled-with-on-cell-touch-262x928-mipi/) | [tailordisplays.com Store Listing](https://www.tailordisplays.com/product/3-23-inch-amoled-262x928-pixels-mipi-interface-on-cell-touch-toh323xvt-01c/)
  - 2.4" Rectangular AMOLED (`TOH240XVT-03CG`): [tailorpixels.com — 2.4" Touch OLED 450×600](https://tailorpixels.com/product/2-4-inch-touch-oled-450x600-spi-mipi-qspi/)
  - 1.98" Watch AMOLED (`TOH198XVT-01CG`, 410×502): [tailorpixels.com — 1.98" Touch AMOLED 410×502](https://tailorpixels.com/product/1-98-inch-touch-amoled-display-with-cover-glass-410x502-qspi-mipi/)
- **Price & Availability:** In stock now. `TBX175EMD-01` board: **~$25–$40 USD**; `TOH323XVT-01C` 3.23" bar AMOLED: **~$33.00 USD**; `TOH240XVT-03CG` 2.4" AMOLED: **~$17–$28 USD** (Combined kit **~$58–$73 USD**).
- **Chip:** ESP32-P4 (dual RISC-V @ 360/400 MHz, 768 KB SRAM, 32 MB 16-bit PSRAM @ 200 MHz DDR, PPA 2D accel).
- **Display Specs (`TOH323XVT-01C` — 3.23" Bar AMOLED):**
  - **Size & Geometry:** **3.23" diagonal bar**, Active Area **22.01 × 77.95 mm** (Outline **23.80 × 81.05 × 0.63 mm**) — almost identical length to our 3.16" LCD (74.7 mm AA) but **7 mm narrower** (23.8 mm total width vs 24.5 mm on our 1.91" AMOLED cuff board!).
  - **Resolution & Density:** **262 × 928 px**, **~302 PPI** (84 µm pixel pitch), ~700 cd/m² brightness, true AMOLED blacks (no backlit grey bridge/margin glow!).
  - **Driver IC & Interface:** **Raydium RM690C0** (display) + **ZT2628** (on-cell touch), **1-lane/2-lane MIPI-DSI**, **internal GRAM (Yes — MIPI Command Mode)**, **24-bit RGB888 (16.7M colours)** default initialization on `TBX175EMD-01` (eliminates RGB565 gradient hue banding).
  - _ Compatibility Verification Note:_ `TBX175EMD-01` has a 31-pin 0.3 mm pitch FPC natively wired for Tailor Pixels' 7 standard QSPI/2-lane MIPI AMOLEDs (`TOH198XVT-01CG` 410×502, `TOH204XVT-01CG` 368×448, `TOH240XVT-03CG` 450×600 with CO6300 driver) plus a 2-lane MIPI expansion adapter for panels like `TOH323XVT-01C` (whose exact FPC pin count/mapping should be confirmed with Tailor Pixels when ordering the bundle so they include the matching FPC adapter).
- **Peripherals on `TBX175EMD-01`:** MicroSD (TF) slot (loads `display.cfg` init timings dynamically at boot), USB-C, BOOT/RST buttons. **Missing on base eval board (verified):** No onboard IMU, no external RTC (uses P4 internal LP RTC), no LiPo charger, and no ESP32-C6 radio module on the bare `TBX175EMD-01` PCB (requires I2C IMU breakout for bench testing or pairing `TOH323XVT-01C` with a full-featured ESP32-P4 board).
- **Renderer Speedup Estimate:**
  - **Internal GRAM + MIPI-DSI:** 0 MB/s continuous PSRAM scan-out drain.
  - **Memory Fit:** Because BLE is absent (or on an external C6 over SDIO), ~600+ KB of the 768 KB internal SRAM is free after L2 cache allocation — enough to keep all three `Tube` structs (48 KB), all fizz masks (8 KB), and **two full 928×100×2 B rendering strips (371 KB) in internal SRAM**!
  - **CPU + PPA:** 1.87× CoreMark + hardware FPU + internal-SRAM strips + PPA 90° rotation + DMA2D push → estimated **~85–110 fps pinned** and **~60–75 fps swinging** on 3 tubes (**~2.3–2.7× faster** than S3-LCD-3.16).
- **Porting Effort:** **Low** (ESP-IDF `esp_lcd` MIPI-DSI + PPA driver; `render.cpp` and `physics.cpp` compile unchanged).

---

#### A2. LILYGO `T-Display-P4` (4.1" 568×1232 AMOLED or 4.05" 540×1168 IPS TFT, Full Sensor + Radio Suite)
- **Vendor Links:**
  - Official Store: [lilygo.cc — T-Display-P4](https://lilygo.cc/products/t-display-p4)
  - GitHub Hardware/Firmware Repo: [github.com/Xinyuan-LilyGO/T-Display-P4](https://github.com/Xinyuan-LilyGO/T-Display-P4)
- **Part Numbers / Variants:**
  - **AMOLED Variant:** 4.1" 568×1232 AMOLED, Driver IC **Raydium RM69A10**, Touch **GT9895**.
  - **TFT Variant:** 4.05" 540×1168 IPS LCD, Driver IC **HI8561 / JD9365TG**.
- **Price & Availability:** Available now on LilyGO store & distributors; **$97.40 USD** (4.05" TFT variant) to **$119.30 USD** (4.1" AMOLED variant). *(Note: A cellular sibling, [`T-Display-P4-Air`](https://github.com/Xinyuan-LilyGO/T-Display-P4-Air) with ESP32-C5 + nRF9151, is in evaluation preview and not yet released).*
- **Chip:** **ESP32-P4** (dual RISC-V @ 360/400 MHz, 768 KB SRAM, **32 MB Hexadeca-SPI PSRAM**, 16 MB Flash, PPA 2D accel) + **ESP32-C6** companion chip (Wi-Fi 6 + **BLE 5.0** over SDIO).
- **Display Specs (4.1" AMOLED Variant):**
  - **Size & Aspect:** **4.1" tall bar/strip**, **568 × 1232 px** (~2.17:1 aspect ratio, **~331 PPI**). Board outline is **63 × 109 mm** (pocket/gauntlet terminal size; larger than a narrow wrist cuff, or maskable to a 3-tube window).
  - **Interface & GRAM:** **2-lane MIPI-DSI**. The **RM69A10** AMOLED driver IC integrates **internal GRAM (Command Mode supported)** and accepts **24-bit RGB888 (16.7M colours)** over MIPI-DSI (eliminating 565 hue banding and AMOLED grey-margin bleed). *(The 4.05" HI8561/JD9365TG TFT variant is a RAMless MIPI-DSI video-mode panel).*
- **Peripherals on Board:** **ICM20948 9-axis IMU** (3-axis accel + 3-axis gyro + 3-axis mag on I2C), **PCF8563 RTC** (I2C, directly compatible with our `rtc.cpp` PCF85063 register family with minor tweaks), **BQ27220 battery fuel gauge** + LiPo charger, **ESP32-C6 BLE 5**, ES8311 audio codec, SX1262 LoRa, L76K GPS, microSD, USB-C OTG + JTAG.
- **Renderer Speedup Estimate:**
  - Because **BLE 5 runs entirely on the external ESP32-C6** (and only exchanges small NUS packets over SDIO/UART), the ESP32-P4 loses **0 KB of internal SRAM to the Bluetooth controller** — eliminating the `ble.h` 3-minute reboot window permanently!
  - At our current `820×320` canvas (or native `1232×320` 3-tube sub-window), ESP32-P4's 360–400 MHz RISC-V cores + 200 MHz DDR 16-bit PSRAM (~110 MB/s) + PPA hardware 90° rotation yield **~80–100 fps pinned / ~55–68 fps swinging** at 820×320, or **~55–65 fps pinned / ~38–48 fps swinging** at full 1232 px length (**2.0–2.5× faster** than S3-LCD-3.16).
- **Porting Effort:** **Low** (Official repo uses ESP-IDF v5.5.4+; only IMU driver changes from QMI8658 to ICM20948).

---

#### A3. Waveshare `ESP32-P4-NANO` (`SKU 29026`) or `ESP32-P4-Module-DEV-KIT` + Modular MIPI-DSI Bar Displays
- **Vendor Links:**
  - `ESP32-P4-NANO` (`SKU 29026`, **$18.99 USD**): [waveshare.com/esp32-p4-nano.htm](https://www.waveshare.com/esp32-p4-nano.htm) | [Wiki](https://www.waveshare.com/wiki/ESP32-P4-NANO)
  - `ESP32-P4-Module-DEV-KIT` (**$23.99 USD**): [waveshare.com/esp32-p4-module-dev-kit.htm](https://www.waveshare.com/esp32-p4-module-dev-kit.htm) | [Wiki](https://www.waveshare.com/wiki/ESP32-P4-Module-DEV-KIT)
  - Compatible Waveshare 22-pin MIPI-DSI Displays:
    - `2.8inch DSI LCD` (480×640 IPS, **~$35.99 USD**): [waveshare.com/wiki/2.8inch_DSI_LCD](https://www.waveshare.com/wiki/2.8inch_DSI_LCD)
    - `6.25inch DSI LCD` (`SKU 28918` / `35000`, **720×1560 IPS bar**, **~$52.99 USD**): [waveshare.com/6.25inch-dsi-lcd.htm](https://www.waveshare.com/6.25inch-dsi-lcd.htm)
    - Also compatible via MIPI-DSI FPC adapter with 3.16" **320×820 ST7701S MIPI-DSI** panels or Tailor Pixels' **3.23" 262×928 RM690C0 MIPI AMOLED**.
- **Chip:** ESP32-P4NRW32 (dual RISC-V @ 360/400 MHz, 768 KB SRAM, **32 MB Hexadeca-SPI PSRAM**) + onboard **ESP32-C6-MINI-1** (Wi-Fi 6 + BLE 5).
- **Peripherals:** USB-C JTAG/UART, USB OTG, microSD (SDIO 3.0), audio mic/speaker, 22-pin Raspberry Pi 5-compatible 2-lane MIPI-DSI connector, GPIO header. **Missing onboard:** IMU and external RTC (easily wired via I2C header; `ESP32-P4-NANO` is compact at **65.0 × 32.0 mm**).
- **Renderer Speedup Estimate:** Driving a 320×820 MIPI-DSI panel (24-bit RGB888 video mode) on `ESP32-P4-NANO`: the 24-bit framebuffer is 787 KB in PSRAM, scanning out at 47 MB/s — only **~12% of P4's 400 MB/s peak PSRAM bus** (vs >50% on S3). Combined with PPA hardware rotation and 360–400 MHz cores + L2 cache, achieves **~75–95 fps pinned / ~52–65 fps swinging** (**~2.0–2.3× faster** than S3-LCD-3.16) while curing RGB565 hue banding via 24-bit MIPI-DSI output.
- **Porting Effort:** **Low** (ESP-IDF `esp_lcd_st7701` has native MIPI-DSI support in IDF v5.3+).

---

#### A4. All-in-One ESP32-P4 4.3"–5.0" Touch Devkits (Guition, Waveshare, Wireless-Tag, M5Stack)
For rapid firmware bench development on ESP32-P4 with an integrated screen (can render our `800×320` or `820×320` 3-tube canvas 1:1 on the screen):
1. **Guition `JC4880P443C_I_W` (`JC-ESP32P4-M3`):**
   - **Link & Price:** [AliExpress Listing](https://www.aliexpress.com/item/3256809437179899.html) | [Community BSP & Pinout](https://community.home-assistant.io/t/guition-esp32-p4-jc4880p443-working-config/712396) — **$22–$32 USD** (in stock).
   - **Specs:** ESP32-P4NRW32 (32 MB PSRAM, 16 MB Flash) + ESP32-C6 (BLE 5), **4.3" 480×800 IPS** (~217 PPI) driven by **ST7701S over 2-lane MIPI-DSI** (RAMless video mode, supports **24-bit RGB888**), GT911 touch, LiPo charger + battery header, microSD, ES8311 audio. *(No onboard IMU/RTC — attach QMI8658 over exposed GPIO header).*
2. **Waveshare `ESP32-P4-WIFI6-Touch-LCD-4.3`:**
   - **Link & Price:** [waveshare.com/esp32-p4-wifi6-touch-lcd-4.3.htm](https://www.waveshare.com/esp32-p4-wifi6-touch-lcd-4.3.htm) — **$33.99 USD** (in stock).
   - **Specs:** ESP32-P4 + ESP32-C6, 32 MB PSRAM, 32 MB Flash, **4.3" 480×800 IPS MIPI-DSI (ST7701, 24-bit RGB888)**, GT911 touch, audio, microSD, 40-pin GPIO header.
3. **Wireless-Tag `WT32P4C5-43S`:**
   - **Link & Price:** [CNX Software Coverage](https://www.cnx-software.com/2026/10/4.3-inch-dual-chip-ESP32-P4-and-ESP32-C5-Wi-Fi6-integrated-touch-display/) | [shop.wireless-tag.com](https://shop.wireless-tag.com/) — **~$32–$37 USD**.
   - **Specs:** ESP32-P4 + **ESP32-C5** (dual-band 2.4/5 GHz Wi-Fi 6 + BLE 5), 32 MB PSRAM, 4.3" 800×480 MIPI-DSI.
4. **M5Stack `Tab5` (`K145` / `C145`):**
   - **Link & Price:** [docs.m5stack.com/en/app/Tab5](https://docs.m5stack.com/en/app/Tab5) — **$65–$75 USD** (base) / **~$115 USD** (with NP-F550 battery).
   - **Specs:** ESP32-P4 (400 MHz, 32 MB PSRAM, 16 MB Flash) + ESP32-C6-MINI-1U (BLE 5.2), **5.0" 1280×720 IPS MIPI-DSI** (~294 PPI, **ILI9881C / ST7123** driver, 24-bit RGB888, RAMless), **BMI270 6-axis IMU**, **RX8130CE RTC** (with supercap backup), INA226 power monitor, battery charging. **Best turn-key ESP32-P4 bench rig** because IMU, RTC, BLE, battery monitor, and 720×1280 MIPI-DSI screen are all integrated and documented out of the box, though too large (5") for a wrist cuff.

---

### Category B: Better AMOLED / Bar Panels on ESP32-S3 (Zero Porting Effort, Eliminates RGB Scan-Out via Internal GRAM)

Why do our two existing ESP32-S3 boards behave so differently (`ESP32-S3-AMOLED-1.91` hits **61.2 fps** on 2 tubes and **35.5 fps** on 3 tubes, while `ESP32-S3-LCD-3.16` drops to **27.6 fps** swinging)?
Because **QSPI AMOLED controllers (`SH8601`, `RM67162`, `RM690B0`, `CO5300`) have internal GRAM!** They do not drain 32 MB/s of PSRAM bandwidth for continuous RGB scan-out, and they support **24-bit RGB888** pixel writes over QSPI (fixing 565 hue banding). If we want a larger/wider display than the 1.91" AMOLED (`536×240`) while keeping 100% compatibility with our existing ESP32-S3 toolchain:

#### B1. Waveshare `ESP32-S3-Touch-AMOLED-2.41` (`SKU 30563` / `30589`) & LilyGO `T4-S3` (`H703`)
- **Vendor Links:**
  - Waveshare (`SKU 30563` bare / `30589` cased): [waveshare.com/esp32-s3-touch-amoled-2.41.htm](https://www.waveshare.com/esp32-s3-touch-amoled-2.41.htm) | [Wiki](https://www.waveshare.com/wiki/ESP32-S3-Touch-AMOLED-2.41) — **~$39.99–$44.99 USD** (in stock).
  - LilyGO `T4-S3` (`SKU H703`): [lilygo.cc/products/t4-s3](https://lilygo.cc/products/t4-s3) | [GitHub](https://github.com/Xinyuan-LilyGO/LilyGO-AMOLED-Series) — **~$55–$60 USD** (in stock, no onboard IMU on T4-S3; **prefer the Waveshare SKU 30563** which includes QMI8658 IMU + PCF85063 RTC).
- **Chip:** ESP32-S3R8 (2× LX7 @ 240 MHz, 512 KB SRAM, 8 MB Octal PSRAM, 16 MB Flash, BLE 5).
- **Display Specs:** **2.41" AMOLED**, **600 × 450 px** (~311 PPI, Active Area **48.96 × 36.72 mm** — 4.7 mm longer than the 1.91" AMOLED and 1.85× taller, easily fitting **three 10-8-6 mm tubes** with generous leather bridges!), **800 cd/m²**, Driver IC **Raydium RM690B0** over **QSPI**, **internal GRAM (Yes!)**, supports **RGB565 and 24-bit RGB888 (16.7M colours)**.
- **Peripherals (Waveshare `SKU 30563`):** **QMI8658 6-axis IMU**, **PCF85063 RTC**, **AXP2101 PMU + LiPo header**, microSD, USB-C — **exact same IMU and RTC chips as our current `lcd316` firmware!**
- **Renderer Speedup Estimate vs `ESP32-S3-LCD-3.16`:**
  1. **Zero scan-out bandwidth drain:** Eliminates the 32 MB/s RGB DMA read from PSRAM (`render` on PSRAM strips runs ~20–25% faster without bus contention).
  2. **27% fewer columns than 820 px (`600` vs `820`):** Directly cuts per-pixel tube render time by **~27%** (`29.9 ms → ~21.8 ms` on the critical `m+s` core during a swing).
  3. **No 525 KB portrait PSRAM framebuffer needed:** Strips push directly over 40–80 MHz QSPI DMA into the RM690B0's internal GRAM (and RM690B0 supports hardware `MADCTL` orientation + window addressing, eliminating the software quarter-turn `push`!).
  - **Resulting Speed:** Estimated **~55–62 fps pinned** and **~38–44 fps swinging** on 3 tubes (**+40–55% faster** than `ESP32-S3-LCD-3.16`), hitting our `>= 30 fps swinging` goal with comfortable headroom and **true AMOLED blacks + 24-bit RGB888 mode**.
- **Porting Effort:** **Minimal (< 1 day)** — identical MCU, IMU (`QMI8658`), and RTC (`PCF85063`); only swaps `esp_lcd_sh8601` init table to `RM690B0` and sets `PANEL_W=600`.

---

#### B2. Waveshare `ESP32-S3-Touch-AMOLED-2.06` (`SKU 31957` Watch Kit) & LilyGO `T-Watch Ultra`
- **Vendor Links:**
  - Waveshare (`SKU 31957` w/ battery & straps, **~$36.99–$42.99 USD**): [waveshare.com/esp32-s3-touch-amoled-2.06.htm](https://www.waveshare.com/esp32-s3-touch-amoled-2.06.htm)
  - LilyGO `T-Watch Ultra` (**~$78–$95 USD**): [lilygo.cc/products/t-watch-ultra](https://lilygo.cc/products/t-watch-ultra)
- **Display Specs:** **2.06" Wearable AMOLED**, **410 × 502 px** (~314 PPI, Active Area **33.09 × 40.51 mm**, Case **50.8 × 42.0 mm**), Driver IC **Chipone CO5300** over **QSPI**, **internal GRAM (Yes)**, **24-bit RGB888 (16.7M colours)**.
- **Peripherals (Waveshare `31957`):** ESP32-S3R8 (8 MB OPI PSRAM, 32 MB Flash), **QMI8658 IMU**, **PCF85063 RTC**, **AXP2101 PMU + LiPo battery**, ES8311 audio, watch case + straps. *(LilyGO T-Watch Ultra has BHI260AP IMU, PCF8563 RTC, AXP2101, SX1262 LoRa, GPS).*
- **Renderer Speedup Estimate:** At 502 px tube length (vs 820 px on `lcd316`), pixel count per tube is **39% lower**, and CO5300 has internal GRAM (no RGB scan-out). Hits **~60+ fps pinned / ~45–50 fps swinging** on 3 tubes. Trade-off: 40.5 mm tube length is 3.7 mm shorter than the 1.91" AMOLED (44.2 mm) and much shorter than the 3.16" bar (74.7 mm), making the tubes look stubbier (aspect ~5:4 overall).

---

#### B3. LilyGO `T-Display-S3 Long` (`SKU H672`, 3.4" 180×640 QSPI Bar LCD with Internal GRAM)
- **Vendor Link:** [lilygo.cc/products/t-display-s3-long](https://lilygo.cc/products/t-display-s3-long) | [GitHub](https://github.com/Xinyuan-LilyGO/T-Display-S3-Long) — **~$27–$33 USD** (in stock).
- **Chip:** ESP32-S3R8 (240 MHz, 8 MB OPI PSRAM, 16 MB Flash, BLE 5).
- **Display Specs:** **3.4" Ultra-Wide Bar IPS TFT**, **180 × 640 px** (~292 PPI, 32:9 aspect ratio), Driver IC **AXS15231B** over **QSPI**, **internal GRAM (Yes! Rare for a 3.4" bar LCD)**, supports RGB565 / RGB666 (262K colours).
- **Peripherals:** LiPo JST 1.25 charger, USB-C, BOOT/RST. **Missing onboard:** No IMU and no external RTC (requires external I2C QMI8658 breakout).
- **Renderer Speedup Estimate:** Because the **AXS15231B integrates internal GRAM over QSPI**, it completely avoids the ST7701S's 32 MB/s continuous PSRAM scan-out penalty! Combined with 640 px length (22% shorter than 820 px) and 180 px height (fits three 50–54 px tubes), it estimates **~55–65 fps pinned / ~38–45 fps swinging** on the same ESP32-S3 chip. However, 180 px height limits tube thickness (`≤ 60 px` per tube on a 3-tube face), IPS black levels still glow, and an external IMU must be wired.

---

### Category C: High-Performance ARM Cortex-M Crossover & Graphics Devkits (STM32, NXP i.MX RT, Renesas, Ambiq)

We already have an `STM32H573I-DK` benchmark plan (`docs/h573-bench-plan.md`, single-core Cortex-M33 @ 250 MHz, 640 KB SRAM, 1,023 CoreMark). While the H573 is 3–4× more power-efficient per MHz than ESP32-S3, its single core is slower than two S3 cores (1,023 vs 1,330 CoreMark) and its 240×240 screen is unsuitable. Below are the **much faster ARM MCUs** with multi-MB internal SRAM, SIMD/dual-issue cores, and MIPI-DSI/GPU2D engines:

| Board / SKU & Link | Price & Stock | MCU, Cores, Clock & CoreMark | Internal SRAM & External RAM | Display Included & Interface | 2D / GPU Accel | Radio / IMU / RTC / Battery |
|---|---|---|---|---|---|---|
| **STM32N6570-DK**<br>[st.com](https://www.st.com/en/evaluation-tools/stm32n6570-dk.html) | **~$290–$325**<br>In stock (Mouser/DigiKey) | **STM32N657X0H3Q**<br>1× **Cortex-M55 @ 800 MHz** + **Helium MVE SIMD** (~5,100 CoreMark, **3.8× S3**) | **4.2 MB contiguous SRAM** + 32 MB Hexadeca-SPI PSRAM (400 MB/s) | **5.0" 800×480 TFT** (Parallel RGB888, RAMless) | **NeoChrom 2.5D GPU** + DMA2D + LTDC | No BLE, **ISM330DLC 6-axis IMU**, internal RTC, no LiPo |
| **STM32H7S78-DK**<br>[st.com](https://www.st.com/en/evaluation-tools/stm32h7s78-dk.html) | **~$190–$210**<br>In stock | **STM32H7S7L8H6H**<br>1× **Cortex-M7 @ 600 MHz** dual-issue (~3,200 CoreMark, **2.4× S3**) | **620 KB SRAM** + 32 MB Hexadeca-SPI PSRAM @ 200 MHz DDR (400 MB/s) | **5.0" 800×480 TFT** (RGB888, RAMless) | **NeoChrom 2.5D GPU** + DMA2D + LTDC | Wi-Fi/BLE module (MXCHIP), no IMU, internal RTC |
| **STM32U5G9J-DK2** / **DK1**<br>[st.com](https://www.st.com/en/evaluation-tools/stm32u5g9j-dk2.html) | **~$150–$190**<br>In stock | **STM32U5G9ZJT6Q**<br>1× Cortex-M33 @ 160 MHz (~650 CoreMark, **0.49× S3**) | **3.0 MB internal SRAM** (zero external PSRAM needed!) | DK2: **5.0" 800×480 RGB888**<br>DK1: **2.47" 480×480 round MIPI-DSI** | **NeoChrom VG 2.5D GPU** + DMA2D | No BLE, no IMU, internal ultra-low-power RTC |
| **NXP MIMXRT1170-EVKB**<br>[nxp.com](https://www.nxp.com/design/design-center/development-boards-and-designs/i-mx-eval-boards/i-mx-rt1170-evaluation-kit-mimxrt1170-evkb:MIMXRT1170-EVKB) | **~$205–$240**<br>In stock ( panel ~$80 extra if unbundled) | **i.MX RT1176**<br>**1× Cortex-M7 @ 1 GHz + 1× Cortex-M4 @ 400 MHz** (**~6,468 CoreMark, 4.8× S3!**) | **2.0 MB internal SRAM** (incl. 512 KB M7 TCM + 256 KB M4 TCM) + 64 MB SDRAM | Optional **5.5" 720×1280 IPS (`RK055HDMIPI4MA0`)**, 2-lane MIPI-DSI, 24-bit RGB888 | **Vivante GC355 VGLite 2D GPU** + **PXP** (hardware 90° rot + blend) | M.2 Wi-Fi/BLE slot, **FXOS8700 6-axis sensor** (accel+mag, no gyro), internal SNVS RTC |
| **NXP MIMXRT595-EVK**<br>[nxp.com](https://www.nxp.com/design/design-center/development-boards-and-designs/i-mx-eval-boards/i-mx-rt500-evaluation-kit:MIMXRT595-EVK) | **~$145**<br>In stock (display sold separately) | **i.MX RT595S**<br>1× Cortex-M33 @ 275 MHz + Fusion F1 DSP (~1,100 CoreMark) | **5.0 MB internal SRAM** + Octal PSRAM | MIPI-DSI connector for **1.2" 390×390 round AMOLED (`G1120B0MIPI`)** or **5.5" 720×1280 (`RK055HDMIPI4MA0`)** | **Vivante VGLite 2D GPU** + MIPI-DSI Command/Video | M.2 slot, **FXOS8700**, internal RTC |
| **NXP MIMXRT700-EVK**<br>[nxp.com](https://www.nxp.com/design/design-center/development-boards-and-designs/i-mx-eval-boards/i-mx-rt700-evaluation-kit:MIMXRT700-EVK) | **~$188**<br>In stock | **i.MX RT798S**<br>**2× Cortex-M33 (325 + 250 MHz)** + HiFi4 DSP + HiFi1 DSP | **7.5 MB internal SRAM** + 64 MB HyperRAM (xSPI) | MIPI-DSI connector (supports `RK055HDMIPI4MA0` 5.5" 720×1280) | **Vivante 2.5D GPU** (OpenVG 1.1) | M.2 Wi-Fi/BLE, accelerometer, RTC |
| **Renesas EK-RA8D1**<br>[renesas.com](https://www.renesas.com/en/products/microcontrollers-microprocessors/ra-cortex-m-mcus/ek-ra8d1-evaluation-kit-ra8d1-mcu-group) | **~$300–$332**<br>In stock (includes 4.5" DSI screen!) | **R7FA8D1BHECBD**<br>1× **Cortex-M85 @ 480 MHz** + **Helium MVE SIMD** (**~3,067 CoreMark, 2.3× S3 on 1 core!**) | **1.0 MB internal SRAM** (incl. TCM) + 64 MB SDRAM | **Included 4.5" 480×854 IPS (`RTK7EK8D1B000000BE`)**, 2-lane MIPI-DSI, **24-bit RGB888** | **Dave2D (DRW) GPU** + GLCDC | No BLE, no onboard IMU, internal RTC |
| **Ambiq Apollo4 Plus / Apollo510 EVB**<br>[digikey.com (`AP510EVB`)](https://www.digikey.com/en/products/detail/ambiq-micro-inc/AP510EVB/2332517) | **$250 + $100** display shield (`AP510DISP`) | **Apollo510:** Cortex-M55 @ 250 MHz + Helium MVE<br>**Apollo4 Plus:** Cortex-M4F @ 192 MHz | **Apollo510:** 4 MB SRAM + 4 MB MRAM<br>**Apollo4:** 2.75 MB SRAM + 2 MB MRAM | **1.4" 454×454 or 468×468 round AMOLED** (MIPI-DSI 1.2 / QSPI, GRAM) | **NemaGFX 2.5D GPU** (`graphiqSPOT`) | **BLE 5.1/5.4** (on Blue variants), no IMU on shield, ultra-low-power RTC |

#### Assessment of ARM Candidates for Our Renderer (`render.cpp` + `physics.cpp`):
1. **Why `STM32U5G9J-DK2` and `MIMXRT595-EVK` are NOT faster for our renderer despite huge SRAM & GPUs:**
   - Both have single-core Cortex-M33 CPUs at 160–275 MHz. Because our per-pixel meniscus/residue/refraction/fizz loops run in software on the CPU, a single 160 MHz M33 (`STM32U5G9`) delivers only ~650 CoreMark — **slower than a single ESP32-S3 core**, even with all buffers in its 3 MB internal SRAM! Their NeoChrom / VGLite GPUs only help with the final rotation/blit, not `renderTube`.
2. **Where ARM Truly Shines (`NXP MIMXRT1170-EVKB`, `STM32N6570-DK`, `Renesas EK-RA8D1`):**
   - **`MIMXRT1170-EVKB` (1 GHz Cortex-M7 + 400 MHz Cortex-M4, 2 MB SRAM):** Maps directly to our dual-core schedule (`renderTube(0)` on the 1 GHz dual-issue M7 with 512 KB zero-wait DTCM; `renderTube(1)` + `renderTube(2)` on the 400 MHz M4 or split on the M7, while the **PXP** hardware engine rotates strips 90° and converts RGB565→RGB888 in the background). Estimated **~120–160 fps pinned / ~90–115 fps swinging** (**3.5–4× faster than S3**).
   - **`Renesas EK-RA8D1` (480 MHz Cortex-M85 + Helium MVE, 1 MB SRAM, bundled 4.5" 480×854 MIPI-DSI bar-ish IPS):** Even without Helium intrinsics, scalar C++ on the dual-issue M85 @ 480 MHz with 1 MB internal SRAM (no PSRAM needed for strips + `Tube` structs!) is **~2.2× faster than S3** (**~60+ fps swinging**); with Helium MVE vectorization of `spriteRun*` and `bandRow`, **~3.5–4× faster**.
   - **Why they rank below ESP32-P4 for this project right now:** Cost (**$190–$330** vs **$19–$119** for ESP32-P4 kits), massive non-wearable PCB footprints, missing onboard IMU/BLE/LiPo charging, and **high porting effort** (new SDK, linker scripts, MIPI-DSI/LTDC bringup, external BLE module integration).

---

### Category D: Small Linux / RTOS SoCs, RISC-V Vector Boards & RP2350

1. **Bouffalo Lab `BL808` — Sipeed `M1s Dock` ([wiki.sipeed.com](https://wiki.sipeed.com/hardware/en/maix/m1s/m1s_dock.html), ~$15–$20 USD):**
   - **Specs:** Triple-core RISC-V: **64-bit XuanTie C906 @ 480 MHz with RVV 0.7.1 (128-bit Vector FPU)** + 32-bit E907 @ 320 MHz + E902 @ 160 MHz, **64 MB embedded pSRAM** on-die (16-bit @ ~160 MHz), RGB/SPI display interface, Wi-Fi 4 + BLE 5.
   - **Catch:** Bundled display is a tiny 1.69" 240×280 SPI screen; no MIPI-DSI; Bouffalo SDK supporting asymmetric dual-core shared-memory synchronization between the 64-bit C906 and 32-bit E907 is poorly documented and fragile.
2. **Rockchip `RV1106G3` — `Luckfox Pico Ultra` ([luckfox.com](https://www.luckfox.com/index.php?route=product/product&product_id=121), ~$19–$29 USD) & Allwinner `T113-S3` (`MangoPi MQ-Dual`, ~$12–$18 USD):**
   - **Specs:** `RV1106`: Single Cortex-A7 @ 1.2 GHz with NEON + FPU + 256 MB DDR3L on-chip, RGB888 parallel LCD interface (typically bundled with a 4" 480×480 RGB screen). `T113-S3`: **Dual Cortex-A7 @ 1.2 GHz** with NEON + 128 MB DDR3 on-chip + RGB888/MIPI-DSI.
   - **Speed vs Effort:** Dual Cortex-A7 @ 1.2 GHz with NEON SIMD and DDR3 memory bandwidth (>1,000 MB/s) would run our renderer at **>150 fps**, and RGB888 eliminates 565 hue banding. However, they run embedded Linux (1.5–3 s boot time, high idle power ~250–400 mW, no onboard IMU/RTC/LiPo watch PMIC) and require a full Linux `drm`/`fbdev` + userspace BLE port (**High porting effort**).
3. **Raspberry Pi `RP2350` — Waveshare `RP2350-Touch-AMOLED-2.41` ([waveshare.com](https://www.waveshare.com/rp2350-touch-amoled-2.41.htm), $46.99) & `RP2350-Touch-AMOLED-1.8` ([waveshare.com](https://www.waveshare.com/rp2350-touch-amoled-1.8.htm), $25.99):**
   - **Specs:** Dual Cortex-M33 @ 150 MHz, 520 KB SRAM, 2 MB or 8 MB **QSPI PSRAM** (4-bit bus @ 100–133 MHz = **~33–50 MB/s**, **half** the bandwidth of ESP32-S3's Octal PSRAM!), **no BLE/Wi-Fi**, no 2D accelerator. See §4 ("Tempting-but-Wrong") below.

---

## 3. Master Comparison Table & Renderer Speedup Estimates

Baseline for speedup column: **Waveshare ESP32-S3-LCD-3.16** (`lcd316@320w10-8-6+t3`, 80 MHz Octal PSRAM, fast mode): **40.7 fps pinned / 27.6 fps swinging**.

| Rank / Candidate | SKU & Vendor Link | Price | MCU, Cores, Clock & SRAM | External RAM & Bandwidth | Display Size, Res, PPI, Tech & Driver IC | Interface, GRAM & Colour Depth | 2D / GPU Accel | Radio, IMU, RTC, Battery | SDK & Port Effort | Est. Speed on 3 Tubes (Pinned / Swing) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Baseline 1 (Current Bar)** | **Waveshare ESP32-S3-LCD-3.16**<br>`SKU 28608` ([Link](https://www.waveshare.com/esp32-s3-lcd-3.16.htm)) | $26–$32 | ESP32-S3R8<br>2× LX7 @ 240 MHz<br>512 KB SRAM | 8 MB Octal PSRAM @ 80 MHz<br>(~55 MB/s; -32 MB/s scanout) | 3.16" Bar IPS<br>320×820 (~279 PPI)<br>ST7701S | 16-bit RGB Parallel<br>**No GRAM**<br>**16-bit RGB565** (bands) | None (GDMA only) | BLE 5, QMI8658, PCF85063, LiPo | ESP-IDF / Arduino<br>*(Current)* | **40.7 / 27.6 fps**<br>*(1.0× ref)* |
| **Baseline 2 (Current Cuff)** | **Waveshare ESP32-S3-AMOLED-1.91**<br>`SKU 28872` ([Link](https://www.waveshare.com/esp32-s3-amoled-1.91.htm)) | $26–$34 | ESP32-S3R8<br>2× LX7 @ 240 MHz<br>512 KB SRAM | 8 MB Octal PSRAM @ 80 MHz<br>(~55 MB/s; 0 scanout) | 1.91" Bar AMOLED<br>240×536 (~323 PPI)<br>SH8601 / RM67162 | QSPI @ 40 MHz<br>**Yes (GRAM)**<br>16-bit / **24-bit RGB888** | None | BLE 5, QMI8658, No ext RTC, LiPo | ESP-IDF / Arduino<br>*(Current)* | **~52 / 35.5 fps** (t3)<br>*(61.2 fps on 2 tubes)* |
| **#1 Top Pick (All-in-One P4 Bar AMOLED)** | **LILYGO T-Display-P4 (AMOLED)**<br>([Link](https://lilygo.cc/products/t-display-p4)) | **$119**<br>*(TFT: $97)* | **ESP32-P4**<br>2× RV32 @ 360–400 MHz<br>**768 KB SRAM** + L1/L2 | **32 MB 16-bit PSRAM @ 200 MHz DDR**<br>(~115 MB/s; 400 MB/s peak) | **4.1" Bar AMOLED**<br>**568×1232 (~331 PPI)**<br>**Raydium RM69A10** | 2-lane MIPI-DSI<br>**Yes (GRAM)**<br>**24-bit RGB888** | **PPA** (90° rot, scale, blend) + 2D-DMA + PIE SIMD | **ESP32-C6 BLE 5**, **ICM20948 9-axis**, **PCF8563 RTC**, LiPo + BQ27220 | ESP-IDF v5.5<br>**Low Effort** | **~85 / 62 fps** (@820w)<br>**~60 / 44 fps** (@1232w)<br>**(~2.2× faster)** |
| **#2 Top Pick (True Wrist-Bar AMOLED + P4)** | **Tailor Pixels TBX175EMD-01 + TOH323XVT-01C**<br>([Board](https://tailorpixels.com/product/tbx175emd-01-esp32p4-display-board-eval-kit-for-amoled/) / [Panel](https://tailorpixels.com/3-23-inch-bar-amoled-with-on-cell-touch-262x928-mipi/)) | **~$65**<br>($32 + $33) | **ESP32-P4**<br>2× RV32 @ 360–400 MHz<br>**768 KB SRAM** + L1/L2 | **32 MB 16-bit PSRAM @ 200 MHz DDR**<br>(~115 MB/s; 0 scanout) | **3.23" Bar AMOLED**<br>**262×928 (~302 PPI)**<br>AA: 22.0×78.0 mm<br>**Raydium RM690C0** | MIPI-DSI<br>**Yes (GRAM)**<br>**24-bit RGB888** | **PPA** (90° rot, blend) + 2D-DMA + PIE SIMD | No C6/IMU/RTC/LiPo on eval PCB *(add via I2C or use P4-NANO)* | ESP-IDF v5.5<br>**Low Effort** | **~95 / 68 fps**<br>**(~2.4× faster)** |
| **#3 Top Pick (Drop-In S3 AMOLED Upgrade)** | **Waveshare ESP32-S3-Touch-AMOLED-2.41**<br>`SKU 30563` ([Link](https://www.waveshare.com/esp32-s3-touch-amoled-2.41.htm)) | **$40–$45** | ESP32-S3R8<br>2× LX7 @ 240 MHz<br>512 KB SRAM | 8 MB Octal PSRAM @ 80 MHz<br>(~55 MB/s; **0 scanout**) | **2.41" AMOLED**<br>**600×450 (~311 PPI)**<br>AA: 49.0×36.7 mm<br>**Raydium RM690B0** | QSPI @ 40–80 MHz<br>**Yes (GRAM)**<br>**24-bit RGB888** & 565 | None (GDMA) | **BLE 5**, **QMI8658 IMU**, **PCF85063 RTC**, **AXP2101 LiPo** | ESP-IDF / Arduino<br>**Trivial (<1d)** | **~58 / 41 fps**<br>**(~1.5× faster)** |
| **#4 Top Pick (Modular P4 + DSI Bar)** | **Waveshare ESP32-P4-NANO (`SKU 29026`) + MIPI-DSI Panel**<br>([Link](https://www.waveshare.com/esp32-p4-nano.htm)) | **$19** + panel ($28–$53) | **ESP32-P4**<br>2× RV32 @ 360–400 MHz<br>**768 KB SRAM** | **32 MB 16-bit PSRAM @ 200 MHz DDR**<br>(~115 MB/s) | Pair w/ **320×820 ST7701S DSI**, **6.25" 720×1560 DSI** (`SKU 28918`), or **4.3" 480×800** | 2-lane MIPI-DSI<br>Video/Cmd Mode<br>**24-bit RGB888** | **PPA** (90° rot, blend) + 2D-DMA | **ESP32-C6 BLE 5**; add I2C QMI8658 + RTC + LiPo | ESP-IDF v5.5<br>**Low Effort** | **~85 / 58 fps** (@320×820)<br>**(~2.1× faster)** |
| **#5 Top Pick (Budget P4 All-in-One Bench)** | **Guition JC4880P443C_I_W** *(or Waveshare P4-4.3)*<br>([Guition](https://www.aliexpress.com/item/3256809437179899.html) / [Waveshare](https://www.waveshare.com/esp32-p4-wifi6-touch-lcd-4.3.htm)) | **$24–$34** | **ESP32-P4**<br>2× RV32 @ 360–400 MHz<br>**768 KB SRAM** | **32 MB 16-bit PSRAM @ 200 MHz DDR**<br>(~115 MB/s) | **4.3" IPS**<br>**480×800 (~217 PPI)**<br>ST7701S | 2-lane MIPI-DSI<br>No GRAM<br>**24-bit RGB888** | **PPA** (90° rot, blend) + 2D-DMA | **ESP32-C6 BLE 5**, LiPo charger *(no IMU/RTC — wire via GPIO)* | ESP-IDF v5.5<br>**Low Effort** | **~80 / 56 fps** (@800×320)<br>**(~2.0× faster)** |
| **#6 (Full-Feature P4 Tablet Bench)** | **M5Stack Tab5 (`K145`)**<br>([Link](https://docs.m5stack.com/en/app/Tab5)) | **$65–$75** | **ESP32-P4**<br>2× RV32 @ 400 MHz<br>**768 KB SRAM** | **32 MB 16-bit PSRAM @ 200 MHz DDR** | **5.0" IPS**<br>720×1280 (~294 PPI)<br>ST7123 / ILI9881C | 2-lane MIPI-DSI<br>No GRAM<br>**24-bit RGB888** | **PPA** + 2D-DMA | **ESP32-C6 BLE 5.2**, **BMI270 IMU**, **RX8130CE RTC**, Battery | ESP-IDF v5.5<br>**Low Effort** | **~82 / 57 fps** (@820×320 window)<br>**(~2.1× faster)** |
| **#7 (Fastest Non-Linux Dual-Core MCU)** | **NXP MIMXRT1170-EVKB**<br>([Link](https://www.nxp.com/design/design-center/development-boards-and-designs/i-mx-eval-boards/i-mx-rt1170-evaluation-kit-mimxrt1170-evkb:MIMXRT1170-EVKB)) | **$205–$240** (+ panel) | **i.MX RT1176**<br>**M7 @ 1 GHz + M4 @ 400 MHz**<br>**2 MB SRAM** (768 KB TCM) | 64 MB SDRAM | Optional **5.5" 720×1280 IPS** (`RK055HDMIPI4MA0`) | 2-lane MIPI-DSI<br>**24-bit RGB888** | **Vivante GC355 VGLite** + **PXP** (rot/blend) | M.2 BLE slot, FXOS8700 (no gyro), internal RTC | MCUXpresso / Zephyr<br>**High Effort** | **~140 / 100 fps**<br>**(~3.6× faster)** |
| **#8 (Fastest Single-Core Helium SIMD)** | **Renesas EK-RA8D1**<br>([Link](https://www.renesas.com/en/products/microcontrollers-microprocessors/ra-cortex-m-mcus/ek-ra8d1-evaluation-kit-ra8d1-mcu-group)) | **$300–$332** *(w/ screen)* | **RA8D1**<br>**1× Cortex-M85 @ 480 MHz + Helium MVE**<br>**1 MB SRAM** | 64 MB SDRAM | **Included 4.5" IPS**<br>**480×854 (~218 PPI)** | 2-lane MIPI-DSI<br>**24-bit RGB888** | **Dave2D (DRW)** + Helium MVE SIMD | No BLE, no IMU, internal RTC | Renesas FSP / Zephyr<br>**High Effort** | **~90 / 60 fps** (scalar)<br>**~140 / 95 fps** (Helium) |

---

## 4. Ranked Top 5 Recommendations

### 🥇 #1. LILYGO `T-Display-P4` (4.1" 568×1232 AMOLED Variant, `RM69A10`) — Best Complete ESP32-P4 Development Platform
- **Why it wins for R&D and high-end gauntlet/pocket builds:** It is the **only shipping board** that combines **ESP32-P4** (dual 360–400 MHz RISC-V, 768 KB SRAM, 32 MB 200 MHz DDR 16-bit PSRAM, PPA 2D rotation/blend engine), a **high-density ~2.17:1 bar-aspect AMOLED (`568×1232`, 331 PPI, Raydium RM69A10 with internal GRAM and 24-bit RGB888 over MIPI-DSI)**, **ESP32-C6 BLE 5**, **ICM20948 9-axis IMU**, **PCF8563 RTC**, and **LiPo charging + BQ27220 fuel gauge** on a single PCB ([lilygo.cc](https://lilygo.cc/products/t-display-p4)).
- **What it fixes immediately:**
  1. **Doubles swinging frame rate** (`27.6 → ~62 fps` at 820 px tube length, or `~44 fps` at full 1232 px length).
  2. **Eliminates the BLE reboot window (`ble.h`):** NimBLE runs on the ESP32-C6 companion chip, freeing ~46 KB of internal SRAM permanently on the P4.
  3. **Eliminates the software quarter-turn `push`:** The ESP32-P4 **PPA SRM** hardware engine rotates strips 90° and converts `RGB565 → RGB888` in DMA hardware.
  4. **Eliminates 565 hue banding & LCD backlight bleed:** 24-bit RGB888 MIPI-DSI + true AMOLED blacks.

### 🥈 #2. Tailor Pixels `TBX175EMD-01` (ESP32-P4 Board) + `TOH323XVT-01C` (3.23" 262×928 Bar AMOLED, `RM690C0`) — Best Physical Form-Factor Match for the Wrist Cuff
- **Why it wins on display geometry:** If the 4.1" LilyGO T-Display-P4 (63 × 109 mm) is too wide for the wrist cuff, Tailor Pixels' **`TOH323XVT-01C` 3.23" Bar AMOLED (`262×928`, 302 PPI, 22.01 × 77.95 mm AA, 23.80 × 81.05 mm outline)** is a **dream match** for our leather cuff with 3 acrylic half-round rods ([tailorpixels.com](https://tailorpixels.com/3-23-inch-bar-amoled-with-on-cell-touch-262x928-mipi/)). At 23.8 mm wide × 81.1 mm long, it is **narrower than our 1.91" AMOLED board (24.5 mm)** and almost the exact length of our 3.16" LCD (74.7 mm AA), while offering **true AMOLED blacks, internal GRAM (`RM690C0`), and 24-bit RGB888 over MIPI-DSI**.
- **How to use it:** Order `TOH323XVT-01C` ($33) paired with either Tailor Pixels' `TBX175EMD-01` ESP32-P4 eval board (~$32, confirm the 31-pin to `TOH323XVT-01C` MIPI FPC adapter with Tailor Pixels when ordering) or wire its MIPI-DSI FPC to a compact **Waveshare `ESP32-P4-NANO` ($18.99, 65 × 32 mm)** which adds the **ESP32-C6 BLE 5** radio. Also order their **`TOH240XVT-03CG` (2.4" 450×600 AMOLED, $17–$28)** which plugs directly into `TBX175EMD-01`'s 31-pin connector with zero adapter needed.

### 🥉 #3. Waveshare `ESP32-S3-Touch-AMOLED-2.41` (`SKU 30563`, 600×450 `RM690B0` QSPI) — Lowest-Friction Immediate Upgrade (< $45, < 1 Day Port)
- **Why it wins on zero-risk speed-to-wrist:** If you want **> 38–42 fps swinging on 3 tubes tomorrow** without changing MCUs, IMU drivers (`QMI8658`), RTC drivers (`PCF85063`), or BLE window logic, this $40 Waveshare board ([waveshare.com](https://www.waveshare.com/esp32-s3-touch-amoled-2.41.htm)) replaces the RAMless 320×820 RGB LCD with a **600×450 QSPI AMOLED (`RM690B0`) with internal GRAM**.
- **Why it beats `ESP32-S3-LCD-3.16` on the exact same ESP32-S3 chip:** No 32 MB/s PSRAM scan-out contention, no 525 KB portrait PSRAM framebuffer, hardware `MADCTL` orientation in the RM690B0 (no software quarter-turn `push`), 27% fewer columns per tube (`600` vs `820`), 49.0 × 36.7 mm active area (plenty of height for three 10-8-6 mm tubes + 4–5 mm leather bridges), true AMOLED blacks, and 24-bit RGB888 QSPI support.

### #4. Waveshare `ESP32-P4-NANO` (`SKU 29026`, $18.99) + Modular MIPI-DSI Display — Best Compact ESP32-P4 Core for Custom Cuff Integration
- At **65.0 × 32.0 mm** and **$18.99 USD** ([waveshare.com](https://www.waveshare.com/esp32-p4-nano.htm)), `ESP32-P4-NANO` gives you the full ESP32-P4 + ESP32-C6 (Wi-Fi 6 / BLE 5) + 32 MB 200 MHz DDR PSRAM + 2-lane MIPI-DSI connector in a wearable-friendly footprint. Pair it with a 22-pin MIPI-DSI panel (such as Waveshare's `2.8inch DSI LCD` 480×640 or `6.25inch DSI LCD` 720×1560 bar for bench testing, or a custom FPC to a 3.16" 320×820 ST7701S MIPI-DSI / 3.23" RM690C0 MIPI AMOLED panel) plus a tiny QMI8658 + PCF85063 I2C breakout.

### #5. Guition `JC4880P443C_I_W` ($25) or `M5Stack Tab5` ($65) — Best Turnkey ESP32-P4 Bench Vehicle
- To benchmark and tune the ESP32-P4 port (`render.cpp` on dual 400 MHz RISC-V cores + PPA hardware 90° rotation + 24-bit RGB888 MIPI-DSI output) immediately for under $35, grab the **Guition `JC4880P443C_I_W`** (4.3" 480×800 ST7701S MIPI-DSI, ESP32-P4 + C6, LiPo charger, ~$25 on AliExpress) or Waveshare's **`ESP32-P4-WIFI6-Touch-LCD-4.3`** ($33.99). If you want onboard **BMI270 IMU + RX8130CE RTC + INA226 power monitoring** built into a clean enclosure with zero soldering, get the **`M5Stack Tab5`** ($65).

---

## 5. Tempting-but-Wrong Candidates (And Why to Avoid Them)

1. **Waveshare `RP2350-Touch-AMOLED-2.41` ($46.99) / `RP2350-Touch-AMOLED-1.8` ($25.99)** ([waveshare.com](https://www.waveshare.com/rp2350-touch-amoled-2.41.htm)):
   - **Why it's tempting:** Looks identical to the Waveshare ESP32-S3 AMOLED boards, has QMI8658 IMU + PCF85063 RTC + RM690B0 2.41" AMOLED, and uses Raspberry Pi's new dual Cortex-M33 RP2350.
   - **Why it's wrong:** **(a)** RP2350 @ 150 MHz has **lower total compute** (~610 CoreMark dual-core) than ESP32-S3 @ 240 MHz (1,330 CoreMark); **(b)** its external PSRAM is **4-bit QSPI** (~33–50 MB/s max), **slower** than S3's 8-bit Octal PSRAM; **(c)** **no BLE radio** on board; **(d)** **no 2D accelerator** and only 520 KB SRAM (still not enough to hold 3 tube strips + 3×92 KB glyph pools without hitting slow QSPI PSRAM). It would render **slower** than our current S3 boards.
2. **Adafruit `Qualia ESP32-S3 for TTL RGB-666 Displays` (`PID 5800`, $19.95) + 3.2" 320×820 Bar LCD (`PID 5828`, `TL032FWV01`, $24.95)** ([adafruit.com](https://www.adafruit.com/product/5828)):
   - **Why it's tempting:** Fixes the RGB565 green/magenta hue banding by wiring the 320×820 ST7701S panel in **18-bit RGB666** mode (`R6-G6-B6`).
   - **Why it's wrong:** Still uses the exact same **ESP32-S3R8** with RAMless parallel RGB scan-out. Worse, on ESP32-S3 LCD_CAM, driving 18-bit RGB666 from memory requires either 24-bit/32-bit unpacked pixels in PSRAM (doubling scan-out DMA bandwidth from 32 MB/s to **64 MB/s**, which completely chokes the 80 MHz PSRAM bus!) or byte-aligning overhead, plus the Qualia board lacks an onboard IMU and RTC.
3. **STM32U5G9J-DK2 ($160) & NXP MIMXRT595-EVK ($145):**
   - **Why they're tempting:** Marketed specifically as "wearable/GUI MCUs" with massive **3 MB to 5 MB internal SRAM** and 2.5D vector GPUs (NeoChrom VG / Vivante VGLite).
   - **Why they're wrong:** Their CPUs are **single-core Cortex-M33s running at only 160 MHz (`STM32U5G9`) or 275 MHz (`RT595`)**. Because our per-pixel meniscus, refraction, Beer–Lambert residue, and fizz shaders run on the CPU rather than as OpenVG vector paths, a single 160–275 MHz M33 core cannot beat two 240 MHz LX7 cores on the S3, despite the zero-wait SRAM.
4. **LILYGO `T-Watch S3` (1.54" 240×240) / `ZSWatch` (nRF5340, 1.28" 240×240 round) / `PineTime` (nRF52832, 240×240):**
   - **Why they're wrong:** Square/round 240×240 panels are far too short (~28 mm AA) and low-density for three horizontal glass vials, and `nRF5340` (128 MHz M33, 512 KB SRAM, 8 MHz QSPI XIP) is roughly **3× slower** at software float/LUT rendering than ESP32-S3.

---

## 6. Verification & Unverified Items Log

- **Verified from vendor datasheets, schematics, and official wikis:**
  - `ESP32-S3-LCD-3.16` schematic (`ESP32-S3-LCD-3.16-schematic.pdf`): ST7701S wired as 16-bit RGB565 (`R0..R4`, `G0..G5`, `B0..B4`), explaining the 565 near-grey hue banding.
  - `ESP32-P4` TRM & datasheet: 768 KB HP L2MEM, 96 KB L1 cache, 32 MB Hexadeca-SPI PSRAM @ 200 MHz DDR, PPA SRM (0/90/180/270° hardware rotation + RGB565/RGB888 conversion) and PPA BLEND.
  - `LILYGO T-Display-P4`, `M5Stack Tab5`, `Waveshare ESP32-P4-NANO`, `Waveshare ESP32-S3-Touch-AMOLED-2.41`, `Tailor Pixels TBX175EMD-01` & `TOH323XVT-01C`: part numbers, resolutions, driver ICs, and pricing verified against current 2026 vendor pages.
- **Marked Unverified (confirm before hardware purchase/layout):**
  1. **Tailor Pixels `TBX175EMD-01` ↔ `TOH323XVT-01C` FPC pin mapping:** While `TBX175EMD-01` natively plugs into Tailor Pixels' 31-pin AMOLED series (`TOH240XVT-03CG` 450×600, `TOH198XVT-01CG` 410×502, `TOH204XVT-01CG` 368×448) and supports 2-lane MIPI expansion, the `TOH323XVT-01C` (262×928 bar AMOLED) datasheet pinout is gated behind a vendor request; confirm with Tailor Pixels that the matching MIPI FPC adapter and `display.cfg` init file for `RM690C0` are included.
  2. **`RM69A10` (LilyGO T-Display-P4) & `RM690C0` (Tailor Pixels 3.23") MIPI-DSI mode in shipping BSP:** Both driver ICs physically contain full-frame GRAM (supporting MIPI Command Mode), but some vendor BSP demos initialize MIPI-DSI panels in Video Mode (DPI passthrough) by default. Even in Video Mode, ESP32-P4's 200 MHz DDR 16-bit PSRAM has ~6× the headroom of ESP32-S3, and switching to Command Mode only requires the vendor's command-mode init sequence.
  3. **Battery connector polarity on third-party boards (`Guition JC4880P443C_I_W`, `LilyGO T-Display-P4`):** As with our Waveshare 1.91" board, JST/MX1.25 polarity is not standardized across Chinese vendors; always meter continuity to USB GND before plugging in a LiPo cell.
