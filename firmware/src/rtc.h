// PCF85063 real-time clock (boards with HAS_RTC, board.h) on the board I2C bus (Wire begun by setup).
// Holds the firmware's wall clock: local seconds, no zone (the same value setClockLocal puts in the system time).
#pragma once
#include <time.h>

// Call once at boot: Arduino's I2C layer allocates a device handle on the first transaction to an address.
// False = the RTC did not answer; rtc_read / rtc_write then fail without touching the bus.
bool rtc_init(void);
// False when the RTC is absent or unreadable, its oscillator stopped since the last set (power lost without a
// backup cell), or it was never set by this firmware (factory or random contents).
bool rtc_read(time_t &localSec);
bool rtc_write(time_t localSec);    // years 2000..2099; clears the oscillator-stop flag
