1. **NVS migration ignores I/O failures.** A failed `getBytes` can overwrite the saved look with defaults. A failed `putBytes` followed by a successful `putUInt` labels the old blob v32. Require both byte counts to equal `sizeof(Params)` before advancing, and report success only after the CRC write returns 4. [main.cpp:145](/home/andrey/_PROJECTS/watches-edge-shade/firmware/src/main.cpp:145)

2. **The generator can select different flags from the firmware.** For `-DRENDER_H=240 -DRENDER_H=288 -DRENDER_H=240`, PlatformIO selects 240 and the generator selects 288. It also drops the operand of `-D TUBE_COUNT=3`. Use PlatformIO’s parsed definitions in order. [gen_rod_rays.py:30](/home/andrey/_PROJECTS/watches-edge-shade/firmware/tools/gen_rod_rays.py:30)

3. **The geometry guard reads past a short tube map.** A three-tube build with a two-tube header reads `ROD_GEN_OF[2]` before it can reject the mismatch. Add a `static_assert` that the map length equals `TUBE_COUNT`. [render.cpp:5603](/home/andrey/_PROJECTS/watches-edge-shade/firmware/src/render.cpp:5603)

4. **The A/B renderer inherits the primary canvas’s table.** With native 320 and `AB_COMPARE=256`, the computed pitches differ, so the secondary renderer would refuse initialization once its pre-existing compile failure is cleared. Undefine `ROD_RAYS_GEN` before its `render.cpp` include to use its boot-time table. [render_ab.cpp:24](/home/andrey/_PROJECTS/watches-edge-shade/firmware/src/render_ab.cpp:24)

5. **The `milk-big` error starts in the hard-edge glow.** At 240f, the lens copies row 18 to `(276,17)`. Continuous glow blending leaves `0x2103` under the band, while firmware’s `T=10` gives `0x2104`. Using `blend565T` with `opacityT(a)` for both non-trace hard-edge glow writes changed the final pixel from `0x3164` to firmware’s `0x3166`. In-memory replay left **zero pixels above 12/255**. [render.ts:1894](/home/andrey/_PROJECTS/watches-edge-shade/sim/src/render.ts:1894)

**settled**

- **1 · Plateau.** Firmware, sim and oracle reject off-tube and TIR rays before pooling. Empty rows inherit the solved plateau. An empty plateau takes `1−s`. The 72-row pin gives **K=35** on rows 0–12 and **223** on row 35.
- **2 · NVS layout and power loss.** Both layouts are 720 bytes. Shape replaces power at byte 108. The exact-size gate, shape `1.5`, version `32` and CRC `static_assert` check out. A reset between successful blob and CRC writes safely repeats the migration.
- **Ray tables.** The generated 320w8-8 table matched all **131,072 bytes** of the host fallback. Hex floats preserve the values. Equal rods share one immutable table and retain separate per-tube sums. With a correctly sized map, a radius or pitch mismatch visibly disables the face.
- **3 · Blood-big.** The final band write matches firmware’s opacity rounding. Keep it.
- **4–5 · Quantization.** Shape clamps before the integer cast. Both contrast-floor paths use the float32 opacity quantizer. `.50195312` gives `T=129` and `0x6800`.

Read-only host review. No serial access.
