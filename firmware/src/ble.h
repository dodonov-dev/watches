// Nordic UART Service bridge: same line protocol as USB serial. `out` fans Serial output out to
// the connected central too (notifications chunked at MTU-3, flushed on '\n').
#pragma once
#include <Arduino.h>

// BLE runs in a window after every boot: on until a central has stayed away BLE_WINDOW_S since boot, or BLE_GRACE_S
// after a disconnect; then the board reboots into fast mode (BLE off: Arduino releases the BT controller's internal RAM
// at boot, ~50 KB with the stack's own, which the face then uses). Fast mode lasts that one boot: any reset brings the
// window back. `B0` (serial) asks for fast mode now, `B1` reboots into the window.
#define BLE_WINDOW_S 180
#define BLE_GRACE_S 15
bool ble_on();             // this boot runs BLE (decided before setup, see bleInUse in ble.cpp)
void ble_request_fast();   // reboot into fast mode (BLE off) now
void ble_tick();           // loop(): the window's timeouts
int ble_window_left_s();   // seconds until the window closes without a central (-1: connected / BLE off)
void ble_init(const char *name);
/** Bytes received from the central, queued for loop(); -1 when empty. */
int ble_read();

class DualOut : public Print {
 public:
  using Print::write;
  size_t write(uint8_t c) override;
  size_t write(const uint8_t *buf, size_t n) override;
  int available() { return Serial.available(); }
  int read() { return Serial.read(); }
  operator bool() { return (bool)Serial; }
};
extern DualOut out;
