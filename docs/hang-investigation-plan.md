# LCD-3.16 hang ("wedge") investigation plan

Written 2026-11-06, desk only (no board access). Revised the same day after a review (13 findings, all taken). For an
agent that runs it with the user at the board.

Hangs:
- **1** the rear-parallax round-2 hang at 80 MHz;
- **2** the 120 MHz flash + PSRAM wedges;
- **3** the old fizz / tubeHeight task-wdt reset (closed, see "Hang 3").

Sources:
- KAIZEN.md: the top "Visual / layout" list, "LCD 3-tube perf", and "Verification pass on the traces uint16 rework";
- BACKLOG.md "Firmware / ESP-IDF";
- docs/lcd316-3tube-perf.md "Wedges at 120 MHz";
- docs/lcd316-refill-dma.patch.

## Hand-off notes

- Board: Waveshare ESP32-S3-LCD-3.16 on Windows, **COM7**, running `lcd316@320w10-8-6+t3` (80 MHz flash + PSRAM). The
  user's look is firmware/bench/lcd-1105.json. /dev/ttyACM0 is the user's phone, never the board.
- From `firmware/`, once per shell:
  ```bash
  cd /home/andrey/_PROJECTS/watches/firmware
  export LW_PORT=COM7 LW_BOARD=lcd316 LW_RES=320w10-8-6 LW_TUBES=3
  W=/mnt/c/Users/i00109058/lwtools; OCD=$W/openocd-esp32; J=$W/jtag; mkdir -p $J   # Windows-visible: openocd.exe and python.exe read from here
  OCDS="$(wslpath -w $OCD/share/openocd/scripts)"
  ocd() { "$OCD/bin/openocd.exe" -s "$OCDS" "$@"; }
  ELF=.pio/build/lcd316/firmware.elf
  GDB=~/.platformio/packages/tool-xtensa-esp-elf-gdb/bin/xtensa-esp32s3-elf-gdb      # esp-gdb 17.1_20260402
  A2L=~/.platformio/packages-lcd316/toolchain-xtensa-esp-elf/bin/xtensa-esp32s3-elf-addr2line
  ROMELF=~/.platformio/packages-lcd316/tool-esp-rom-elfs/esp32s3_rev0_rom.elf      # symbols for PCs 0x40000000-0x4005ffff
  RELAY="target remote | python.exe -u '$(wslpath -w $J/relay.py)' 127.0.0.1 3333"
  ESPT="python.exe -m esptool --chip esp32s3 --port COM7"                          # Windows esptool (flash-win.sh uses the same)
  ```
  The files that commands refer to (`$J/capture.tcl`, `relay.py`, `step0.gdb`, `wedge.gdb`, `usbwatch.ps1`,
  `listen.py`) are given in full under "Files". Write them first.

### OpenOCD (installed and verified by the user, 2026-11-06)
- Release: openocd-esp32 **v0.12.0-esp32-20260424**, the one ESP-IDF 5.5.5 pins (`framework-espidf/tools/tools.json`,
  the IDF this build uses).
- Download:
  `https://github.com/espressif/openocd-esp32/releases/download/v0.12.0-esp32-20260424/openocd-esp32-win64-0.12.0-esp32-20260424.zip`,
  sha256 `d0005eea5b916df047afca7b777792050f8c6a6a502407180c8d839e9a841f75`.
