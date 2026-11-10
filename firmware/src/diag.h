// Hang diagnostics (docs/hang-investigation-plan.md "Firmware aids"): a boot record in RTC memory that survives
// software / watchdog / panic resets, a panic breadcrumb (esp_core_dump_write wrapped, see platformio.ini), the last
// coredump's summary cached at boot, and the `v` / `C` fields. All state is static; nothing allocates after boot
// (the coredump summary is read once in diag_boot, the only place its IDF calls may allocate).
#pragma once
#include <stdint.h>
#include <Print.h>

enum DiagStage : uint8_t {
  DIAG_NONE = 0,
  DIAG_EARLY,         // IDF CORE init fn (priority 1): after the CPU-start MSPI tuning / PSRAM init, before any C++ constructor
  DIAG_SETUP,         // setup() entered
  DIAG_DISPLAY,       // display_init done
  DIAG_RENDER,        // render_init / physics_init done
  DIAG_BLE,           // BLE init starting (window boots only)
  DIAG_READY,         // setup() done
  DIAG_RUNNING,       // at least one frame since boot
  DIAG_RESTART_REQ,   // r / B0 / B1 / BLE window end asked for esp_restart
  DIAG_SHUT_FIRST,    // the first shutdown handler ran (esp_restart entered)
  DIAG_PRELOAD_DONE,  // preload_shutdown finished its wait (drained or timed out: the record's preload field)
  DIAG_SHUT_LAST,     // our last shutdown handler ran: next esp_timer's, then esp_restart_noos
  DIAG_PANIC,         // a panic (fault, task / interrupt watchdog, abort) reached the coredump write
  DIAG_GUARD,         // -DSTACK_GUARD: render0's guard below its stack was overwritten
};

#ifdef BOARD_LCD316   // LCD only: the AMOLED build has no static RAM to spare (its 88.4 KB bar)
void diag_boot(Print &out);      // first thing in setup(): prints the previous boot's record and the cached coredump
void diag_setup_done();          // last thing in setup(): registers the first-running shutdown handler
void diag_stage(uint8_t stage);  // normal task context only
void diag_frame(uint32_t workerFree, uint32_t loopFree);   // once per rendered frame
void diag_cmd(char c);           // each serial command
void diag_print_v(Print &out);   // the extra `v` fields (same line, no newline)
void diag_print_core(Print &out);   // `C`: the cached coredump summary
void diag_usb_reenum();          // first in setup(), before Serial.begin: host re-enumeration after a CPU-only reset
void diag_preload(bool drained);  // display_lcd316.cpp preload_shutdown: the drain's result, kept through SHUT_LAST
#define DIAG_LINE_MAX 448          // worst case: the `v` line (prefix ~90 B + diag fields ~300 B)
size_t diag_printf(Print &out, const char *fmt, ...) __attribute__((format(printf, 2, 3)));   // no heap (diag.cpp)
#else
inline void diag_boot(Print &) {}
inline void diag_setup_done() {}
inline void diag_stage(uint8_t) {}
inline void diag_frame(uint32_t, uint32_t) {}
inline void diag_cmd(char) {}
inline void diag_print_v(Print &) {}
inline void diag_print_core(Print &out) { out.println("coredump: not in this build"); }
inline void diag_preload(bool) {}
inline void diag_usb_reenum() {}
#define diag_printf(out, ...) (out).printf(__VA_ARGS__)   // AMOLED: no RAM for the static line buffer
#endif

#if defined(LOOP_WDT) && defined(BOARD_LCD316)
void diag_loop_wdt_init(Print &out);   // setup(): subscribes loopTask to the task watchdog, once
void diag_feed();                      // end of each loop() iteration, and inside long commands (x, X)
#else
inline void diag_loop_wdt_init(Print &) {}
inline void diag_feed() {}
#endif
