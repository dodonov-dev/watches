// Hang diagnostics: boot record, panic breadcrumb, cached coredump summary, `v` / `C` fields (diag.h).
#include "diag.h"
#ifdef BOARD_LCD316
#include <Arduino.h>
#include <string.h>
#include "esp_attr.h"
#include "esp_system.h"
#include "esp_rom_sys.h"
#include "esp_rom_spiflash.h"
#include "esp_app_desc.h"
#include "esp_core_dump.h"
#include "esp_private/panic_internal.h"
#include "esp_private/spi_flash_os.h"
#include "esp_private/startup_internal.h"
#include <stdarg.h>
#include <stdio.h>
#include "soc/soc.h"
#include "soc/spi_mem_reg.h"
#include "soc/timer_group_reg.h"
#include "soc/rtc_cntl_reg.h"
#include "soc/reset_reasons.h"
#include "hal/usb_serial_jtag_ll.h"
#ifdef LOOP_WDT
#include "esp_task_wdt.h"
#endif

// The record lives in RTC memory (RTC_NOINIT: not cleared by software, watchdog or panic resets; garbage after a
// power-on, not guaranteed across an EN reset). magic + a checksum over every field before it tell a valid record
// from garbage or from a write torn by a reset. Writers: the early constructor and setup (core 1, before the render
// tasks), loop() (core 1), shutdown handlers (the restarting task), the panic wrapper (any core, interrupts off).
// A panic on core 0 can tear a loop()-side update: the checksum then marks the record invalid, nothing worse.
struct LwBootRec {
  uint32_t magic;
  uint32_t boots;            // boots since the record was last invalid (power-on)
  uint32_t upMs;             // millis() at the last write
  uint32_t frames;           // frames rendered this boot
  uint32_t panicPc;          // panic_info_t addr (0: no panic this boot)
  uint8_t stage;             // DiagStage reached
  uint8_t lastCmd;           // last serial command letter
  uint8_t panicCore;
  uint8_t panicExc;          // panic_exception_t
  uint8_t panicPseudo;       // pseudo_excause (interrupt WDT, double exception, cache error ...)
  uint8_t ringPos;           // next slot of the reset-cause rings
  uint8_t preload;           // the refill preload drain at esp_restart: 0 not reached, 1 drained, 2 timed out (20 ms)
  uint8_t pad;
  uint8_t rom0[8], rom1[8];  // ROM reset causes (soc_reset_reason_t) of the last 8 boots, core 0 / core 1
  uint16_t workerMin, loopMin;   // stack high-water marks at the last frame, bytes
  uint8_t usbReenum;         // this boot's USB detach / re-attach: 0 skipped (not a CPU-only reset, or -DUSB_REENUM=0),
                             // 1 forced, no BUS_RESET within USB_REENUM_WAIT_MS, 3 forced and a BUS_RESET observed
  uint8_t pad2;
  uint16_t usbWaitMs;        // ms from the cleared latch after re-attach to the BUS_RESET (or the timeout); a real host
                             // reset comes tens of ms after attach, ~0 ms would be suspect
  uint32_t sum;              // FNV-1a over the words before it
};
static const uint32_t REC_MAGIC = 0x4c574252;   // "LWBR"
static const int REC_WORDS = (int)(offsetof(LwBootRec, sum) / 4);
static_assert(offsetof(LwBootRec, sum) % 4 == 0, "boot record checksum must be word aligned");

RTC_NOINIT_ATTR static LwBootRec rec;
static LwBootRec prevRec;    // the previous boot's record, copied by the early constructor (DRAM, static)
static bool prevValid = false;
static bool shutdownOk = true;

// IRAM: the panic wrapper calls it with the flash cache possibly unusable. Only immediates, no tables.
static uint32_t IRAM_ATTR __attribute__((noinline)) recSum(const LwBootRec *r) {
  const volatile uint32_t *w = (const volatile uint32_t *)r;
  uint32_t h = 2166136261u;
  for (int i = 0; i < REC_WORDS; i++) { h ^= w[i]; h *= 16777619u; }
  return h;
}
static inline void recSeal() { rec.sum = recSum(&rec); }