- Unzip it to `C:\Users\i00109058\lwtools\` so that `lwtools\openocd-esp32\bin\openocd.exe` exists. Config:
  `board/esp32s3-builtin.cfg`.
- The JTAG interface (`USB JTAG/serial debug unit`, interface 2 of VID 303A / PID 1001) is on WinUSB already (user).
- If OpenOCD reports `LIBUSB_ERROR_NOT_FOUND`, Espressif's fix is `idf-env driver install --espressif`. That is a
  user action.

### WSL networking is NAT
- `wslinfo --networking-mode` says nat: Windows' `localhost:3333` is not reachable from WSL.
- GDB therefore runs in WSL and reaches OpenOCD through `target remote | python.exe relay.py`, a stdio-to-TCP relay
  that Windows Python runs against Windows' loopback.
- The relay is tested on Linux only. Fallback: the Windows esp-gdb 17.1_20260402 (tools.json win64 zip), run as `.exe`
  against `localhost:3333`.

### COM7 and JTAG at once: yes
The S3's USB-Serial-JTAG is one composite USB device: a CDC-ACM port (COM7) and a JTAG interface. Espressif: "JTAG
debugging, performed simultaneously with serial operations using tools like OpenOCD" (IDF v5.5 S3 "USB Serial/JTAG
Controller Console"). Caveats:
- **Which resets drop USB:**
  - `esp_restart` (`r`, `B0`, the BLE window's end) resets only the CPUs and some peripherals, not the USB-Serial-JTAG.
    The port normally survives (rloop.py: 30/30 "kept" at 80 MHz), and so may OpenOCD's connection.
  - A system reset, an RTC reset, esptool's USB reset or an EN reset re-enumerates the device. That drops COM7 and the
    JTAG interface, and OpenOCD must be restarted.
  - So neither "port kept" nor "port dropped" alone says whether the chip reset.
- While the cores are halted the firmware does not answer COM7: send nothing then.
- Never run esptool or flash-win.sh while OpenOCD is attached.
- One serial client at a time: a passive `listen.py` also counts.

### Rules
- **Risk levels:**
  - **none** = desk or host only, or plain serial reads.
  - **possible** = may stop the chip or need a reset. This covers every JTAG attach / halt / resume and every reset or
    flash at 80 MHz.
  - **likely** = expected to provoke the hang.
- **Every "possible" / "likely" step is one action.**
  - Announce it: "next: X; it may stop the board and need BOOT + RST; ready?".
  - Wait for the user's "ready", do that one thing, report, stop.
  - No unattended loops, no chained risky steps (memory: board-checks-need-user-ready).
- **A JTAG halt is an experiment, not passive.**
  - The RGB scan, its bounce-buffer GDMA and the tile GDMA keep running while the CPUs stop.
  - OpenOCD's halt handler writes zero to the TIMG0 / TIMG1 / RTC watchdog configurations (openocd-esp32
    `esp32s3.c` on_halt). After any halt, the watchdogs stay off until the next boot.
  - The OCD-aware panic path is armed while a debugger has ever been attached.
  - Watchdog-dependent experiments therefore start from a fresh boot without any debugger session.
- **No JTAG/GDB reset of a healthy board, ever.**
  - Forbidden: `reset`, `reset halt`, `reset init`, `soft_reset_halt`, `program_esp`, any `flash …` OpenOCD command,
    `monitor reset …`, the IDF default gdbinit (`mon reset halt`), and `pio debug`.
  - Only `init`, `halt`, `resume`, register and memory reads are allowed.
  - Resets and flashes happen only in announced steps.
- **Fast mode for halts.** A halted CPU starves the BT controller, so halt only when `s` ends `ble off`.
  - The BLE window ends with an `esp_restart` 180 s after boot (ble.cpp: "ble: window over, rebooting into fast
    mode"), the same path as `B0`.
  - Reaching fast mode is therefore itself a reset. Announce it as "possible", whether you wait or send `B0`.
- **"Did it reboot?"** `ble off` before and after does not prove "no reboot": the board can reboot into the window and
  restart into fast mode 3 min later. Evidence:
  - a boot banner caught by a listener held open across the step;
  - the aids build's boot counter and uptime (`v`);
  - the ROM / banner reset reasons.
- **A wedge costs the user BOOT + RST.** After a manual download-mode entry, the app starts only after RST without
  BOOT, or after a replug (the straps latch, KAIZEN).
- **Memory:** everything new is static or allocated once at boot (CLAUDE.md). Internal heap is ~9 KB in the BLE
  window and ~25 KB in fast mode. Check `pio run` RAM against HEAD and the `s` heap after any memory change.
  - Diagnostic builds may free memory elsewhere to make room: BLE off / fast mode, a smaller fizz pool, trimmed
    buffers. Still static, sized for the worst case.
  - Each step says what it freed.
  - **Repro builds** (H1.4, H1.5, H2.x) free nothing on the suspected path (render tasks' stacks, digit kernels,
    refill / tile DMA, PSRAM strips). Their memory layout stays close to production: moving buffers can mask a
    corruption bug.
- Keep the ELF of every build you flash: `.compare/elf/<first 8 of sha256>.elf`.
- **Preserve the coredump partition before any fault injection.** `CONFIG_ESP_COREDUMP_FLASH_NO_OVERWRITE` is unset,
  so the next panic overwrites the only copy. Do this with `read-flash 0xFF0000 0x10000` in a download-mode session
  (E0).

### Watchdogs and checks in this build
From the libs sdkconfig, `~/.platformio/packages-lcd316/framework-arduinoespressif32-libs/esp32s3/sdkconfig`.

Watchdogs:
- The task WDT watches IDLE0 only (5 s, panics). Core 1 / `loop()` is not watched.
- The interrupt WDT (300 ms) covers both cores.
- The bootloader arms the RTC WDT at 9 s. It stays armed through the app's MSPI tuning and PSRAM init, and is disabled
  at init priority 999.
- `esp_restart_noos` arms the RTC WDT at 1 s: stage 0 = system reset, stage 1 = RTC reset.
- The panic handler arms it at 10 s (RTC reset).

Checks already on:
- `CONFIG_FREERTOS_CHECK_STACKOVERFLOW_CANARY`;
- `CONFIG_FREERTOS_WATCHPOINT_END_OF_STACK` (it uses one of the two hardware watchpoints: set none in GDB);
- `CONFIG_COMPILER_STACK_CHECK` (normal);
- `CONFIG_ESP_DEBUG_OCDAWARE`;
- `CONFIG_ESP_COREDUMP_ENABLE_TO_FLASH` (ELF format, partition at 0xFF0000, 64 KB).

`CONFIG_ESP_SYSTEM_PANIC_GDBSTUB` is off.

## Desk findings (before any board step)

**Hang 3, closed.** The task-wdt reset on a tubeHeight shrink with fizz on (KAIZEN, 2026-09-01) is fixed:
- In a13f41a (2026-09-18) `fizzMag` clamps its row range into the tube.
- The magnification rows are clamped to [0.2, 5].
- The bubble row loops are now clipped to the band rows `[r0, r1)` and to `[0, H-1]` (`bubbleRows`, `planBubble`), so
  they no longer depend on `ry`.
- Host repro (scratch harness from render.cpp + seq.h, lcd316 320w10-8-6, 3 tubes, tiles, ASan + UBSan):
  - Setup: fizz 240 / size 6 / spring, vertical, 600 steps at H1, then H2, rendering every step around the switch.
  - Results: 72→55, 80→10, 80→4, 54→30 and 120→20 all ran clean. With fizzMag's pre-a13f41a range, the same harness
    segfaults.
- Board: on 2026-11-05 a PUSH_VERIFY run of lcd-1105 (fizz on) took "tubeHeight 60 and back" without a reset.

**Hang 1 (80 MHz).**
- The round-2 tree that hung was never committed. The closest committed shape is HEAD (5f97a18), where `PieRun`
  carries `T[144]` / `C[144]` (and `want[144]` with DIGIT_VERIFY) **on the stack**. The working tree moved them, plus
  the row buffer, into the per-Tube `DigitScratch`.
- **H1.4 result (2026-11-09, 80 MHz).**
  - Build: the current tree + aids + docs/hang1-stack-reconstruction.patch (round-2 kernel scratch back on the stack),
    `-DDIGIT_VERIFY=1`, production 4,096 B render0, ELF `0e02c937` (archived in .compare/elf). No debugger attached.
  - Sequence: `bench.py --preset bench/lcd-1105.json --live-imu` (its `B0`, then fps 32.5, digit-verify bad 0 of 16.8 M
    px), then `swing.py COM7 60 '-1,0>0.6,0@3'` (median 23.2 fps, bad 0 of 79.7 M px).
  - render0 stack-free: **588 B** after the bench, **492 B** after the swing (H1.0 predicted ~490 B); loop 4,412 B.
    `f` afterwards: digit-verify bad 0 of 109,270,289 px.
  - No hang or reset: boot 4 throughout. The `B0` restart and the closing esptool reset (the step where 11-06 went
    silent) were both clean. The restore flash's next boot recorded `prev: boot 4 stage running … worker 492`.
  - **Verdict: ≥ 300 B free, so a render0 stack overflow is not supported** for the reconstructed tree. Hang 1 stays
    unexplained: one 11-06 event, no coredump (E0), not reproduced here. Remaining: H1b (silent deadlock), H1d, or a
    cause outside the stack.
- **E0 result (2026-11-09).**
  - The coredump partition (0xFF0000, 64 KB; sha256 `0ccaf4f03d1c68d6…07f6`) is saved as
    `C:\Users\i00109058\lwtools\jtag\core-20261109-e0.bin`. It holds one valid ELF core of 16,324 B.
  - Its build is app ELF sha `eb42e35d2`. No ELF of that build survives (no archived ELFs then, scratchpads gone), so it
    was decoded with esp_coredump's SHA check bypassed (`scratchpad/core/cd_nosha.py`). Registers and ROM PCs are
    exact; app symbols are not.
  - Contents: crashed task `btController`, `exccause 0x45` = pseudo `PANIC_RSN_INTWDT_CPU0` (interrupt watchdog,
    CPU0). PC 0x40006fd0 `r_assert_param` ← `r_emi_get_mem_addr_by_offset` ← `r_ble_util_buf_rx_alloc` (ROM).
    Setup was still in BLE init (no NimBLE host task yet).
  - So the BLE controller asserted in its RX buffer allocation. That matches the 2026-11-05 TUBE_PROF + PUSH_PROF boot
    loop (KAIZEN: "BLE_INIT: Malloc failed, then reset int-wdt"), not hang 1.
  - **Consequence:** the coredump writer erases the partition before writing, and this older core is intact. So no
    panic since 2026-11-05 reached the coredump write: not hang 1 (11-06), not the g1 wedge, not the 11-09 USB-UART
    reset. Hang 1 was therefore a silent hang (H1b), a panic that stopped before the coredump stage, or a non-panic
    wedge. "A panic's coredump write hung" (H1c) does not fit, since its erase would have destroyed this core.
- **H1.0 result (compiled frames, 2026-11-06).**
  - Method:
    - `-fstack-usage -fcallgraph-info=su` on render.cpp with the lcd316 320w10-8-6+t3 compile command (from
      `pio run -t compiledb`), plus main / physics / display_lcd316 / tile_dma; call graphs merged from
      `renderWorker`.
    - Four variants: the working tree; HEAD with its own headers (`git archive`); a **reconstruction of the hung
      round-2 tree**; each with and without DIGIT_VERIFY.
    - The reconstruction is the working tree with the scratch arrays put back on the kernels' stacks where KAIZEN's
      "fractional kernels' stack scratch" places them: lanes in `PieRun`, `want` in `PieRun::end`, `row` in
      `spriteRunFracScalar`. It is saved as docs/hang1-stack-reconstruction.patch and applies to the working tree.
  - Static depth from `renderWorker`, in bytes:

    | tree | deepest chain | digit-kernel chain |
    |---|---|---|
    | working tree (± DV) | 2,384 (edge ramp: drawTube 992 → lambda 480 → rampRowR 112 → rampPieR 640) | 2,080 (DV) |
    | HEAD, DV | 2,656 (digits: drawTube 928 → labelBand 288 → spriteGlyphRows 192 → copies 80 → seg 32 → spriteRunInt 640 → PieRun::end 336) | same |
    | reconstruction, no DV | 2,608 (digits: … seg 128 → spriteRunFracPie 720) | same |
    | reconstruction, DV | **2,960** (… seg 128 → spriteRunFracPie 736 → PieRun::end 336 → pieBlend 32) | same |

  - Calibration: today's build measures ~3,028 B used (`v` worker-stack-free ~1,068) against a 2,384 B static chain.
    That leaves ~644 B outside the compiled frames: interrupt context saves on the task stack, the coprocessor
    (FPU / PIE) save area, task entry, library calls.
  - Estimates for the hung tree: DV ≈ 2,960 + 644 = **~3,600 B, ~490 B free**; without DV ~3,250 B (~840 B free).
    HEAD + DV: ~3,300 B (~800 B free).
  - **The 1,384 B were never all live at once.** `spriteRunFracPie` (lanes) and `spriteRunFracScalar` (row) are
    siblings under `SpriteRow::seg`, so the most live together is 576 + 288 = 864 B. The ≈316 B overflow estimate
    assumed all three; it is withdrawn.
  - Only if the round-2 code held the row in a common caller (e.g. `seg`) would the DV chain reach ~3,480 + 644 ≈
    4,124 B, i.e. ~28 B over.
  - Verdict: a plain render0 overflow is **not supported** by the compiled frames as reconstructed. It needs the row
    buffer in a shared frame, or ~490 B more interrupt / coprocessor overhead at the worst moment. The suspect is
    weakened, not excluded. The "survived after the move" observation is one run.
  - Deepest single frames: `Tube::lensMagRows` 1,088, `drawTube` 992, `buildPalette` 768, `spriteRunFracPie` 736 (DV,
    reconstruction). A stack guard meant to catch a jump past the end needs N ≥ ~1.1 KB, not 256 B.
- Why the stack checks may stay silent:
  - The canary and the end-of-stack watchpoint cover only the lowest 16-32 B.
  - The canary is checked only at a context switch.
  - A frame with a large array moves SP past the stack end, and its writes land below the stack.
- Why it may never reset:
  - `loop()` waits for render0 with `ulTaskNotifyTake(…, portMAX_DELAY)` and spins on `physDone`. render0 spins on
    `hoursPushDone`.
  - With render0 dead or stuck and no watchdog on core 1, nothing fires while core 0 still reaches IDLE0.
- The panic path (panic.c → `panic_restart` → `esp_restart_noos`) writes the coredump and restarts **without shutdown
  handlers**. So `preload_shutdown` does not cover panics, and the tile GDMA has no handler on either path.
- Open: why esptool's USB reset found no ROM ("No serial data received" twice). The USB-JTAG reset is hardware. It
  fails if `RTC_CNTL_USB_CONF.USB_RESET_DISABLE` (bit 17) is set, if the device is gone or flapping, or if the chip
  resets into a failing boot.

**Hang 2 (120 MHz).**
- `esp_restart_noos` resets only the CPUs plus the MSPI / DMA / timer peripherals. The flash and PSRAM dies keep their
  mode state until power is removed.
- **HPM is never applied to this flash in this build.**
  - The vendor is 0x20 (XMC; 16 MB ⇒ probably ID 0x204018).
  - IDF's XMC entry is in the dummy-cycle ("HPM-DC") table, compiled only with `CONFIG_BOOTLOADER_FLASH_DC_AWARE=y`.
    That option is unset here, and the other tables do not match.
  - `spi_flash_enable_high_performance_mode` therefore logs "High performance mode of this flash model hasn't been
    supported" (hidden at log level ERROR), and `cpu_start.c` ignores the result.
  - 120 MHz ran this flash at default dummy cycles, which is likely beyond its rating. The datasheet of the exact part
    decides (ID from step 0).
  - Consequence 1: the app does not write the flash's volatile SR3 at 120 MHz. This holds if the 120 MHz build used
    this sdkconfig plus only the frequency options (H2.2).
  - Consequence 2: do not set `BOOTLOADER_FLASH_DC_AWARE` through `custom_sdkconfig`. The hybrid compile does not
    rebuild the bootloader (libs `bin/bootloader_*.elf` dated Jul 20; none has `bootloader_spi_flash_reset`), and
    `flash-win.sh --full` flashes PlatformIO's factory image with that packaged bootloader. The result would be an app
    that sets the DC bits with a bootloader that cannot read the flash after a reset: a guaranteed wedge. H2.7 shows
    the explicit way.
- **H2.2 result (2026-11-09, desk).**
  - Flash ID (step W capture, rom_spiflash_legacy_data): **0x204018**, chip size 16 MB. That is XMC (0x20), memory
    type 0x40, capacity 0x18. In XMC's C generation the 0x40 type carries the size in the last byte: XM25QH64C =
    20 40 17 (XM25QH64C Rev 1.0, 7.1.1 "Manufacturer and Device Identification"), XM25QH256C = 20 40 19 (XM25QH256C
    Rev 1.8, 7.1.1). So 0x204018 = **XM25QH128C**. The XM25QH128C PDF itself was not found online: XMC's product page
    https://www.xmcwh.com/site/product_con/202 lists 133 MHz but links no PDF. The A generation (LCSC copy of
    XM25QH128A) could not be read, so whether A/B/D revisions share 0x204018 is not established.
  - Rating, the same in both C datasheets ("Read performance Comparison Table", p. 6, and 6.1.13 "Dummy Cycle Bits"):
    Fast Read Quad I/O (EBh) is **108 MHz with the default 6 dummy cycles** and 133 MHz with 8 (DC1/DC0 in status
    register 3). Dual I/O (BBh) is 108 MHz at the default 4.
    - https://www.xmcwh.com/uploads/207/XM25QH64C.pdf
    - https://www.xmcwh.com/uploads/198/XM25QH256C_Ver1.8.pdf
  - What the 120 MHz build used:
    - QIO (platformio.ini `board_build.flash_mode = qio`, memory_type qio_opi) with the bootloader header in DIO / 80m
      (ROM banner `mode:DIO`).
    - No HPM for this ID without a DC-aware bootloader (above), so the app keeps IDF's generic quad-I/O dummy,
      `SPI_FLASH_QIO_DUMMY_BITLEN 6` (spi_flash_defs.h). IDF's XMC HPM path would use 10
      (`SPI_FLASH_QIO_HPM_DUMMY_BITLEN`, after setting the SR3 DC bits).
    - MSPI timing tuning at boot only picks a sampling point (DIN_MODE / DIN_NUM) that passes its test pattern at that
      moment's temperature. It cannot add dummy cycles.
  - **Verdict: 120 MHz ran this flash out of spec** (EBh at 120 MHz with 6 dummy cycles vs a 108 MHz rating), for the
    whole run, not only around resets. Nothing measured whether that causes the wedges ("never in steady running" argues
    against a pure margin effect). But no 120 MHz result from this board is valid, and no upstream report is possible,
    until it runs in spec.
  - That makes **H2.7 (DC-aware bootloader + HPM-DC) the precondition for any further 120 MHz work**, not an optional
    late test.
  - PSRAM: octal PSRAM at 120 MHz is IDF-experimental for MSPI timing / temperature reasons (Kconfig help). No
    PSRAM-device datasheet limit was checked in this round.
- Octal PSRAM at 120 MHz is "experimental, works when the temperature is stable" (IDF Kconfig), and so is the
  temperature retuning task.
- 120 MHz is all or nothing: IDF's static asserts reject octal PSRAM at 120 + 80 and 80 + 120.
- Boot hangs run under the bootloader's 9 s RTC WDT, and hangs in `esp_restart_noos` under its 1 s RTC WDT. A
  permanent wedge is therefore most likely a reset loop, a dead or flapping USB device, or a halted state no watchdog
  sees.
- **g1 (the retuning-task build), H2.0 result.** Source: the 2026-11-05 session transcript (Claude session
  2e184d9c, ~16:46-17:33 local).
  - The A/B matrix ran f0 → f1 → g1 → f0 → f1. Each slot is a flash (esptool USB reset + boot), then bench.py, which
    sends `B0` (an `esp_restart` into fast mode) because a fresh flash boots in the BLE window, then a 60 s swing.
  - g1's slot started 16:52:36. Its flash boot and its `B0` restart both succeeded. The pinned bench and the 60 s swing
    completed ("median fps 31.4 push 6.48 ms over 22 windows").
  - The next slot's flash (f0, 16:55:30) failed: 10 attempts until 17:27, then f1 failed too. At 17:33, esptool
    `chip-id` gave "No serial data received" and an 8 s raw serial capture gave nothing. usbipd still listed
    `303a:1001 … COM7, USB JTAG/serial debug unit`: **USB stayed enumerated**.
  - Windows' System log shows the only sleep at 16:08-16:40, before the matrix.
  - The user's BOOT + RST then gave download mode, and f0 was flashed.
  - Verdict:
    - "~3 min into a swing bench" (KAIZEN) is 3 min into g1's matrix slot (flash, bench, swing). The swing itself
      finished.
    - The wedge showed at the first esptool USB-JTAG reset after the swing, within seconds of the swing's end. So g1
      is reset-associated, as the perf doc has it.
    - The BLE-window-restart reading is refuted: bench.py's `B0` had put the board in fast mode for that boot.
    - Not excluded: the chip hung in the few seconds between the swing's end and the reset, with live retuning as
      the cause. The data cannot separate the two.
  - Repro implication (H2.8): g1 build, flash, bench (with its `B0`), 60 s swing, then **one esptool reset**, with
    Step W ready.
  - Since USB stayed enumerated in g1's wedge, a JTAG attach in that state is plausible.
- The 120 MHz build was never committed. Reconstructed recipe (confirm with the user, H2.2):
  - in `[env:lcd316]`: `board_build.f_flash = 120000000L` and `board_build.f_image = 80000000L`;
  - in `custom_sdkconfig`: `CONFIG_ESPTOOLPY_FLASHFREQ_120M=y` and `CONFIG_SPIRAM_SPEED_120M=y`
    (`IDF_EXPERIMENTAL_FEATURES` is already y);
  - the libs rebuild takes ~10 min each way.

## Step 0: JTAG bring-up on the healthy 80 MHz board

User: board connected, face running, nothing else on COM7 (browser Web Serial closed), OpenOCD unzipped.

| # | action | expect | risk |
|---|---|---|---|
| 0.1 | done (user, 2026-11-06): `C:\Users\i00109058\lwtools\openocd-esp32\bin\openocd.exe` = "Open On-Chip Debugger v0.12.0-esp32-20260424", `board/esp32s3-builtin.cfg` present. **Also check the scripts root:** `ls $OCD/share/openocd/scripts/{bitsbytes,memory,mem_helper,mmr_helpers}.tcl`. The 2026-11-06 install lacked every root-level file there (only the subfolders were extracted), and OpenOCD then stops at `esp_common.cfg:5: Can't find bitsbytes.tcl` before `init`. Fix: re-extract the whole zip | — | none |
| 0.2 | `powershell.exe -NoProfile -c "Get-PnpDevice -PresentOnly \| ? InstanceId -like 'USB\VID_303A&PID_1001*' \| ft -auto Status,Class,FriendlyName,InstanceId"` | COM7 = MI_00, `USB JTAG/serial debug unit` = MI_02, all OK | none |
| 0.2b | the JTAG interface (MI_02) must be on a WinUSB binding **with** `DeviceInterfaceGUIDs` (libusb needs it): `Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_303A&PID_1001&MI_02\<instance>\Device Parameters'`. Microsoft's automatic `winusb.inf` ("WinUsb Device", from the chip's MS compatible ID) has none, so OpenOCD's `init` fails with `libusb_open() failed with LIBUSB_ERROR_NOT_FOUND`. Fix used 2026-11-09 (Zadig not needed): `idf-env driver install --espressif`, then Device Manager → the interface → Update driver → pick from the list → Espressif's "USB JTAG/serial debug unit" (libwdi WinUSB, oem162.inf, originally usb_jtag_debug_unit.inf), because Windows kept Microsoft's winusb.inf after idf-env. Result: `DeviceInterfaceGUIDs {80869ad8-c37f-476a-a6b4-ae241c30a473}`. COM7 stays usbser. Replug afterwards | GUID present | none |
| 0.3 | `tools/device.py v s` | tag `lcd316@320w10-8-6+t3`, stack-free worker ~1068 / loop ~4352, `s` ends `ble off` | none |
| 0.3b | only if `ble on`: announce it, then let the window end (≤ 180 s after boot) **or** `tools/device.py B0`. Either one is an `esp_restart` | `s` → `ble off` | possible |
| 0.4 | one halt / resume cycle, announced. First start `python.exe -u "$(wslpath -w $J/listen.py)" COM7 40 \| tee $J/com-0.4.txt &` (holds COM7: a boot banner during the cycle = reboot). Then `ocd -c "set ESP_RTOS none" -c "set ESP_FLASH_SIZE 0" -f board/esp32s3-builtin.cfg -c "set TAG step0" -f "$(wslpath -w $J/capture.tcl)" 2>&1 \| tee $J/cap-step0.txt` | cpu0 / cpu1 examined, both halt, registers and dumps, resume, exit; no banner in com-0.4.txt; the panel recovers. PCs: `$A2L -pfiaC -e $ELF <pc>` (ROM PCs `-e $ROMELF`) | possible |
| 0.5 | after the listener exits: `tools/device.py f s` | normal `f`, `ble off` | none |
| 0.6 | GDB cycle, announced. OpenOCD server: `ocd -c "set ESP_FLASH_SIZE 0" -f board/esp32s3-builtin.cfg -l "$(wslpath -w $J/ocd-gdb.log)" &` (FreeRTOS awareness). With it attached and the target running, `tools/device.py f` (COM7 next to JTAG). Then `$GDB -nx -q $ELF -ex 'set trust-readonly-sections on' -ex 'set remotetimeout 20' -ex "$RELAY" -x $J/step0.gdb 2>&1 \| tee $J/gdb-step0.txt` | `f` answers with OpenOCD attached; GDB: tasks with backtraces, the board's `app_elf_sha256` = `sha256sum $ELF`, the flash ID, render0's stack bottom and the 64 B below it; `detach` resumes | possible |
| 0.7 | stop OpenOCD: `printf 'shutdown\x1a' \| python.exe -u "$(wslpath -w $J/relay.py)" 127.0.0.1 6666`; `tools/device.py v s`; 0.2 again | same tag, `f` normal, same PnP list | none |

