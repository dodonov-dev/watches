# Desk housing: parts (verified links, 2026-11-13)

## Current order list: prototype (2026-11-14)

The authoritative list. Everything further down is history and alternatives.

**Prints (FDM; files in `cad/desk/out/`):**

| File | Material | Note |
|---|---|---|
| `shell.stl` | PLA Matte, black or ivory | print upside down (top on the bed) |
| `lid.stl` | PLA Matte, same colour | flat plate, 4 magnet holes |
| `teststrip.stl` | PLA Matte, same colour as the shell | judges the slot width, edge profile and chamfer light spill |
| `logo-inlays.stl` | PLA/PETG Translucent, white/natural (or amber for contrast) | 3 clearance sets; print flat as it lies |

**Components:**

| Part | Status | Where / search | Must have |
|---|---|---|---|
| 90° USB-C adapter | user ordering | MOGOOD (Amazon) | bends over its flat side; listing: plug 8, body 7 × 12 × 21 (the model is built for it) |
| Battery | user picked | 3000 mAh, 10 × 35 × 68 | plug MX1.25 / Molex 1.25 / Micro JST 1.25 2-pin (not PH 2.0, not GH); polarity: red to "+" |
| Magnets Ø2 × 1 (8 used) | to order | supermagnete S-02-01-N (link below) or Amazon `Neodym Magnete 2x1 mm rund` | glued in, polarity by stacking |
| Warm-white LEDs | to order | Amazon `vorverdrahtete LED warmweiß 3V` / `SMD LED 0603 mit Kabel warmweiß`, or Schönwitz 50058 (below) | ~100 Ω at 3.3 V if no resistor |
| Kapton tape | to order | Amazon `Kapton Klebeband` | insulates the battery from the board's back |
| Board tape | user has | – | small patches; the far-end strip ≤ 1.5 wide |
| LED power cable (optional) | – | Amazon `JST SH 1.0 4 Pin Kabel` / Qwiic | 3V3 from the I2C/UART header, or solder to a 3V3 pad |
| Diffuser film (optional) | only if the inlays don't diffuse enough | Amazon `Lichtstreufolie` | 0.2–0.5 mm opal |

**Not needed for the prototype:** USB-C breakout, MX1.25 4-pin cable, USB-C panel extension, latching button,
opal acrylic (wood stage), tesa 4965.

Each link below was opened and checked. Prices include VAT and exclude shipping. Amazon.de could not be verified by the
tools used (503), so there are no Amazon links. agy's first list was mostly wrong links; don't reuse it.

| Item | Pick | Link | Price | Notes |
|---|---|---|---|---|
| ~~USB-C panel extension~~ (superseded: breakout below) | partsdata HX-M2-02, 20 cm, flange | https://www.partsdata.de/USB-Type-C-Panel-Montagekabel-Buchse-Stecker-20cm/HX-M2-02 | 13.96 € (+3.99 shipping), 3 in stock | Cut-out ~9 × 3.5, screws 4-40 at ~25 mm. 10 Gb/s class, so D± are almost certainly wired, but the page doesn't list them. Straight male, round cable. |
| alt | BerryBase Adafruit ADA6069, 30 cm, round threaded | https://www.berrybase.de/adafruit-usb-c-panel-mount-verlaengerungskabel-rund-mit-gewinde-und-schutzkappe-30cm | 4.30 € | 12–18 mm round hole, nut. USB 2.0 data not stated: continuity-test D± before trusting it. |
| Logo LEDs | Schönwitz 50058, 0603 warm white, enamelled wire, 10 pcs | https://www.modellbahnshop.de/en/schoenwitz-50058-led-smd-0603-with-kupferlackdraht-warmweiss-10-stueck/pd/212395 | 14.90 € | Bare LEDs, no resistor. At 3.3 V, Vf ~2.8: 100 Ω ≈ 5 mA, 47 Ω ≈ 10 mA. Pick on the bench. |
| JST SH1.0 4-pin cable | BerryBase Adafruit ADA4399, 300 mm, both ends | https://www.berrybase.de/adafruit-jst-sh-4-pin-kabel-1-mm-pitch-fuer-stemma-qt-und-qwiic-i2c-gnd-sda-scl-3-3-v | ~1.3–2 € | Cut in half → 2 pigtails. Check the pin order against the board's silkscreen. |
| Battery | BerryBase Soldered 103048, 1500 mAh, PCM | https://www.berrybase.de/soldered-li-ion-akku-lithium-polymer-103048-3-7v-1500mah-mit-2-pin-jst-stecker | 8.15 € | 47.7 × 29.5 × 9.9, JST-PH 2.0 plug, so splice to: |
| battery pigtail | BerryBase Adafruit ADA3922, PicoBlade 1.25 2-pin, 200 mm | https://www.berrybase.de/adafruit-molex-picoblade-kabel-2-polig-200mm-1.25mm-pitch-reibungsverriegelung | 1.30 € | Meter the polarity (board: + left, back view, USB up, per silkscreen) before plugging in. |
| Opal acrylic | diconfa XT opal, 25 % transmission, 3 mm, from 100 × 100 | https://diconfa.de/en/acrylic-sheet-xt-opal-white-frosted-25-light-transmission-3-6-mm-100x100-1000x2000-mm-pmma/ | ~3 € + 3.45 shipping | Wood-stage only. plattenzuschnitt24 "opal" is 3 % transmission (opaque): avoid. |
| Thin tape | Reichelt tesa 4965, 12 mm × 50 m | https://www.reichelt.de/de/de/shop/produkt/doppelseitiges_klebeband_tesafix_temperaturbestaendig-214830 | 20.95 € | Only needed if the board is taped. With the back panel + foam design it isn't. |

