# bootloader-dc

DC-aware 2nd-stage bootloader for env lcd316 (flash + PSRAM 120 MHz, HPM dummy-cycle mode).

- Why: the XMC XM25QH128C is in spec at 120 MHz only with its DC bits set (the app does it: `SPI_FLASH_HPM_ENA`). The
  bits survive a CPU-only reset; only a bootloader with `BOOTLOADER_FLASH_DC_AWARE` resets the flash before reading
  it. Arduino's prebuilt one does not, and pioarduino's hybrid build never rebuilds it: an HPM-DC app on it wedges at
  the next reset.
- Build: `tools/bootloader-dc.sh` (cmake + ninja with the IDF 5.5.5 of `~/.platformio/packages-lcd316`, into
  `.pio/bootloader-dc/`; no new installs). Exits 1 unless the image's sha256 equals `bootloader-dc.sha256`.
- Byte-identical to the image tested on the board 2026-11-09 (`bootloader-dc.bin`, `fec269a9…`, docs/hang-investigation-plan.md
  H2.7): the compile date is pinned with `SOURCE_DATE_EPOCH`. Header DOUT / 80m / 16MB; validation hash `6153b170…`
  (`BOOT_DC_DIGEST` in src/diag.cpp).
- `sdkconfig.defaults`: only what reaches the bootloader image (checked line by line); the app's flash options sit in
  platformio.ini.
- Flashing: `tools/flash.sh --env lcd316 --full` writes it (+ partition table, otadata, app; headers kept, NVS kept) and
  verifies it. App-only flashes check the board's 0x0 against it first and refuse on a mismatch. Never
  `pio run -t upload` or pio's `firmware.factory.bin` for lcd316: both carry Arduino's bootloader.
- On the board: `v` shows `boot-dc 1`; `0-MISMATCH` plus a banner warning = HPM-DC app on a non-DC bootloader.
- A deliberate change: edit, `tools/bootloader-dc.sh --any-sha`, put the new sha256 into `bootloader-dc.sha256` and the
  new validation hash (`esptool image-info`) into `BOOT_DC_DIGEST`, then `--full` and a restart soak.