// Earliest app-side marker: an ESP-IDF system init function at the CORE stage, priority 1. start_cpu0_default runs
// do_core_init (these, by priority; IDF's own start at 10) before do_global_ctors (every C++ constructor, e.g. main.cpp's
// framebuffer allocation), and both after the CPU-start MSPI timing tuning and PSRAM init (cpu_start.c). Coverage
// boundary: a boot that dies in the ROM, the bootloader, the CPU-start code or an IDF early init leaves the previous
// boot's record untouched (boot count not advanced). Only RTC memory, .bss (zeroed by then) and ROM calls are used.
ESP_SYSTEM_INIT_FN(diag_early, CORE, BIT(0), 1) {
  prevValid = rec.magic == REC_MAGIC && rec.sum == recSum(&rec);
  prevRec = rec;
  if (!prevValid) { memset(&rec, 0, sizeof rec); rec.magic = REC_MAGIC; }
  rec.boots++;
  const int p = rec.ringPos & 7;
  rec.rom0[p] = (uint8_t)esp_rom_get_reset_reason(0); rec.rom1[p] = (uint8_t)esp_rom_get_reset_reason(1);
  rec.ringPos = (uint8_t)((p + 1) & 7);
  rec.stage = DIAG_EARLY; rec.upMs = 0; rec.frames = 0; rec.lastCmd = 0; rec.preload = 0;
  rec.panicPc = 0; rec.panicCore = rec.panicExc = rec.panicPseudo = 0; rec.workerMin = rec.loopMin = 0;
  rec.usbReenum = 0; rec.usbWaitMs = 0;
  recSeal();
  return ESP_OK;
}

// Panic breadcrumb: -Wl,--wrap=esp_core_dump_write (platformio.ini, env lcd316). The Arduino core already wraps
// esp_panic_handler (esp32-hal-misc.c), and its hook walks the backtrace with a 256 B struct on the panicking stack:
// too much for a stack-overflow panic. The coredump write is the next step of every rebooting panic (panic.c, after the
// register dump, before the flash write), so a record left at DIAG_PANIC without a new coredump means the write hung.
// Context: interrupts off, the other core stalled (it may hold any lock): plain stores to RTC memory, recSum (IRAM), no
// call into flash code; then the real coredump write. The panic itself is not altered.
extern "C" void __real_esp_core_dump_write(panic_info_t *info);
extern "C" void IRAM_ATTR __wrap_esp_core_dump_write(panic_info_t *info) {
  rec.stage = DIAG_PANIC;
  rec.panicCore = (uint8_t)info->core;
  rec.panicExc = (uint8_t)info->exception;
  rec.panicPseudo = (uint8_t)info->pseudo_excause;
  rec.panicPc = (uint32_t)info->addr;
  rec.sum = recSum(&rec);
  __real_esp_core_dump_write(info);
}

// Shutdown handlers run from the highest slot down and slots fill from 0: the one registered first runs last. Slots
// (IDF SHUTDOWN_HANDLERS_NO 5), checked in the ELF 2026-11-09: 0 esp_timer (startup), 1 shutLast, 2 preload_shutdown
// (display_init), 3 shutFirst; one spare. esp_timer's handler (system time into RTC) still runs after shutLast.
static void shutLast() { rec.stage = DIAG_SHUT_LAST; rec.upMs = millis(); recSeal(); }
static void shutFirst() { rec.stage = DIAG_SHUT_FIRST; rec.upMs = millis(); recSeal(); }