Not found in German shops: a flat FPC or right-angle USB-C panel extension (Pimoroni UK has a right-angle 25 cm, on
pre-order), a 7 mm latching panel button, and a LiPo ≤ 30 mm wide with a 1.25 mm plug already fitted.

## Revised (2026-11-13, later): USB through the board's J5 "USB" header, lid magnets

The board's J5 (4-pin: VBUS, U_N, U_P, GND) is the same net as the Type-C J2 (schematic). A breakout socket wired to
it gives data and charging. J5 is **MX1.25 4-pin** (Waveshare product page: "MX1.25 4PIN USB header", I2C SH1.0 4PIN), so the SH1.0 cable does not fit it: it needs an MX1.25 / PicoBlade 1.25 4-pin pigtail (not yet sourced; check the board's box first).

| Item | Pick | Link | Price | Notes |
|---|---|---|---|---|
| USB-C breakout | Pololu 2585 (usb07a) via exp-tech.de | https://exp-tech.de/products/usb-20-type-c-connector-breakout-board-usb07a | 4.50 € excl. VAT, 14 in stock, 2–3 days | Pololu page: 5.11 kΩ on CC1 + CC2, D± broken out, 20.3 × 14 mm (15.2 with the connector), 2 × Ø2.2 holes (M2). Spacing not stated. |
| alt | Adafruit 4090 via BerryBase | https://www.berrybase.de/en/adafruit-usb-type-c-breakout-board-downstream-connection | 3.25 € | Out of stock. 20.4 × 14.2 × 5.0, 5.1 kΩ CC, D±. |
| Lid magnets | supermagnete.de S-02-01-N, Ø2 × 1, N48, 20 pcs | https://www.supermagnete.de/eng/disc-magnets-neodymium/disc-magnet-2mm-1mm_S-02-01-N | 4.00 € | ~110 g each. Fits a 3 mm wall. |
| alt | supermagnete.de S-03-02-N, Ø3 × 2, 20 pcs | https://www.supermagnete.de/eng/disc-magnets-neodymium/disc-magnet-3mm-2mm_S-03-02-N | 4.80 € | ~300 g each; needs ≥ 4 mm walls. |

**Later variant (not v1):** instead of J5 + an MX1.25 cable, use a 90° angled USB-C data cable (A→C): cut off the A end
and solder its 4 wires (VBUS, GND, D−, D+; a charge-only cable has only 2) to the breakout. It plugs into the board's
own Type-C port. The chin grows ~2–4 mm (a straight plug would need ~25–35 mm). Measure the plug before changing the chin.
