// Minimal PCF85063 driver (registers per NXP PCF85063A datasheet): RAM byte 03h, then seconds..years 04h..0Ah in
// BCD, 24-hour mode (power-on default). Seconds bit 7 = OS: the oscillator stopped, the time is invalid.
#include "rtc.h"
#include <Arduino.h>
#include <Wire.h>

static const uint8_t ADDR = 0x51;
static const uint8_t REG_RAM = 0x03;
static const uint8_t MARK = 0x4C;   // RAM byte value: the time was set by this firmware
static bool present = false;        // rtc_init answered: the I2C device handle exists, later calls allocate nothing

static uint8_t bcd(int v) { return (uint8_t)((v / 10) << 4 | v % 10); }
static int unbcd(uint8_t b) { return (b >> 4) * 10 + (b & 0x0F); }
// Days from 1970-01-01 to a civil date (H. Hinnant's days_from_civil): no TZ / mktime involved.
static int64_t daysFromCivil(int y, int m, int d) {
  y -= m <= 2;
  const int era = (y >= 0 ? y : y - 399) / 400, yoe = y - era * 400;
  const int doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  return (int64_t)era * 146097 + yoe * 365 + yoe / 4 - yoe / 100 + doy - 719468;
}

bool rtc_init(void) {
  uint8_t ram;
  Wire.beginTransmission(ADDR); Wire.write(REG_RAM);
  present = Wire.endTransmission(false) == 0 && Wire.requestFrom((int)ADDR, 1) == 1 && Wire.readBytes(&ram, 1) == 1;
  return present;
}

bool rtc_read(time_t &localSec) {
  if (!present) return false;
  uint8_t b[8];   // RAM, seconds, minutes, hours, days, weekdays, months, years
  Wire.beginTransmission(ADDR); Wire.write(REG_RAM);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom((int)ADDR, (int)sizeof b) != (int)sizeof b ||
      Wire.readBytes(b, sizeof b) != sizeof b) return false;
  if (b[0] != MARK || (b[1] & 0x80)) return false;
  const int s = unbcd(b[1] & 0x7F), mi = unbcd(b[2] & 0x7F), h = unbcd(b[3] & 0x3F), d = unbcd(b[4] & 0x3F);
  const int mo = unbcd(b[6] & 0x1F), y = 2000 + unbcd(b[7]);
  if (s > 59 || mi > 59 || h > 23 || d < 1 || d > 31 || mo < 1 || mo > 12) return false;
  localSec = (time_t)(daysFromCivil(y, mo, d) * 86400 + h * 3600 + mi * 60 + s);
  return true;
}

bool rtc_write(time_t localSec) {
  if (!present) return false;
  tm t; gmtime_r(&localSec, &t);   // local seconds read as UTC = the wall clock
  if (t.tm_year < 100 || t.tm_year > 199) return false;
  const uint8_t b[9] = {REG_RAM, MARK, bcd(t.tm_sec), bcd(t.tm_min), bcd(t.tm_hour), bcd(t.tm_mday),
                        (uint8_t)t.tm_wday, bcd(t.tm_mon + 1), bcd(t.tm_year - 100)};
  Wire.beginTransmission(ADDR); Wire.write(b, sizeof b);
  return Wire.endTransmission() == 0;
}