// USB detach / re-attach after a CPU-only reset (docs/hang-investigation-plan.md, 2026-11-09 dead-CDC finding).
// esp_restart, every IDF panic / task-wdt / int-wdt restart (all through esp_restart_noos) and the hardware CPU-reset
// watchdog stages reset only the CPUs: the USB-Serial-JTAG controller and the host keep their endpoint state across the
// boot. At 120 MHz the IN endpoint then never drained (the app's CDC TX dead, RX alive, JTAG alive) and HWCDC cannot
// recover. Detach (SE0 through the PHY pull override), re-attach, then wait for the host's BUS_RESET: the same idea as
// arduino-esp32's usb_switch_to_cdc_jtag() (#10857), polled instead of an ISR + semaphore (nothing allocated).
// The four causes below are the complete CPU-only set (0x10 / 0x12 / 0x13 are system resets). Other causes are left
// alone: power-on / EN, system and RTC resets reset the controller with the chip. The USB-UART / USB-JTAG causes
// (0x15 / 0x16) are core resets that need not imply a bus reset (JTAG SRST leaves the controller alone): this logic
// does not claim they re-enumerate, it only does not act on them.
// phy_sel / usb_pad_enable are not touched: they are inherited from the previous boot (internal PHY, pads on: the
// retained-HWCDC case this is for).
// Called first in setup(), before Serial.begin: the ROM's and the bootloader's output came before. The detach drops the
// whole composite USB device, JTAG included: an attached OpenOCD may need a restart (attach after the boot settles), and
// -DUSB_REENUM=0 bypasses it for debug sessions.
#ifndef USB_REENUM
#define USB_REENUM 1
#endif
#define USB_REENUM_DETACH_MS 50     // D+ held low; USB 2.0 needs > 2.5 us for a disconnect, hosts debounce ~10-100 ms
#define USB_REENUM_SETTLE_MS 2      // after re-attach: let the line state settle before the BUS_RESET latch is cleared
#define USB_REENUM_WAIT_MS 1000     // the host's BUS_RESET after re-attach (Arduino's reference waits 1 s too)
static bool cpuOnlyReset(soc_reset_reason_t r) {
  return r == RESET_REASON_CPU0_MWDT0 || r == RESET_REASON_CPU0_SW || r == RESET_REASON_CPU0_RTC_WDT || r == RESET_REASON_CPU0_MWDT1;
}
void diag_usb_reenum() {
  if (!USB_REENUM || !cpuOnlyReset(esp_rom_get_reset_reason(0))) { rec.usbReenum = 0; rec.usbWaitMs = 0; recSeal(); return; }
  usb_serial_jtag_ll_disable_intr_mask(USB_SERIAL_JTAG_LL_INTR_MASK);   // HWCDC's ISR is not installed yet: polled
  const usb_serial_jtag_pull_override_vals_t detach = {.dp_pu = false, .dm_pu = false, .dp_pd = true, .dm_pd = true};
  usb_serial_jtag_ll_phy_enable_pull_override(&detach);   // SE0: the host sees a disconnect
  delay(USB_REENUM_DETACH_MS);
  const usb_serial_jtag_pull_override_vals_t attach = {.dp_pu = true, .dm_pu = false, .dp_pd = false, .dm_pd = false};
  usb_serial_jtag_ll_phy_enable_pull_override(&attach);   // the device FS pull-up, as HWCDC::begin sets it
  usb_serial_jtag_ll_phy_disable_pull_override();
  delay(USB_REENUM_SETTLE_MS);
  // Only now clear the latch: the SE0 of the detach itself can latch BUS_RESET while the PHY stays enabled, which would
  // otherwise satisfy the wait below at once without any host.
  usb_serial_jtag_ll_clr_intsts_mask(USB_SERIAL_JTAG_INTR_BUS_RESET);
  const uint32_t t0 = millis();
  bool reset = false;
  while (millis() - t0 < USB_REENUM_WAIT_MS) {
    if (usb_serial_jtag_ll_get_intraw_mask() & USB_SERIAL_JTAG_INTR_BUS_RESET) { reset = true; break; }
    delay(1);
  }
  usb_serial_jtag_ll_clr_intsts_mask(USB_SERIAL_JTAG_INTR_BUS_RESET);
  const uint32_t waited = millis() - t0;
  rec.usbReenum = reset ? 3 : 1; rec.usbWaitMs = (uint16_t)(waited > 0xffff ? 0xffff : waited);
  recSeal();
}

