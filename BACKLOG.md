# BACKLOG
*todos and nice-to-haves*

## Power Management

- find out levels of sleep and how much they differ
- create extra playground firmware for measuring power consumption
- measure components in various conditions (e.g. display by itself without updates, with max/min brightness)

## BLE
- review/polish (was one-shoted)
- ensure webpage works even when we are already connected
- tests
- running BLE symbol when connecting, fixed when connected -
probably another "digit" in the same font

## UX
- taps for control: turning ble/wifi on
- taps for control: setting time?

## UI
- if we are ever able to measure pulse - end of liquid pumping as pulse
- different warping of glass and of liquid from glass for digits/ticks lying at the bottom
- work on bubble(s) realism, useless now
- surface lean on tilt should depend on the tube's inner width (narrow 6 mm vs wide 8 mm lens): keep capillarity
stronger than real life, but the curvature / angle a tilt gives should scale with the width, not be one preset
number (now angleTiltGain / angleMax; vertical mode uses the real tilt up to 45°)

## General
- Connection over Wi-Fi? How? Strich/QR displayed?
- App? Or just BLE/Wi-Fi?
- Softened metall ball to fill weight shift when tilting