Lessons from the first run (2026-11-09):
- **OpenOCD does not resume on its own.** It leaves the cores halted when a script fails, when it exits, and on GDB
  `detach` (seen: halted 4.5 min after "detached"). Always end with an explicit `resume` (capture.tcl does; after
  GDB: `printf 'resume\x1a' | python.exe -u relay.py 127.0.0.1 6666`), then `targets` must show `running`.
- **TCL:** `[...]` inside a double-quoted string is command substitution. A label like `"[debugger-modified]"` aborted
  the script with both cores halted. Keep brackets out of strings.
- **Never kill a serial client with `timeout`** (device.py, listen.py). The killed Windows bridge drops DTR while RTS is
  high: a USB-UART reset (cause 21) was seen. Use `device.py --timeout N`, and let listeners end by their own duration.
- **A halt counts as uptime** for the BLE window (`millis()` kept running): resuming a window boot after a long halt
  ended the window at once (`esp_restart` into fast mode). Halt only in fast mode; in a wedge capture of a window boot,
  expect that restart after the resume.
- Clean run (2026-11-09 14:10): OpenOCD `-c "set ESP_RTOS hwthread" -c "set ESP_FLASH_SIZE 0"`, `target extended-remote | relay`, step0.gdb ending `monitor resume` / `detach` / `quit`: both cores halted, backtraced, `running` again, no reset (stack-free and `ble off` unchanged); COM7 answered `v`/`s`/`f` with OpenOCD attached and the cores running. One `f` window right after the attach read 27 fps (cores 27 / 34 ms), the next ones 40.5 - 41: no lasting slowdown, but discard the first `f` window after an attach.
- GDB with `ESP_RTOS none` shows one thread, and `monitor targets esp32s3.cpu1` + `flushregs` does not switch GDB's
  view. Take core 1's PC / stack from capture.tcl, or start OpenOCD with `-c "set ESP_RTOS hwthread"` for one thread per
  core.

Notes:
- `ESP_FLASH_SIZE 0` means no flash stubs and no partition-table read on connect. It does not make the attach passive:
  the halt still stops the CPUs and zeroes the watchdog configurations.
- The board stays without TIMG / RTC watchdogs until its next boot. Do not run watchdog-dependent tests in this boot.
- Step 0 answers:
  - whether attach / halt / resume works without a reset (listener evidence);
  - whether the flashed app is this ELF (if not, the next flash is an announced "possible" step);
  - the flash ID (hang 2);
  - render0's stack position (hang 1).

## Step W: capture when the chip is wedged (attach without reset)

Order matters: the first seconds hold the reset loop's text. Touch nothing on the board and run no esptool.

1. **At once, in parallel:**
   - the passive listener `python.exe -u "$(wslpath -w $J/listen.py)" COM7 60 | tee $J/com-<tag>.txt &`, if COM7
     exists; it re-opens the port when it reappears;
   - the USB watcher `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w $J/usbwatch.ps1)" 60 | tee $J/usb-<tag>.txt &`.

   Classify the event with the reset evidence, not by USB presence:
   - ROM `rst:` lines (cause, `Saved PC`) and boot banners;
   - the aids build's boot counter, uptime and early-boot marker;
   - later, the JTAG `RTC_CNTL_RESET_STATE`.

   USB presence is only a hint: `esp_restart` keeps the port, and the watcher (~1 s polls) misses short drops.