// The last coredump in flash, read once at boot (its IDF calls allocate temporarily: boot only, by design).
static esp_core_dump_summary_t coreSum;
static bool coreValid = false;

// Formatted output without Arduino's Print::vprintf, which mallocs for 64 B and more: one static worst-case line
// buffer (loop task only: setup, serial commands), truncation flagged in the output itself.
static char diagLine[DIAG_LINE_MAX];
size_t diag_printf(Print &out, const char *fmt, ...) {
  va_list ap; va_start(ap, fmt);
  const int n = vsnprintf(diagLine, sizeof diagLine, fmt, ap);
  va_end(ap);
  if (n < 0) return 0;
  size_t len = (size_t)n;
  if (len >= sizeof diagLine) {   // truncated: say so in the line
    static const char T[] = " [TRUNC]";
    len = sizeof diagLine - 1;
    memcpy(diagLine + len - (sizeof T - 1), T, sizeof T - 1);
  }
  return out.write((const uint8_t *)diagLine, len);
}

static const char *stageName(uint8_t s) {
  static const char *const N[] = {"none", "early", "setup", "display", "render", "ble", "ready", "running", "restart-req",
                                  "shut-first", "preload-done", "shut-last", "panic", "guard"};
  return s < sizeof N / sizeof N[0] ? N[s] : "?";
}

void diag_boot(Print &out) {
  if (prevValid) {
    const int last = (prevRec.ringPos + 7) & 7;
    diag_printf(out, "prev: boot %lu stage %s up %lu ms frames %lu cmd %c stack-free worker %u loop %u rst %u/%u",
               (unsigned long)prevRec.boots, stageName(prevRec.stage), (unsigned long)prevRec.upMs, (unsigned long)prevRec.frames,
               prevRec.lastCmd >= 32 && prevRec.lastCmd < 127 ? prevRec.lastCmd : '-', prevRec.workerMin, prevRec.loopMin,
               prevRec.rom0[last], prevRec.rom1[last]);
    if (prevRec.preload) diag_printf(out, " preload %s", prevRec.preload == 1 ? "drained" : "TIMEOUT");
    if (prevRec.usbReenum) diag_printf(out, " usb-reenum %u %u ms", prevRec.usbReenum, prevRec.usbWaitMs);
    if (prevRec.stage == DIAG_PANIC)
      diag_printf(out, " panic core %u exc %u pseudo %u pc 0x%08lx", prevRec.panicCore, prevRec.panicExc, prevRec.panicPseudo, (unsigned long)prevRec.panicPc);
    out.println();
  } else out.println("prev: none (power-on, EN reset or a torn record)");
  out.print("rst ring (core0/core1, oldest first):");
  for (int i = 0; i < 8; i++) { const int k = (rec.ringPos + i) & 7; if (rec.rom0[k] || rec.rom1[k]) diag_printf(out, " %u/%u", rec.rom0[k], rec.rom1[k]); }
  out.println();
  coreValid = esp_core_dump_image_check() == ESP_OK && esp_core_dump_get_summary(&coreSum) == ESP_OK;
  diag_print_core(out);
  shutdownOk = esp_register_shutdown_handler(shutLast) == ESP_OK;   // registered first: runs last
  rec.stage = DIAG_SETUP; rec.upMs = millis(); recSeal();
}

void diag_setup_done() {
  shutdownOk = esp_register_shutdown_handler(shutFirst) == ESP_OK && shutdownOk;   // registered last: runs first
  rec.stage = DIAG_READY; rec.upMs = millis(); recSeal();
}

void diag_stage(uint8_t stage) { rec.stage = stage; rec.upMs = millis(); recSeal(); }

void diag_preload(bool drained) { rec.preload = drained ? 1 : 2; rec.stage = DIAG_PRELOAD_DONE; rec.upMs = millis(); recSeal(); }