2. Note the time, the last command or step, the temperature from the last `s`, and the build (tag, ELF sha8).
3. When the listener has run ~20 s, or at once if COM7 is absent: stop the listener (it holds COM7). If the JTAG
   interface is present, run
   `ocd -c "set ESP_RTOS none" -c "set ESP_FLASH_SIZE 0" -f board/esp32s3-builtin.cfg -c "set TAG <tag>" -c "set HOLD 1" -f "$(wslpath -w $J/capture.tcl)" 2>&1 | tee $J/cap-<tag>.txt`.
   The attach itself is risk "possible", but the board is already wedged. It stays up halted for GDB.
   - Read for:
     - whether each core halts at all (a core that will not halt is stuck on a bus access, e.g. cache → MSPI);
     - PC / PS / EXCCAUSE / DEBUGCAUSE and the PC's region: ROM `0x4000_0000-0x4005_FFFF`, bootloader IRAM, app IRAM
       `0x4037_xxxx`, flash text `0x42xx_xxxx`;
     - `RTC_CNTL_RESET_STATE` (0x60008038): [5:0] PRO and [11:6] APP cause (0x01 power-on, 0x03 sw sys, 0x09 RTC-WDT
       core, 0x0C sw CPU, 0x10 RTC-WDT sys + RTC, 0x15 USB-UART, 0x16 USB-JTAG);
     - `RTC_CNTL_STORE6` (+0xC8, the reset-reason hint) and `RTC_CNTL_USB_CONF` (+0x120: bit 17 USB reset disable,
       bits 19 / 20 PHY select);
     - `SYSTEM_PERIP_RST_EN0` (0x600C0020: SPI01 in reset?) and `SYSTEM_CORE_1_CONTROL_0`;
     - SPI0: CLOCK +0x14, TIMING_CALI +0xA8, DIN_MODE +0xAC, DIN_NUM +0xB0, SMEM_TIMING_CALI +0xBC, SMEM_DIN_MODE
       +0xC0, SMEM_DIN_NUM +0xC4, CORE_CLK_SEL +0xEC. SPI1: CMD +0x00 (a flash op pending);
     - EXTMEM: DCACHE / ICACHE_CTRL, PRELOAD_CTRL +0x40 (bit 0 ena, bit 1 done), CACHE_STATE +0x130, the
       illegal-access / reject / MMU-fault registers;
     - GDMA ch0-4 IN / OUT state and link;
     - the aids boot record, and the render0 guard (aids, addresses from `nm`).
   - **The watchdog registers in this dump (TIMG0/1 WDTCONFIG0, RTC_CNTL WDTCONFIG0) are debugger-modified:** OpenOCD
     zeroed them on halt. They say nothing about the wedge's own watchdog state, which is not recoverable from JTAG.
     The aids' `v` shows the configured values on a healthy boot, for reference.
   - Never read 0x3C00_0000-0x3DFF_FFFF or 0x4200_0000-0x43FF_FFFF (flash / PSRAM through the cache) on a wedged
     chip. capture.tcl reads stacks only when SP is in internal SRAM.
4. If a core halted in app code: `$GDB -nx -q $ELF -ex 'set trust-readonly-sections on' -ex "$RELAY" -x $J/wedge.gdb 2>&1 | tee $J/gdb-<tag>.txt`. Then stop OpenOCD (0.7).
5. Recovery ladder, one rung at a time, noting each result:
   - (a) The user presses **RST only**. Does the app boot? (`tools/device.py v`: banner reason, boot count.)
   - (b) If not: **BOOT + RST** (download mode). Run `$ESPT --before no-reset --after no-reset flash-id`, then **E0**
     (export the coredump) and `$ESPT --before no-reset --after no-reset read-flash 0x0 0x8000 "$(wslpath -w $J/boot-<tag>.bin)"` (the board's bootloader, once). Then RST.
   - (c) If still not: replug.
6. Next boot: `tools/device.py v` (aids: previous-boot record, cached coredump summary). Decode the exported coredump:
   `~/.platformio/penv/bin/python -m esp_coredump --chip esp32s3 info_corefile -t raw -c $J/core-<tag>.bin --gdb $GDB <that build's ELF>`.

**E0, coredump export.** Mandatory before H1.4 / H1.5 / any "likely" step, and after every wedge. Run it in a
download-mode session the user enters anyway, or piggyback it on the first planned flash: esptool connects in download
mode there.
- Command: `$ESPT --before no-reset --after no-reset read-flash 0xFF0000 0x10000 "$(wslpath -w $J/core-<date>-<n>.bin)"`
  (or, in the flash session, `$ESPT read-flash …` right before the write).
- Archive it even without the matching ELF: task, cause and raw PCs remain.
- Erase only after the export, and only in a download session: `$ESPT --before no-reset --after no-reset erase-region 0xFF0000 0x10000`.
- Risk: as the session it rides on (none extra).

## Firmware aids (build "aids"; static, allocated at boot)

**Implemented 2026-11-09 (host only, not flashed), revised after review:**
- Code: `src/diag.cpp` / `diag.h` (LCD only; no-ops on the AMOLED), hooks in main.cpp / ble.cpp / display_lcd316.cpp,
  `-Wl,--wrap=esp_core_dump_write` in env lcd316.
- Early marker: an IDF `ESP_SYSTEM_INIT_FN(…, CORE, BIT(0), 1)`, first in the init table (checked in the ELF). It runs
  before every C++ constructor; Xtensa runs the constructor table backwards, so a constructor would not be first.
- The refill preload drain is recorded as drained / timed out and kept through SHUT_LAST.
- All new formatted output goes through `diag_printf` (a static 448 B line buffer, `[TRUNC]` when cut), not Arduino's
  `Print::vprintf`, which mallocs for 64 B and more.
- `-DLOOP_WDT` feeds: after each command, per input byte drained, between ≤ 512 B output chunks of `x` / `p?`, per `X`
  frame, at the end of `renderBoth` (after its waits) and of `loop()`. The render waits themselves stay unfed.
- `rloop.py --stop-on-fail` validates the whole transcript (`check_restart`; mocked cases in `tools/test_rloop.py`).
- **The default build is not byte-for-byte production:** the boot output (`prev:`, rst ring, coredump lines), the `v`
  line and the new `C` command change; `s` / `f` and rendering do not (check_render_frames identical,
  check_board_render 75/77 as before). RAM +448 B static internal, +48 B RTC.

One flash at 80 MHz (risk possible). Do E0 in the same esptool session, before the write. Memory: the additions are
small. The static render0 stack + TCB move ~4.5 KB from the heap to .bss (net ~0), and the guard adds 256 B. They fit
in both modes without freeing anything; if `pio run` says otherwise, shrink the fizz pool and record it (not in repro
builds).

1. **`v` identity and state** (no flash access; internal reads):
   - `elf <sha8>` (`esp_app_get_elf_sha256_str`; the bin carries the ELF's sha256, checked equal to `sha256sum $ELF`);
   - `boot <count> up <ms>` (from aid 3);
   - `flash <id>` (`rom_spiflash_legacy_data->chip.device_id`);
   - `hpm-dc <0/1>` (`spi_flash_hpm_dummy_adjust()`);
   - `mspi` = raw SPI0 CLOCK / CORE_CLK_SEL / TIMING_CALI / DIN_MODE / DIN_NUM / SMEM_TIMING_CALI / SMEM_DIN_MODE /
     SMEM_DIN_NUM (this boot's tuning point);
   - `rom-rst <c0>/<c1>`;
   - `wdt` = raw TIMG0 / TIMG1 / RTC WDTCONFIG0 (the pre-debugger reference);
   - `temp`.
2. **Coredump summary, boot only.**
   - In `setup()` before `display_init`: if `esp_core_dump_image_check() == ESP_OK`, read `esp_core_dump_get_summary()`
     into a **static** `esp_core_dump_summary_t` plus a valid flag. Both calls allocate temporary iterator / mapping
     metadata, so they are allowed only here, once.
   - Print it in the banner. `v` / `C` print the cached copy.
   - No runtime erase: `esp_core_dump_image_erase()` allocates (`esp_partition_find_first`). Erase through esptool
     after E0.
3. **Boot record** `RTC_NOINIT_ATTR static LwBootRec`, ~64 B in RTC memory, magic + CRC. It is garbage after a
   power-on and not guaranteed across an EN reset.
   - Fields: boot count; a ring of the last 8 ROM causes per core; `stage`; uptime; frame count; render0 / loop stack
     minimum; last serial command; the last panic's core / PC / cause.
   - **Early marker:** a `__attribute__((constructor(101)))` function bumps the boot count and sets stage `early`. It
     runs after the CPU-start MSPI tuning and PSRAM init, before `setup()`.
   - Later stages: setup start, display ok, render ok, BLE init, ready, running, restart requested, shutdown first,
     preload drained, shutdown last, panic.
   - At boot print `prev: stage … up … frame … cmd … rst …`, then start a new record.
   - Reading a "shutdown last" record with ROM cause 0x10 / 0x09 on the next boot leaves two possibilities, kept apart
     by the early marker:
     - a hang inside `esp_restart_noos` (the boot count did not move between);
     - a completed restart whose next boot died before the constructor ran (ROM, bootloader, MSPI tuning, PSRAM init).
       The boot count did not move either, so these two are told apart only by Step W text (a ROM `rst:` / bootloader
       output between them) or a JTAG PC.
   - If the boot count moved and stage = `early` / `setup …`, that boot died after the marker.
4. **Panic breadcrumb** (implemented 2026-11-09 as `-Wl,--wrap=esp_core_dump_write`. The Arduino core already wraps `esp_panic_handler`, and its hook builds a 256 B struct on the panicking stack. The coredump write is the next step of every rebooting panic. The ELF check: `esp_panic_handler` loads `__wrap_esp_core_dump_write`, in IRAM. Original plan text follows:) `-Wl,--wrap=esp_panic_handler`. `__wrap_esp_panic_handler` is IRAM-only, lock-free, with no
   IDF API calls. It stores core / addr / exception into the RTC record with plain stores, then calls `__real_…`.
   - With `-DPANIC_QUIESCE=1` (test flag, H1.6) it also, before the coredump write:
     - (i) sets a `volatile bool` in internal RAM that the refill ISR tests instead of `preloadOff`-under-`preloadMux`.
       Use a plain store with no `portENTER_CRITICAL`: IDF stalls the other CPU before `esp_panic_handler`, maybe while
       it holds `preloadMux`, and `preload_shutdown` takes that mux.
     - (ii) spins on the ROM `Cache_DCache_Preload_Done()`, bounded by `esp_cpu_get_cycle_count()` (20 ms).
     - (iii) stops each tile GDMA channel by register: set `OUTLINK_STOP` (bit 20 of `GDMA_OUT_LINK_CHn_REG`,
       0x6003F080 + 0xC0·n) and `INLINK_STOP` (bit 21 of `GDMA_IN_LINK_CHn_REG`, 0x6003F020 + 0xC0·n). Then poll
       `OUT_STATE` / `IN_STATE` (bits [22:20] of +0x84 / +0x24) for idle, bounded.
   - The channel numbers are captured once at boot with `gdma_get_channel_id` into a static `int8_t[6]`.
   - Audit: everything it calls must be in IRAM or ROM (`nm`/map: no `.flash.text` symbols in its call chain).
5. **Core-1 watchdog** (`-DLOOP_WDT=1`, off by default):
   - Register once in `setup()`: `esp_task_wdt_add(loopTask)`. It allocates its list entry once; check the result,
     and print "FATAL" on failure.
   - Feed with `esp_task_wdt_reset()` at the end of every ordinary `loop()` iteration. That covers every mode: only
     `'l'` renders, the others `delay(1)`. A blocked render wait then goes unfed.
   - It turns a silent deadlock into a task-wdt panic and so changes the phenomenon. Every H1 run is done once without
     it (baseline) before the run with it.
6. **Stack guard** (`-DSTACK_GUARD=N`, a detection build, not a repro build):
   - render0 from `xTaskCreateStaticPinnedToCore`: a static `StackType_t` array with N extra bytes at its low end
     (0xA5-filled at boot, outside the stack FreeRTOS sees) and a **static `StaticTask_t`**.
   - Choose N from H1.0: the deepest single frames are `lensMagRows` 1,088 B and `drawTube` 992 B, so N ≥ ~1.1 KB to
     catch a jump past the end. 256 B is too small. In fast mode the internal heap has room; if it does not, shrink
     the fizz pool for this build and record it.
   - Partial detection only: a larger excursion skips it, and `loop()`'s per-frame check cannot run while `loop()` is
     blocked on render0. In a hang, read the guard over JTAG (`mdw <guard> N/4`, address from `nm`).
   - The stack moves from the heap to .bss, which changes what an overflow would hit. Use the guard to measure, never
     to reproduce.
   - `WORKER_STACK` becomes overridable (`#ifndef WORKER_STACK`).
7. **`CONFIG_ESP_SYSTEM_PANIC_GDBSTUB`: not used.**
   - It needs a libs rebuild.
   - Its stub talks on the primary console, UART0, which is not on USB here.
   - It disables all watchdogs and waits forever, so every panic becomes a wedge.
   - JTAG with OCDAWARE (already on) halts at the faulting PC only while OpenOCD is attached; without it, a panic
     reboots normally with a coredump.
   - If USB proves dead in a wedge, the only other window is UART0 (GPIO43 TX, 115200, ROM + bootloader output). It
     needs a 3.3 V USB-UART adapter and an exposed pad. Pad JTAG (GPIO39-42) is taken by VSYNC / DE / PCLK and needs an
     eFuse.
8. **Tooling:** `tools/rloop.py --stop-on-fail`. On a dropped port, a missing `ready.` or a reset reason other than
   `sw`: print and exit at once. The current version retries `s` up to 10 × (3 s + 2 s) and then continues. Use it only
   as `-n 1 --stop-on-fail`, one announced action per restart.

## Hang 1: rear-parallax round-2 hang (80 MHz)

**Status 2026-11-09: Hang 1 (rear-parallax round-2, 80 MHz, 2026-11-06) parked, not reproduced (H1.4 2026-11-09: reconstructed round-2 tree + DIGIT_VERIFY, bench + 60 s swing, render0 492 B free, digit-verify 0 bad of 109 M px, the closing esptool reset clean; no coredump from it, E0). The hang diagnostics (src/diag.cpp: RTC boot record, panic breadcrumb, cached coredump summary, `v` / `C`) are in the production LCD build and will record it if it recurs; -DLOOP_WDT and -DSTACK_GUARD=1152 stay opt-in (docs/hang-investigation-plan.md).** H1.5-H1.9 stay available if it recurs.

Hypotheses:
- **H1a** render0 stack overflow corrupting memory below its stack.
- **H1b** a silent deadlock after that (render0 dead, `loop()` blocked or spinning, no watchdog on core 1).
- **H1c** a panic whose coredump write or restart hangs on the preload / tile GDMA (no shutdown handlers on the panic
  path).
- **H1d** the USB reset made ineffective (USB_RESET_DISABLE, a reset loop).

| step | build / commands | captures | memory freed | risk |
|---|---|---|---|---|
| H1.0 desk | **done 2026-11-06** (Desk findings, hang 1): compiled frames + merged call graph, working tree / HEAD / reconstruction, ± DIGIT_VERIFY | reconstruction + DV ≈ 3.6 KB of 4 KB (~490 B free); all 1,384 B never live together | — | none |
| H1.1 E0 | export the existing coredump (piggyback on the aids flash) | the last panic's core, maybe the 2026-11-06 event | — | as the flash (possible) |
| H1.2 | aids flash (`tools/flash-win.sh --env lcd316 --res 320w10-8-6 --tubes 3 COM7`, aids 1-4, 8; no LOOP_WDT, no guard); first boot prints the old summary | `v` identity, `prev:` record, coredump summary | none | possible |
| H1.3 | step 0.6 GDB on the aids boot: render0 `pxStack` and the block below; the loop task likewise | what an overflow overwrites | none | possible (halt) |
| H1.4 | **historical repro, production layout**: working tree + `git apply ../docs/hang1-stack-reconstruction.patch` (the round-2 kernels with their scratch on the stack, 4,096 B render0; HEAD is not the hung tree: no fractional kernels, ~800 B headroom) + aids 1-4, `PLATFORMIO_BUILD_FLAGS="-DDIGIT_VERIFY"`; fresh boot, fast mode (announced restart), **no debugger** (baseline), then the original load: `tools/bench.py --preset bench/lcd-1105.json --live-imu`, then `tools/swing.py COM7 60 '-1,0>0.6,0@3'`; afterwards `tools/device.py v` | the measured render0 headroom (`stack-free worker`) vs H1.0's prediction ~490 B: ≥ ~300 B and no hang ⇒ H1a not supported, look at H1c / H1d; ≤ ~100 B or a hang (Step W) ⇒ H1a supported | none (repro: production layout) | likely |
| H1.5 | same build, OpenOCD attached (attach only, no halt), the same load | OCD-aware: a canary / watchpoint panic halts at the fault, `wedge.gdb` gives both cores | none | likely |
| H1.6 | only if H1.4 hung: + `-DLOOP_WDT=1`, the same load | the silent hang becomes a task-wdt panic + coredump: where core 1 and render0 were | none | likely |
| H1.7 | fault injection, not confirmation: working tree + `-DWORKER_STACK=<H1.0 headroom - margin>` (current code, overflow forced), no debugger | does an overflow end in a canary / watchpoint panic and a clean reboot, or in a wedge (Step W)? Tests the detection / recovery path only | the reduced stack (heap layout shifts: noted) | likely |
| H1.8 | only if H1.4 / H1.7 wedged in the panic path: + `-DPANIC_QUIESCE=1`, repeat it; then, one more round, `CONFIG_ESP_COREDUMP_ENABLE_TO_NONE=y` instead | wedge gone ⇒ H1c | none | likely |
| H1.9 | close: the production tree with `-DSTACK_GUARD=1152`, the same load | `v` stack minimum, guard untouched | +N B .bss, stack heap→.bss (no repro claims) | possible |

Reading:
- H1.4 / H1.5 reproduce with the reconstruction at production size, with a canary / watchpoint halt or a damaged area below
  render0 ⇒ H1a confirmed. Plus core 1 in `loop()`'s wait ⇒ H1b.
- H1.4 never hangs and leaves the predicted ~490 B: H1a is not supported. The hang stays unexplained (the round-2 tree
  is only reconstructed), and the per-Tube scratch is then hygiene, not the fix. Then look at H1c / H1d: like g1, the
  2026-11-06 hang showed at the next esptool reset.
- H1.7 only says whether an overflow is caught and recovers. It is not evidence about 2026-11-06.
- H1.8 removing a wedge ⇒ H1c, and upstream item 1 below.

## Hang 2: 120 MHz wedges

**Status 2026-11-09: done.** Out-of-spec flash (H2a) plus a dead USB CDC after CPU-only resets (the "wedge" left the app
running). In-spec HPM-DC with the DC-aware bootloader and the USB re-enumeration fix passed the board session and a
30-cycle restart soak (below). 120 MHz is now env lcd316's default: platformio.ini carries the recipe, firmware/bootloader-dc/
+ tools/bootloader-dc.sh rebuild the tested bootloader byte for byte, flash-win.sh writes it with `--full` and refuses an
app-only flash onto another bootloader, `v` shows `boot-dc`. H2.6 / H2.8 / H2.9 not needed.

Hypotheses:
- **H2a** the flash read above its rating (no HPM for this ID).
- **H2b** GDMA / preload traffic on PSRAM at the MSPI reset in `esp_restart_noos` (tile channels unhandled).
- **H2c** boot-time MSPI tuning picks a marginal point, so the boot loops.
- **H2d** the PSRAM or flash die left in a state only power removal clears.
- **H2e** USB not coming back.
- **H2f** the temperature retuning task changing live timing under GDMA load (g1, if no restart was involved).

| step | build / commands | captures | memory freed | risk |
|---|---|---|---|---|
| H2.0 desk | **done 2026-11-06** (Desk findings, hang 2): g1 involved restarts (flash boot, bench.py `B0`), both fine; bench + swing finished; the wedge showed at the next esptool USB reset, USB enumerated | g1 is reset-associated; repro = g1 + bench + swing + one esptool reset (H2.8) | — | none |
| H2.1 desk | above | — | — | none |
| H2.2 | **done 2026-11-09** (desk; Desk findings, hang 2 "H2.2 result"): flash ID 0x204018 = XMC C-generation 128 Mbit (XM25QH128C); Fast Read Quad I/O (EBh) is rated 108 MHz at the default 6 dummy cycles, 133 MHz only with DC bits set (8 dummy); the 120 MHz build read with IDF's generic 6 | **120 MHz was out of spec on this flash** (≈11 % over); H2.7 is the only in-spec 120 MHz configuration | — | none |
| H2.3 | 120 MHz build (recipe) + aids 1-4, 8: `tools/flash-win.sh --env lcd316 --res 320w10-8-6 --tubes 3 COM7` (E0 first in that session) | banner, `v` (`mspi`, `flash`, `hpm-dc 0`, `boot`) | none | possible (one boot wedge was seen) |
| H2.4 | one restart: `tools/rloop.py --port COM7 -n 1 --stop-on-fail` (fast mode), one announced action per restart; repeat only on the user's "ready" | per restart: kept / dropped, ROM `rst:` + `Saved PC`, banner reason, boot count; on failure Step W at once | none | likely |
| H2.5 | the restart from the BLE window: `tools/device.py B1`, wait for `ready`, `tools/device.py B0` (bench.py's path, BT controller running); one per action | as H2.4 | none | likely |
| H2.6 | H2b: + a shutdown handler that stops the tile GDMA channels and waits for idle (next to `preload_shutdown`; normal context, IDF APIs allowed), repeat H2.4 | the rate with / without | none | likely |
| H2.7 | H2a; **required before any other 120 MHz step** (H2.2: out of spec without it). **Explicit images, no factory bin**: (1) build a DC-aware bootloader with the local IDF 5.5.5 (`framework-espidf`, a scratch IDF project with this sdkconfig + `CONFIG_BOOTLOADER_FLASH_DC_AWARE=y`, `idf.py bootloader`); verify `bootloader_spi_flash_reset` in its ELF and `esptool image-info` = flash mode **DOUT**, 80m; (2) build the app with the same option in `custom_sdkconfig` (`pio run`, not flash-win.sh); (3) in one download session: `$ESPT read-flash 0x0 0x8000 boot-orig.bin` (rollback copy), then `$ESPT write-flash --flash-mode keep 0x0 bootloader-dc.bin 0x10000 .pio/build/lcd316/firmware.bin` (NVS and partitions untouched), then `$ESPT verify-flash 0x0 bootloader-dc.bin`; (4) boot: `v` = `hpm-dc 1`; then H2.4 | wedges gone with in-spec flash ⇒ H2a. Rollback: `write-flash 0x0 boot-orig.bin` + a non-DC app in one session | none | likely (bootloader change) |
| H2.8 | H2f / g1 repro (per H2.0): + `CONFIG_SPIRAM_TIMING_TUNING_POINT_VIA_TEMPERATURE_SENSOR=y` (flash vendor 0x20: supported), flash, `tools/bench.py --preset bench/lcd-1105.json` (its `B0` = one restart), `tools/swing.py COM7 60 '-1,0>0.6,0@3'`; then, as its own announced action, **one esptool reset** (`$ESPT chip-id`), with Step W's listener started first. Optionally first a 5 min swing with OpenOCD attached (attach only) | does the wedge need the reset (chip alive until `chip-id`) or does it hang during / after the swing (listener silent before the reset); the retuning task's PC and the MSPI registers | the PSRAM timing task's 5 KB stack must fit: fast mode | likely |
| H2.9 | only for an upstream report: `git apply docs/lcd316-refill-dma.patch`, `-DREFILL_DMA=1`, 120 MHz | Step W at boot | none | likely |

### H2.7 prepared (2026-11-09, host only; nothing flashed)

**Images** (all in `C:\Users\i00109058\lwtools\jtag\h27\`, sha256 in `SHA256SUMS`):

| file | what | header | checks |
|---|---|---|---|
| `bootloader-dc.bin` (`fec269a9…`) | IDF 5.5.5 bootloader, DC-aware | DOUT, 80m, 16MB (`e9 03 03 4f`), entry 0x403c88b8, checksum + hash valid | `bootloader_spi_flash_reset` present (flash reset at boot clears the DC bits), plus `bootloader_flash_xmc_startup` and `bootloader_enable_qio_mode` |
| `app-120-4b25269a.bin` (`264e7d80…`, ELF in `.compare/elf/4b25269a.*`) | current tree + aids, flash + PSRAM 120 MHz, HPM-DC | DIO, 80m (the header tops out at 80m; the app switches to 120), 16MB | HPM table has 6 entries; [1] = "dummy sr3-bit01", whose probe matches 0x204017 / 0x204018 (literal compare in `spi_flash_hpm_probe_chip_with_dummy`); `spi_flash_hpm_get_dummy_xmc` and `s_hpm_dummy_changed` present. The 80 MHz build has no HPM table |
| `app-80-aids-3d41d605.bin` | the aids production build now on the board (rollback) | DIO, 80m, 16MB | — |
| `bootloader-pio-80-fallback.bin` (`31b3c1be…`) | pio's 80 MHz bootloader (Arduino prebuilt) | DIO, 80m, 16MB | its segments (0x10cc @0x3fce2820, 0xc2c @0x403c8700, 0x30b0 @0x403cb700) equal the ROM's `load:` lines on the board, so it is very likely the board's current bootloader. Rollback if `boot-orig.bin` is missing |
| `partitions-80.bin` = `partitions-120.bin` (`bd0f7954…`) | partition table, identical for both | — | |

**Build provenance:**
- Bootloader: scratchpad `h27/dcboot` (minimal IDF project). `sdkconfig.defaults` is the lcd316 libs sdkconfig plus
  `ESPTOOLPY_FLASHFREQ_120M`, `SPIRAM_SPEED_120M`, `SPI_FLASH_HPM_ENA`, `SPI_FLASH_HPM_DC_AUTO`,
  `BOOTLOADER_FLASH_DC_AWARE` and the custom partition table. Built with cmake + ninja. idf.py needs PyYAML, which is
  not installed; the image was made with esptool 5.3 `elf2image` using IDF's own arguments
  (`--flash-mode dout --flash-freq 80m --flash-size 16MB`). The bootloader log level stays ERROR, as now.
- App: a worktree of the current tree with only platformio.ini changed. In env lcd316, `custom_sdkconfig` gains
  `CONFIG_ESPTOOLPY_FLASHFREQ_120M=y`, `CONFIG_SPIRAM_SPEED_120M=y`, `CONFIG_SPI_FLASH_HPM_ENA=y` and
  `CONFIG_BOOTLOADER_FLASH_DC_AWARE=y`, plus `board_build.f_flash = 120000000L` and `board_build.f_image = 80000000L`.
- The app was built against a separate packages copy, `~/.platformio/h27/packages-lcd316` (4.3 GB), so the shared
  `packages-lcd316` and the 80 MHz production build are untouched.
- The resulting libs sdkconfig has FLASHFREQ_120M, SPIRAM_SPEED_120M, SAMPLE_MODE_STR, SPI_FLASH_UNDER_HIGH_FREQ,
  HPM_ON, HPM_DC_AUTO, **HPM_DC_ON**, DC_AWARE, 64 KB D-cache, PERF, and LCD_RGB_RESTART_IN_VSYNC off.

**Bootloader vs app configs:** compared over every ESPTOOLPY_ / BOOTLOADER_ / SPI_FLASH_HPM / XMC / partition-offset /
SECURE_ option, they differ only in the HPM choice. The bootloader has HPM_ENA; the app has HPM_AUTO, because pioarduino
did not apply that choice from custom_sdkconfig. On the S3 both give HPM_ON and HPM_DC_ON. AUTO only adds a "Read Docs
First" warning at boot, hidden at log level ERROR.

**Recipe, confirmed vs guessed:**
- Confirmed (platformio.ini comment, docs/lcd316-3tube-perf.md, KAIZEN):
  - `f_flash = 120000000L` and `f_image = 80000000L`;
  - flash and PSRAM both at 120 MHz (IDF's static asserts allow only that pair);
  - a `custom_sdkconfig` change is what rebuilds the libs.
- Guessed:
  - that the original 2026-11-05 120 MHz build used exactly `ESPTOOLPY_FLASHFREQ_120M` + `SPIRAM_SPEED_120M` (never
    committed);
  - the retuning task stays off (g1 only);
  - the bootloader's remaining options follow the libs sdkconfig rather than the board's actual bootloader, whose
    sdkconfig is unknown. Its image matches pio's prebuilt bootloader byte layout (above).
- New by design: `BOOTLOADER_FLASH_DC_AWARE` and `SPI_FLASH_HPM_ENA`.

**Prepared esptool commands.** From WSL, `cd /mnt/c` first: python.exe gets a Windows cwd.

```bash
ESPT="python.exe -m esptool --chip esp32s3 --port COM7"; H='C:\Users\i00109058\lwtools\jtag\h27'
# A1 backup (one download session; esptool's USB reset enters download mode, no-reset keeps it there)
$ESPT --before default-reset --after no-reset read-flash 0x0 0x8000 "$H\boot-orig.bin"
$ESPT --before no-reset --after no-reset read-flash 0x8000 0xC00 "$H\part-orig.bin"
#    host checks before going on: part-orig.bin == partitions-80.bin (cmp); image-info boot-orig.bin parses (DIO, 80m,
#    16MB, valid hash) and its segments equal bootloader-pio-80-fallback.bin's; sha256 of both noted
# A2 write bootloader + app (headers kept as built)
$ESPT --before no-reset --after no-reset write-flash --flash-mode keep --flash-freq keep --flash-size keep \
      0x0 "$H\bootloader-dc.bin" 0x10000 "$H\app-120-4b25269a.bin"
# A3 verify
$ESPT --before no-reset --after no-reset verify-flash 0x0 "$H\bootloader-dc.bin" 0x10000 "$H\app-120-4b25269a.bin"
# A4 boot it (hard reset; start the listener immediately after)
$ESPT --before no-reset --after hard-reset chip-id
# R1 rollback, chip reachable by esptool's USB reset
$ESPT --before default-reset --after no-reset write-flash 0x0 "$H\boot-orig.bin" 0x10000 "$H\app-80-aids-3d41d605.bin"
$ESPT --before no-reset --after no-reset verify-flash 0x0 "$H\boot-orig.bin" 0x10000 "$H\app-80-aids-3d41d605.bin"
$ESPT --before no-reset --after hard-reset chip-id
#    (no boot-orig.bin: use "$H\bootloader-pio-80-fallback.bin" at 0x0 instead)
# R2 recovery, the new bootloader does not boot (no serial, "No serial data received"; Step W capture first):
#    user: hold BOOT, tap RST, release BOOT (ROM download mode needs no bootloader), then
$ESPT --before no-reset --after no-reset write-flash 0x0 "$H\boot-orig.bin" 0x10000 "$H\app-80-aids-3d41d605.bin"
$ESPT --before no-reset --after no-reset verify-flash 0x0 "$H\boot-orig.bin" 0x10000 "$H\app-80-aids-3d41d605.bin"
#    user: press RST alone (after a manual download entry the straps stay latched: esptool's hard reset re-enters download)
```

NVS (0x9000), otadata, the coredump partition and the partition table are not written by any of these.

**Steps 1-2 done 2026-11-09 16:45:**
- A1 backups: `boot-orig.bin` (sha256 `e44c5475…`, a valid DIO/80m image, the first 19,968 B identical to
  `bootloader-pio-80-fallback.bin`, 0xFF after) and `part-orig.bin` (= `partitions-80.bin`).
- A2 / A3: hash and digest verified.
- Boot `reset usb` → `v`: `elf 4b25269a boot 7 flash 204018 hpm-dc 1`. mspi `core 00000003` (was 2),
  `din 01249249/00015555` (was 0/0), `cali 00000001` (was 0), smem din mode `01249249` (was `04924924`).
- The BLE-window heap is 8,032 B (11,312 at 80 MHz).
- The ROM lines of that boot were lost: the USB re-enumeration happens before the listener's port opens.

**Finding 2026-11-09 16:49 (120 MHz, boot 7 → 8 by the BLE-window end `esp_restart`, listener held open):**
- ROM and bootloader printed normally: `rst:0xc`, `mode:DOUT`, loads 0x10cc / 0xc30 / 0x30d0, `entry 0x403c88b8`.
- The app then sent nothing, not even the banner, and later answered no command (two `v` attempts got 0 chars).
- Yet the app runs. JTAG shows both cores rendering, and the RTC record shows boot 8 running with 5,649 frames and
  no panic. Arduino's `HWCDC connected` reads true.
- The USJ registers 0x18-0x34 and the SYSTEM USB clock / reset bits equal the healthy 80 MHz capture; the host's SOFs
  keep counting.
- The same held-open window restart at 80 MHz (step 0.3b) printed its banner.
- So the likeliest explanation of the "120 MHz wedges" is the app's USB-CDC path going dead after a CPU-only reset at
  120 MHz. capture.tcl now also reads USJ 0x04-0x48 (EP1_CONF, INT_RAW / ST / ENA, OUT_EP_ST, MEM_CONF), the USJ
  interrupt-matrix entries and the cores' INTENABLE.

**Extended capture 2026-11-09 17:00 (same dead-CDC boot 8, two samples):**
- The USJ interrupt is routed: core 1 map = CPU int 2, enabled in `intenable` 0x1300000f; core 0 map = 6, IDF's
  unused slot. HWCDC's `intr_handle` = cpu 1, intno 2, source 96.
- INT_ENA 0x20c (OUT_RECV_PKT, IN_EMPTY, BUS_RESET) and INT_ST 0.
- The ISR is alive: OUT_EP1 shows a received and consumed 2-byte packet, RX queue empty, `connected` true. The `v`
  arrived and its reply went into the ring buffer.
- TX is stuck: EP1_CONF = 0, so SERIAL_IN_EP_DATA_FREE = 0 (the IN FIFO is occupied), and IN_EMPTY raw = 0. The
  256 B ring buffer is full, holding the boot-8 banner. Nothing changes between the samples except the frame counter.
- Verdict: interrupt delivery and routing are fine. The USB IN endpoint never drains: the host takes no data from
  EP1 while still sending OUT. HWCDC cannot recover, because it re-arms and flushes only while `connected` is false.

**Board session (each line is one announced action; the listener + USB watcher run around each; OpenOCD and
capture.tcl are ready to attach without reset; any silence ⇒ Step W, then stop):**
1. **Flash** (A1 → host checks → A2 → A3 → A4). Risk likely: new bootloader, out-of-spec flash fixed.
2. **Boot and `v`:**
   - The banner and `prev:` line should be there.
   - `v` must show `hpm-dc 1`, `flash 204018`, and an `mspi` CLOCK / CORE_CLK_SEL that differs from 80 MHz
     (`clk 00010001 core 00000002` at 80).
   - If `hpm-dc 0`, stop: HPM-DC did not engage, and the setup is no better than the out-of-spec one.
3. **`B0`** (restart 1, from the BLE window, BT running), so the bench needs no `B0` of its own.
4. **Bench:**
   - `tools/bench.py --preset bench/lcd-1105.json --fix-pose --runs 2`, then `tools/swing.py COM7 60 '-1,0>0.6,0@3'`.
   - Reference at 120 MHz (2026-11-05): 48.5 pinned / 31.8 swing.
5. **`r`** (restart 2): `tools/rloop.py --port COM7 -n 1 --stop-on-fail`.
6. **`B0`** again (restart 3, from fast mode).
7. **esptool reset** (restart 4): `$ESPT chip-id` (the trigger seen in hang 1 and g1).
8. **Then the user decides:** keep 120 MHz for a soak, or R1 back to 80 MHz.

### USB re-enumeration fix (implemented 2026-11-09, host only; Astra review before flashing)

**What the fix does:**
- `diag_usb_reenum()` (src/diag.cpp) runs first in `setup()`, before `Serial.begin`.
- It acts only when the ROM reset cause of core 0 is CPU-only: 0x0B CPU0_MWDT0, 0x0C CPU0_SW (`esp_restart`, and
  every IDF panic / task-wdt / int-wdt restart, which all go through `esp_restart_noos`), 0x0D CPU0_RTC_WDT,
  0x11 CPU0_MWDT1.
- Then it detaches through the PHY pull override (SE0 for 50 ms) and re-attaches with the FS pull-up. After a 2 ms
  settle it clears the BUS_RESET latch, and only then polls INT_RAW for the host's BUS_RESET, for up to 1 s. No ISR,
  nothing allocated. (Review 2026-11-09: clearing the latch before the SE0 would let the detach's own SE0 satisfy the
  wait.)
- The boot record gets `usbReenum` and `usbWaitMs`, shown as `usb-reenum <flag> <ms> ms` in `v` and in the next boot's
  `prev:` line:
  - flags: 0 skipped, 1 forced with no BUS_RESET in 1 s, 3 forced and a BUS_RESET observed;
  - `usbWaitMs` is the time from the cleared latch to the BUS_RESET. A real host reset takes tens of ms after attach;
    ~0 ms is suspect.
- The four causes are the complete CPU-only set (0x10 / 0x12 / 0x13 are system resets). Every other cause is left
  alone: power-on / EN and system / RTC resets reset the controller with the chip. The USB-UART / USB-JTAG core resets
  (0x15 / 0x16) are not proof of a bus reset (JTAG SRST leaves the controller alone); they are simply not acted on.
- `phy_sel` and `usb_pad_enable` are not touched. They are inherited from the previous boot (internal PHY, pads on),
  which is the retained-HWCDC case this is for.
- The detach drops the whole composite device, JTAG included. Attach OpenOCD only after the boot settles; one attached
  across such a boot may need a restart. Debug builds can bypass the detach with `-DUSB_REENUM=0`.
- AMOLED: not included (diag is LCD-only; the same issue is possible there, KAIZEN).
- The TX-stall watchdog: not added (KAIZEN, it could flap with no host reading).

**Builds:**
- 80 MHz production, ELF `6dd168b3` (after the review fix; was `2691b0c4`), in `.compare/elf`.
- 120 MHz app (h27 packages, the same recipe), ELF `ef8b7a8b` (after the review fix; was `abb69e30`), staged as `h27\app-120-ef8b7a8b.bin` (sha256 `7de5d92f…`).

**Board session (each line one announced action):**
- **Before each action:** listener + USB watcher; OpenOCD / capture.tcl ready, not attached.
- **After each action:**
  - EP1 IN drains: the banner and `prev:` arrive on the held-open listener (no new port open needed), and COM7 then
    answers a `v` that shows `usb-reenum` with a plausible wait (tens of ms);
  - if the banner does not arrive or `v` stays silent despite `usb-reenum 3`, the detach did not clear the stuck
    endpoint. The next step is a `SYSTEM_USB_DEVICE_RST` pulse (PERIP_RST_EN1 bit 10) instead of, or after, the detach.
    Not implemented; that is the fallback;
  - the user asked: is the face normal, black or frozen?
  - if black or frozen: capture.tcl (now with LCD_CAM) + `panel.gdb` twice, ~1 s apart, without reset, before
    anything else.

1. **App-only flash** of the 120 MHz app at 0x10000 (the DC-aware bootloader stays):
   `$ESPT --before default-reset --after hard-reset write-flash 0x10000 "$H\app-120-ef8b7a8b.bin"`. Boot via the
   USB-UART chip reset, so expect `usb-reenum 0`.
2. **The BLE-window end restart** (≤ 180 s after boot, by itself): expect `rst:0xc`, then `usb-reenum 3 <ms>` and the
   banner on the still-open listener.
3. **`r`:** `tools/rloop.py --port COM7 -n 1 --stop-on-fail`. Expect a clean `check_restart` and `usb-reenum 3`.
4. **`B0`** (from fast mode): the same expectation.
5. **esptool reset:** `$ESPT chip-id` (the USB-JTAG chip reset), so expect `usb-reenum 0`.
6. If all pass: the bench (`--fix-pose --runs 2`) and the 60 s swing at 120 MHz on the user's ready, then the soak.

**Board session 2026-11-09 17:33-18:00, results (`ef8b7a8b`, 120 MHz HPM-DC with the USB fix):**
- Every restart type was clean, with the screen normal after each:
  - the BLE window end ×2, `r`, `B0`: `usb-reenum 3 99 ms`, and output flowed on the reopened port;
  - the esptool reset: `usb-reenum 0`, banner and `prev:` complete.
- Bench (lcd-1105, fast mode):
  - pinned 48.3 fps (render 20.62 ms), parity >12/255 off: 0;
  - step swing 31.2 / smooth swing 33.9 fps (scratchpad `swing_pinned.py`: lcd-1105 pinned by p~, 60 s each);
  - refill late 0 / restarts 0 throughout.
- 80 MHz reference (issue-1): 40.6 / 26.8 / 29.0. Old out-of-spec 120 MHz: 48.5 / 31.8.

**Restart soak 2026-11-09 18:02-18:35** (`ef8b7a8b`; scratchpad `soak.py`; log `jtag\soak-20261109.log`):
- 30 cycles (10 esptool, 10 `r`, 7 `B0`, 3 window-end), 0 anomalies, boot 7 → 37.
- `usb-reenum 3` on all 20 CPU-only resets, wait min 99 / median 99 / max 100 ms. `usb-reenum 0` on all 10 esptool
  resets.
- `hpm-dc 1` every boot; refill late 0 / restarts 0 every boot; `ready.` reached every time.
- fps unpinned 30.3-47.5.
- The USB watcher saw an unrelated second Espressif device (COM9) from 18:30:00 to about 18:32.

Always end at 80 MHz (libs rebuild), with one `v` and one bench.

Post-flash silence, seen once (2026-11-09) and not reproduced:
- The first app-only flash of the 120 MHz default (49217b75) came after ~27 min up on ef8b7a8b. COM7 was silent at
  `v` ~3 s after the reset, the face was normal, and a replug recovered it.
- 2026-11-10, all clean:
  - a flash with an immediate open (+ pinned e2e: 48.0 fps, parity 0 >12/255);
  - esptool resets with a first open at 4 s and at 8 s;
  - a flash with a first open at 3.5 s (6a35bc23, a relink of the same sources).
- After esptool hard resets (rom-rst 21) `usb-reenum 0` is expected: not a CPU-only cause.
- If it recurs: take the JTAG capture (EP1 IN / IN_EMPTY, int_raw, HWCDC connected, boot record, both PCs) before any
  replug.

Reading Step W for hang 2:
- A ROM / bootloader PC or ROM text repeating, recovered by RST only ⇒ a boot loop (H2c / H2d). The SPI0/1 dump says
  at which speed and timing point it fails.
- A core stuck in `esp_restart_noos` with DCACHE_PRELOAD ena = 1 or a GDMA channel busy ⇒ H2b.
- No USB and RST recovers ⇒ H2e plus a failure before USB init. Only the boot record, coredump or UART0 can say more.
- Gone with H2.6 ⇒ H2b. Gone only with H2.7 ⇒ H2a. Only with live retuning, without a restart ⇒ H2f.

## Upstream or ours

- **Ours:**
  - stack sizing (H1a);
  - a missing watchdog on core 1 (H1b);
  - tile GDMA without a shutdown handler (H2b, if the hang needs our channels);
  - a flash run above its rating (H2a);
  - experimental options misbehaving within their documented risk (octal PSRAM 120 MHz, retuning: H2f).
- **Upstream ESP-IDF** when the hang reproduces with documented, supported configuration and stock drivers, with a
  captured location inside IDF:
  1. `esp_restart_noos`, and the panic path that skips shutdown handlers, disabling the caches / resetting the MSPI
     while a D-cache preload runs. Reproduce with the stock RGB driver's bounce-buffer mode (it preloads the same way;
     our refill off): hang until the RTC WDT, PC in `esp_restart_noos`, PRELOAD_CTRL ena = 1. Already in BACKLOG.
  2. The RGB driver's `LCD_RGB_RESTART_IN_VSYNC` EOF-count issue (BACKLOG; not a hang).
  3. A 120 MHz wedge only with in-spec flash (H2.7) and without our GDMA traffic. For octal PSRAM 120 MHz and
     retuning: only with a minimal IDF example.
- A wedge that only power removal clears, with every chip reset failing, is reportable as such. List the reset types
  tried (USB-JTAG, RTC WDT, EN) and the register state.

## Hang 3: closed (fixed)

Evidence is in "Desk findings". Optional board check, if the user wants it (risk possible: a task-wdt reboot if it were
not fixed; 80 MHz):
- `tools/device.py 'p~fizz=1' 'p~tubeHeight=72'`, wait 5 s, then `tools/device.py 'p~tubeHeight=55'`, ×6 (the 2026-09
  repro reset 2/6).
- Watch the aids' boot count, then restore from `p?`.

## Files (write to `$J`)

`$J/relay.py`: stdio to TCP, for `target remote | …`. Tested on Linux against an echo server: binary-clean.
```python
# stdio <-> TCP relay: GDB in WSL runs `target remote | python.exe -u relay.py [host] [port]` and reaches OpenOCD on Windows' loopback.
import os, socket, sys, threading
if os.name == 'nt':
    import msvcrt; msvcrt.setmode(0, os.O_BINARY); msvcrt.setmode(1, os.O_BINARY)
s = socket.create_connection((sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1', int(sys.argv[2]) if len(sys.argv) > 2 else 3333))
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
def up():
    while True:
        b = os.read(0, 65536)
        if not b: break
        s.sendall(b)
    try: s.shutdown(socket.SHUT_WR)
    except OSError: pass
threading.Thread(target=up, daemon=True).start()
while True:
    b = s.recv(65536)
    if not b: break
    os.write(1, b)
```

`$J/capture.tcl`: attach-only snapshot.
- Needs `TAG`.
- Optional: `REC` / `GUARD` (addresses from `xtensa-esp32s3-elf-nm $ELF`), and `HOLD` (stay halted for GDB).
```tcl
proc try {cmd} { if {[catch {uplevel 1 $cmd} msg]} { echo "FAILED: $cmd -> $msg" } elseif {$msg ne ""} { echo $msg } }
proc dump {name addr words} { echo "== $name"; try "mdw $addr $words" }
init
echo "=== $TAG [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S]"
try targets
echo "=== halt (OpenOCD's on_halt zeroes the TIMG0/1 and RTC WDT configs: WDT values below are debugger-modified)"
try {halt 2000}
foreach t {esp32s3.cpu0 esp32s3.cpu1} {
  echo "=== $t"; try "targets $t"; try "$t curstate"
  foreach r {pc ps sar a0 a1 a2 a3 a4 a5 a6 a7 windowbase windowstart exccause excvaddr epc1 epc2 epc3 epc4 epc5 epc6 debugcause intenable interrupt} { try "reg $r" }
  set sp 0
  if {![catch {capture "reg a1"} out]} { regexp {0x[0-9a-fA-F]+} $out sp }
  if {$sp >= 0x3FC88000 && $sp < 0x3FD00000} { echo "== stack from a1 $sp"; try "mdw $sp 64" } else { echo "== a1 $sp not internal SRAM: stack not read" }
}
try "targets esp32s3.cpu0"
dump "RTC_CNTL +0x00..+0x13C (RESET_STATE +0x38, STORE0-3 +0x50, WDTCONFIG0 +0x98 (debugger-modified), SW_CPU_STALL +0xBC, STORE4-7 +0xC0, USB_CONF +0x120)" 0x60008000 80
dump "SYSTEM +0x00..+0x6C (CORE_1_CONTROL_0 +0x00, CPU_PER_CONF +0x10, PERIP_CLK_EN0 +0x18, PERIP_RST_EN0 +0x20, SYSCLK_CONF +0x60)" 0x600C0000 28
dump "TIMG0 WDTCONFIG0.. +0x48..+0x64 (debugger-modified)" 0x6001F048 8
dump "TIMG1 WDTCONFIG0.. +0x48..+0x64 (debugger-modified)" 0x60020048 8
dump "SPI0 cache<->flash/PSRAM +0x00..+0xFC" 0x60003000 64
dump "SPI1 flash ops +0x00..+0xFC" 0x60002000 64
dump "EXTMEM +0x00..+0x13C (DCACHE_CTRL +0, PRELOAD_CTRL +0x40, ICACHE_CTRL +0x60, ILG_INT_ST +0xE4, ACS_CACHE_INT_ST +0xF0/+0xFC, DBUS/IBUS_REJECT +0x100/+0x108, MMU_FAULT +0x120/+0x124, CACHE_STATE +0x130)" 0x600C4000 80
dump "USB_SERIAL_JTAG +0x04..+0x48 (EP1_CONF +0x04, INT_RAW/ST/ENA +0x08/+0x0C/+0x10, CONF0 +0x18, JFIFO_ST +0x20, FRAM_NUM +0x24, IN_EP0-3_ST +0x28.., OUT_EP0-2_ST +0x38.., MISC +0x44, MEM_CONF +0x48; +0x00 is the FIFO: never read)" 0x60038004 18
dump "USB_SERIAL_JTAG interrupt matrix: core0 map +0x180, core1 map +0x980 (CPU interrupt number the USJ source routes to)" 0x600C2180 1
dump "core1 USJ map" 0x600C2980 1
dump "GDMA ch0-4, 0xC0 each (IN_CONF0 +0, IN_LINK +0x20, IN_STATE +0x24, OUT_CONF0 +0x60, OUT_LINK +0x80, OUT_STATE +0x84)" 0x6003F000 240
dump "LCD_CAM +0x00..+0x7C (LCD_CLOCK +0, LCD_USER +0x14 (bit 27 lcd_start), LCD_MISC +0x18, LCD_CTRL +0x1C, CTRL1/2 +0x20/+0x24, LC_DMA_INT_ENA/RAW/ST +0x64/+0x68/+0x6C)" 0x60041000 32
echo "== flash chip (device_id, chip_size)"
if {![catch {read_memory 0x3FCEFFE4 32 1} p]} { try "mdw [lindex $p 0] 2" }
if {[info exists REC]} { dump "boot record" $REC 16 }
if {[info exists GUARD]} { dump "render0 guard" $GUARD 64 }
if {[info exists HOLD]} { echo "=== holding halted: GDB on 3333; stop with 'shutdown' on 6666" } else { try resume; shutdown }
```

`$J/step0.gdb` (healthy board; read-only):
```
set pagination off
set confirm off
info threads
thread apply all bt 16
set trust-readonly-sections off
x/s esp_app_desc.version
x/s esp_app_desc.time
p/x esp_app_desc.app_elf_sha256
set trust-readonly-sections on
p/x esp_app_desc.app_elf_sha256
p/x ((unsigned *)(*(unsigned *)0x3fceffe4))[0]
p/x ((unsigned *)(*(unsigned *)0x3fceffe4))[1]
p 'main.cpp'::workerStackFree
p/x ((StaticTask_t *)'main.cpp'::workerTask)->pxDummy6
x/16wx (char *)((StaticTask_t *)'main.cpp'::workerTask)->pxDummy6 - 64
monitor resume
monitor targets
detach
quit
```
- The first `app_elf_sha256` is the board's, the second the ELF's.
- A `device_id` of 0x204018 would be XMC 128 Mbit.

`$J/panel.gdb` (black / frozen screen: the LCD refill path, target halted; the ELF of the flashed build):
```
set pagination off
set confirm off
p 'display_lcd316.cpp'::refillLate
p 'display_lcd316.cpp'::refillRestarts
p 'display_lcd316.cpp'::refillsInFrame
p 'display_lcd316.cpp'::eofKnown
p 'display_lcd316.cpp'::vsyncAt
p 'display_lcd316.cpp'::eofAt
p 'display_lcd316.cpp'::refillCycles
p 'display_lcd316.cpp'::preloadOff
p 'display_lcd316.cpp'::fbuf
p *(esp_rgb_panel_t *)'display_lcd316.cpp'::panel
p ((esp_rgb_panel_t *)'display_lcd316.cpp'::panel)->bounce_pos_px
p ((esp_rgb_panel_t *)'display_lcd316.cpp'::panel)->bb_eof_count
p ((esp_rgb_panel_t *)'display_lcd316.cpp'::panel)->expect_eof_count
x/8wx ((esp_rgb_panel_t *)'display_lcd316.cpp'::panel)->bounce_buffer[0]
x/8wx ((esp_rgb_panel_t *)'display_lcd316.cpp'::panel)->bounce_buffer[1]
```
Take it twice, ~1 s apart, resuming in between (the refill counters and `bounce_pos_px` must move while the scan runs).
With it, capture.tcl's GDMA and LCD_CAM dumps (the RGB panel's GDMA OUT channel, `LC_DMA_INT_RAW`, `lcd_start`)
show whether the scan stopped, the refill stalled or the panel is scanning a stale or black bounce buffer.

`$J/wedge.gdb` (OpenOCD with `ESP_RTOS none`, target halted):
```
set pagination off
set confirm off
info threads
thread apply all bt 24
info registers pc ps a0 a1 sar
x/8i $pc
```
- If only one thread is listed: `monitor targets esp32s3.cpu1`, `flushregs`, `bt 24`.
- Leave with `quit`. The chip stays halted for the recovery ladder.

`$J/usbwatch.ps1` prints USB-JTAG device changes for N s. Each `Get-PnpDevice` call takes ~0.5-1 s, so short drops
are missed. It is a hint only.
```powershell
param([int]$Seconds = 30)
$end = (Get-Date).AddSeconds($Seconds); $last = $null
while ((Get-Date) -lt $end) {
  $d = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'USB\VID_303A&PID_1001*' } |
       ForEach-Object { "$($_.Status) $($_.FriendlyName)" } | Sort-Object
  $s = if ($d) { $d -join '; ' } else { 'ABSENT' }
  if ($s -ne $last) { '{0:HH:mm:ss.fff} {1}' -f (Get-Date), $s; $last = $s }
  Start-Sleep -Milliseconds 200
}
```

`$J/listen.py` is a passive COM listener for Windows Python.
- It opens with DTR = RTS = 1 like device.py, never writes, and drops RTS before DTR on close.
- It re-opens when the port disappears and comes back, and prints `[port lost]` / `[port back]` with timestamps.
```python
import serial, sys, time
port, secs = sys.argv[1], float(sys.argv[2] if len(sys.argv) > 2 else 10)
end = time.time() + secs; s = None
def stamp(m): sys.stdout.write(f'\n[{time.strftime("%H:%M:%S")} {m}]\n'); sys.stdout.flush()
while time.time() < end:
    if s is None:
        try:
            s = serial.Serial(); s.port = port; s.baudrate = 115200; s.timeout = 0.2
            s.dtr = True; s.rts = True; s.open(); stamp('port open')
        except Exception: s = None; time.sleep(0.2); continue
    try:
        b = s.read(4096)
        if b: sys.stdout.write(b.decode('utf-8', 'replace')); sys.stdout.flush()
    except Exception:
        stamp('port lost'); s = None
if s is not None:
    s.rts = False; s.dtr = False; s.close()
```

## First session with the user (order)

1. **Step 0** (0.4 and 0.6 are "possible": announced, one at a time). It validates the tooling and gives the flash ID
   and render0's stack position.
2. H1.0 and H2.0 are done (desk, 2026-11-06).
3. **H1.2**, the aids flash, with **E0** in the same esptool session (one "possible" action).
4. **H1.4**, then H1.5 (one "likely" action each), and only then the rest of hang 1.
5. Hang 2 after hang 1 is settled, from H2.2 / H2.3.