void diag_frame(uint32_t workerFree, uint32_t loopFree) {
  if (rec.stage < DIAG_RUNNING) rec.stage = DIAG_RUNNING;
  rec.frames++; rec.upMs = millis();
  rec.workerMin = (uint16_t)(workerFree > 0xffff ? 0xffff : workerFree); rec.loopMin = (uint16_t)(loopFree > 0xffff ? 0xffff : loopFree);
  recSeal();
}

void diag_cmd(char c) { rec.lastCmd = (uint8_t)c; recSeal(); }

void diag_print_v(Print &out) {
  char sha[9] = {0};
  esp_app_get_elf_sha256(sha, sizeof sha);
  const int last = (rec.ringPos + 7) & 7;
  diag_printf(out, " elf %s boot %lu up %lu flash %06lx hpm-dc %d rom-rst %u/%u", sha, (unsigned long)rec.boots, (unsigned long)millis(),
             (unsigned long)g_rom_flashchip.device_id, (int)spi_flash_hpm_dummy_adjust(), rec.rom0[last], rec.rom1[last]);
  diag_printf(out, " mspi clk %08lx core %08lx din %08lx/%08lx cali %08lx smem %08lx/%08lx/%08lx",
             (unsigned long)REG_READ(SPI_MEM_CLOCK_REG(0)), (unsigned long)REG_READ(SPI_MEM_CORE_CLK_SEL_REG(0)),
             (unsigned long)REG_READ(SPI_MEM_DIN_MODE_REG(0)), (unsigned long)REG_READ(SPI_MEM_DIN_NUM_REG(0)),
             (unsigned long)REG_READ(SPI_MEM_TIMING_CALI_REG(0)), (unsigned long)REG_READ(SPI_MEM_SPI_SMEM_TIMING_CALI_REG(0)),
             (unsigned long)REG_READ(SPI_MEM_SPI_SMEM_DIN_MODE_REG(0)), (unsigned long)REG_READ(SPI_MEM_SPI_SMEM_DIN_NUM_REG(0)));
  diag_printf(out, " usb-reenum %u %u ms", rec.usbReenum, rec.usbWaitMs);
  diag_printf(out, " wdt %08lx/%08lx/%08lx coredump %s shutdown %s", (unsigned long)REG_READ(TIMG_WDTCONFIG0_REG(0)),
             (unsigned long)REG_READ(TIMG_WDTCONFIG0_REG(1)), (unsigned long)REG_READ(RTC_CNTL_WDTCONFIG0_REG),
             coreValid ? "yes" : "no", shutdownOk ? "ok" : "FULL");
}

void diag_print_core(Print &out) {
  if (!coreValid) { out.println("coredump: none (or invalid)"); return; }
  const esp_core_dump_summary_t &s = coreSum;
  diag_printf(out, "coredump: task %.16s pc 0x%08lx cause %lu vaddr 0x%08lx elf %.9s bt", s.exc_task, (unsigned long)s.exc_pc,
             (unsigned long)s.ex_info.exc_cause, (unsigned long)s.ex_info.exc_vaddr, (const char *)s.app_elf_sha256);
  const uint32_t depth = s.exc_bt_info.depth < 16 ? s.exc_bt_info.depth : 16;
  for (uint32_t i = 0; i < depth; i++) diag_printf(out, " 0x%08lx", (unsigned long)s.exc_bt_info.bt[i]);
  out.println(s.exc_bt_info.corrupted ? " (corrupted)" : "");
}

#ifdef LOOP_WDT
static bool loopWdt = false;
void diag_loop_wdt_init(Print &out) {   // call from setup(): it runs in loopTask
  loopWdt = esp_task_wdt_add(nullptr) == ESP_OK;   // allocates the watchdog's entry once, here
  if (!loopWdt) out.println("FATAL: loop task watchdog not registered");
}
void diag_feed() { if (loopWdt) esp_task_wdt_reset(); }
#endif
#endif   // BOARD_LCD316
