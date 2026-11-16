# Roly-poly CAD: review by GPT-6 Astra (Codex CLI, 2026-11-15)

Subject: `cad/desk/rolypoly.py` and `cad/desk/out-rolypoly/` as first built. Numbers reproduced from the exported files.
Its `/tmp/roly-review` evidence links are scratch files and are gone after a reboot.

**The nominal mass model reproduces, but the 25° requirement has effectively no margin.** Repository unchanged; measurements and scratch scripts are in [/tmp/roly-review](/tmp/roly-review).

1. **Blocker — 25° compliance depends on unrealistically exact assumptions.** Independently measured forward limit: **25.03°**. Changing only the board to 40 g gives **23.57°**; cast density to 4.8 gives **24.68°**. Board 40 g, battery 60 g and density 4.8 also reduce the rocking margin to **7.76 mm**, failing both requirements. At nominal geometry, approximately **+0.33 g of board mass or −0.70 g of cast** consumes the forward margin. The 0.5° sampling conceals this fragility.  
   **Fix:** weigh the hardware and cured ballast; design and assert against bounded mass/position uncertainties with several degrees of reserve. Evidence: [limit calculation](cad/desk/rolypoly.py:1086), [acceptance assertions](cad/desk/rolypoly.py:1416), [independent results](/tmp/roly-review/measure.txt:23).

2. **Should fix — the bottom flat invalidates the small-amplitude rocking and trim claims.** The exported cup terminates at z **0.020**, leaving a flat footprint **2.653 × 7.474 mm**. Although shallow, it is mechanically significant: initial sideways tipping torque is approximately **3.65–4.74 mN·m**. The quoted 1.00 s period describes an ideal smooth rocker, not the final motion onto this flat.  
   Leaving out the two left segments produces **Gx = −0.173 mm**, equivalent to **−1.07°** on a smooth R44 rocker; the flat instead holds it upright and masks the imbalance. Another **55.74 g·mm** of correction is needed—moving 5 g approximately **11.15 mm right**. Required combined ballast centroid with all six segments is **x = +1.703 mm**, versus the reported +1.69.  
   **Fix:** model a continuous contact surface through the pole; trim after finishing that surface. Correct the ballast-centroid formula, which includes the existing cast moment in its “non-ballast” numerator. Evidence: [pole truncation](cad/desk/rolypoly.py:263), [trim formula](cad/desk/rolypoly.py:1543), [bottom measurements](/tmp/roly-review/extras.txt).

3. **Should fix — the assembly instructions do not establish a workable breakout/wiring installation.** Straight upward insertion of the breakout intersects the cradle; both mesh clipping and STEP intersection confirm it. The assertions check only its seated position. A simple horizontal insertion above the bulkhead also collides at the back. This does **not** prove every tilted path impossible, but the documented path is insufficient. LED installation, wire retention and door-opening service slack are absent.  
   **Fix:** demonstrate a swept insertion/removal path for the breakout **including socket and soldered wires**, or make the cradle/bulkhead removable. Add LED installation before closing access and reserve a service loop over the bulkhead. Evidence: [assembly instructions](cad/desk/out-rolypoly/build-sheet.txt:30), [seated-only check](cad/desk/rolypoly.py:1348), [independent intersections](/tmp/roly-review/fits.txt:17).

4. **Should fix — hardware clearance is overstated.** The imported board stack is **9.0 mm**, not the requested **9.3 mm**. With the specified board, battery clearance is **0.70 mm**, not 1.00, before insulation and tolerances. Otherwise, the exported envelopes pass: PCB **0.500 mm**, glass **1.575 mm**, J5/I2C **0.825 mm**, battery **0.378 mm** minimum STEP clearance. The plugs still use an unverified **4 mm** protrusion including the wire bend.  
   **Fix:** use the specified stack and measured plugged connector envelopes; include tape, leads and manufacturing clearance in the sweeps. Evidence: [hardware constant](cad/desk/housing.py:55), [derived stack](cad/desk/rolypoly.py:520), [measurements](/tmp/roly-review/fits.txt:1).

5. **Should fix — slot length departs from the explicit contract.** Measured slots are **66.85 mm**, rods **66.65 mm**: 0.10 mm clearance at each end. The 3 mm E profile, 45° long-side bevels and straight ends reproduce correctly. Slots span z **33.90–100.75**; rods **34.00–100.65**. AA placement uses a 7.50 mm PCB-bottom offset, consistent with the supplied approximate measurements; the +1.90 mm AA shift relative to the PCB is preserved.  
   **Fix:** separate the visible 66.65 mm opening from any concealed fitting clearance, or explicitly revise the contract. Evidence: [length calculation](cad/desk/rolypoly.py:533), [contract](docs/desk-housing-handoff.md:59), [sections](/tmp/roly-review/geom.txt).

6. **Should fix — joint strength is a catalogue-force estimate, not a verified safety factor.** Hanging printed cup plus ballast is **158.55 g**, before attached hardware. STEP confirms six magnet pairs, two dowels and approximately **1 mm boss ligaments**. The 2.2 mm-deep pockets can leave each 2 mm magnet recessed by 0.2 mm if bottomed; the door pockets have the same issue. Sliding dowels locate the cup but do not retain it vertically. The vendor’s approximately 300 g figure supports the nominal arithmetic, not an assembled-joint factor of 11.4. [Vendor data](https://www.supermagnete.de/eng/data_sheet_S-03-02-N.pdf).  
   **Fix:** specify flush-setting shims/jigs, magnet grade and adhesive; proof-test the printed joint in axial pull and peel. Keep cup removal available for door servicing. Evidence: [hole depths](cad/desk/rolypoly.py:755), [cup holes](cad/desk/rolypoly.py:829).

7. **Should fix — inverted-cup supports and casting instructions are incomplete.** Excluding the terrace, approximately **2,080 mm²** of the inverted cup’s internal surface exceeds a 45° unsupported overhang. Supporting only “under the trim terrace” misses the bowl ceiling. The body’s crown and approximately 29 mm opening bridge also require the stated support strategy to be checked in a slicer. The 0.8 mm logo skin needs an actual toolpath inspection; “two perimeters” is not verification.  
   Casting reaches **15.45 mm** maximum depth. “Two pours if the epoxy warms up” reacts after the process has started; cure heat depends on the selected resin and pour geometry. [Manufacturer guidance](https://www.westsystem.com/SAFETY/UNCONTROLLED-CURE/).  
   **Fix:** inspect supports beneath the whole internal bowl, verify removal access and logo extrusion paths, and specify a qualified resin/pour schedule before filling the finished rocker. Evidence: [print instructions](cad/desk/out-rolypoly/build-sheet.txt:4), [casting instructions](cad/desk/out-rolypoly/build-sheet.txt:38).

8. **Note — the architectural departures have mechanical justification, but change the agreed assembly.** Moving the battery upright onto the door raises the calculated CG enough to leave only **5.02 mm** rocking margin. The 19-segment-only cup gives **5.49 mm**. Thus the belly battery and cast ballast address real deficiencies. The wider inner flare is also defensible; PCB-centred door placement does not misalign the AA.  
   **Fix:** record the revised battery mounting, casting process and service arrangement explicitly against [decision 6](docs/desk-housing-rolypoly-handoff.md:131). RST/BOOT behind a removable service door are acceptable for a prototype; an inaccessible everyday power switch is a usability defect unless intentionally accepted. Validate a tool-operated door-release path after wiring.

9. **Note — the checks are weaker than their labels, but STEP volume tolerance is not the main fault.** The “every sideways tilt” assertion requires only **90°**, and its search stops at 120°. My full-revolution nominal check finds one stable rest and one unstable crest, so no additional sideways resting trap was found. Fresh absolute-tolerance STEP remeshing agrees with supplied STL volumes within **0.07%**; I also reproduced unreliable OCC integrated volumes. The 1e−3 volume tolerance alone is therefore not evidence of bad solids.  
   However, `dummy-cast.stl` contains **two disconnected pockets in dowel holes**, accepted by the 2% fragment allowance: **13.81 mm³ / 0.070 g** of fictitious ballast.  
   **Fix:** test the full angular range and uncertainty bounds, label stability results as calculated, retain fresh-remesh convergence checks, and count only the connected pourable cavity. Evidence: [righting assertion](cad/desk/rolypoly.py:1418), [cast-fragment allowance](cad/desk/rolypoly.py:1311).

The table uses the author’s nominal masses and solid PLA density for direct comparison. Fine angular extrema include small STL-facet irregularities.

| Key quantity | Reported | Independently reproduced |
|---|---:|---:|
| Body volume / mass | 46.3 cm³ / 57.5 g | 46.346 / 57.469 |
| Rock cup volume / mass | 12.8 / 15.9 | 12.839 / 15.920 |
| Stepped cup volume / mass | 18.2 / 22.6 | 18.204 / 22.572 |
| Flat cup volume / mass | 10.0 / 12.4 | 10.033 / 12.440 |
| Door volume / mass | 5.8 / 7.1 | 5.764 / 7.148 |
| Cast volume / mass | 24.0 cm³ / 123 g | 24.044 / 122.626; pourable component 24.030 / 122.555 |
| Cast centroid | z 12.0 | **(0.0218, 1.7549, 11.9922) mm** |
| Rocking total / CG | 322 g; z 34.73, y 1.51 | **322.149 g; (−0.1730, 1.5096, 34.7256) mm** |
| Rocking margin / ideal period | 9.27 mm / 1.00 s | 9.274 / 1.004 |
| Ideal restoring stiffness | 0.51 mN·m/° | 0.512 |
| Forward / backward limit | 25.0° / 26.5° | ≈25.03° / first crest 26.44°, another at 26.99° |
| R44 error / radial asymmetry | 0.005 / 0.004 mm | 0.00499 / 0.00487 mm |
| Outer seam step | Zero by construction | ≤0.00183 mm in sampled STL sections |
| Seam contact angle | — | ≈60° sideways; outside normal ±15° rocking |
| Flat total / CG above desk | 236 g / 32.0 mm | 236.044 / 31.956 |
| Flat tipping R / L / F / B | 64° / 44° / 36° / 36° | ≈63.4–64.4° / 44.03° / 36.03° / 36.50° |

**Could not verify:** actual component masses/centroids, connector and cable bends, a complete breakout insertion/removal path, wired door removal, magnet/adhesive strength, sliced extrusion/support paths, print tolerances, friction/damping, cable-induced lean, epoxy density/exotherm, or logo illumination. The 8.8 cm³ “shot in stepped-cup gaps” accessibility estimate was not independently reproduced.
---

## Pass 2 on round 2 (2026-11-15)

Run in two parts: the first stopped before its report (the Codex workspace ran out of credits) and was resumed in
the same session. Astra's report follows (paths made repo-relative); its scratch files were in `/tmp/roly-review2/`. "The partial
summary" in it is an interim summary the parent chat wrote from those files; this report replaces it.

**No remaining CAD blocker demonstrated.** Findings below retain the original review numbers, ordered by current severity. Repository unchanged; measurements are in [/tmp/roly-review2](/tmp/roly-review2).

1. **Should fix — #3 assembly/wiring: partly resolved.** The revised breakout path works for the exported envelopes: upward clearances **0.400 mm PCB, 0.354 mm socket, 2.000 mm wire stub**; no swept intersections. Battery clearance is **0.429 mm**. The door tool also passes: **0.901 mm** to the body, **0.500 mm** to the PCB; a short outward push remains clear.

   However, `dummy-wires.stl` represents only a **9 × 2 × 6 mm stub**. The **40 mm service travel is assigned, not checked**, and the 55/65 mm routes omit bundle thickness, bends, solder and retention. LED instructions specify **3–5 mm behind the logo**, while the tested volume is **4.5–8.5 mm behind and shifted 2 mm right**, with **0.483 mm** body clearance.

   **Fix:** use the tested LED location; dry-fit the actual harness and demonstrate closing plus 40 mm door withdrawal before gluing. Keep loops clear of the release tool and trim weights. Sources: [wire/service calculation](cad/desk/rolypoly.py:1728), [LED envelope](cad/desk/rolypoly.py:1458), [assembly instructions](cad/desk/out-rolypoly/build-sheet.txt:39), [independent fits](/tmp/roly-review2/fits.txt).

2. **Should fix — #7 printing/casting: partly resolved.** On-back printing is plausible, but the cup cannot rely on its own bed footprint. At **0.12 mm above the tangent bed plane**, its section spans only **13.64 × 5.82 mm**; **25.25 × 10.67 mm occurs at 0.60 mm**, correcting the partial summary. These are section envelopes, not contact areas. Its projected centre of mass lies outside the first-layer patch. I reproduce **1,613 mm²** of overhang exceeding 45°, with none in the designated rolling band.

   **Fix:** use a broad, anchored support cradle under the back and bowl, with support brim; inspect its first layers and support removal access. This orientation preserves the sideways profile better than rim-down, but “needs no sanding” remains a print-dependent claim. Brims improve adhesion for small footprints. [Prusa guidance](https://help.prusa3d.com/article/skirt-and-brim_133969).

   The horizontal **Ø3.1 magnet / Ø3.2 dowel holes** have short unsupported crowns: usable after checking and cleanup, not guaranteed round as printed. Exclude supports inside them; gauge/ream with a depth stop before installing hardware.

   **The gauge instructions need correction.** Its concavity is R44, but it checks the central profile, not zero clearance across the cup’s doubly curved surface. Sandpaper thickness \(t\) reduces its effective radius to **44−t**. Use it unlined for inspection; a sanding tool needs **R44+t** and a calibrated surface. Sources: [print/finish instructions](cad/desk/out-rolypoly/build-sheet.txt:9), [gauge construction](cad/desk/rolypoly.py:1450), [orientation measurements](/tmp/roly-review2/pole.txt).

   Casting instructions now specify two pours and a depth-rated slow resin. Heat compatibility with the selected resin and PLA remains untested.

3. **Should fix — #4 hardware clearance: partly resolved.** The accepted **9.0 mm measured stack** closes the drawing discrepancy. Exported insertion clearances reproduce: PCB **0.500**, glass **1.575**, plugs **0.825**, battery **0.381 mm**. The plugs still assume **4 mm protrusion**, without a realistic flexible lead bend.

   **Fix:** measure the plugged hardware and include insulation, adhesive and wire bends in the physical fit check. No demonstrated hard-part collision requires changing the opening. Source: [connector envelopes](cad/desk/rolypoly.py:1049), [independent fits](/tmp/roly-review2/fits.txt).

4. **Should fix — #9 assertions/reporting: partly resolved.** Full-revolution checking, bad-case stability and exclusion of inaccessible cast fragments address the original faults. Remaining blind spots:

   - The pole test accepts an **empty selection** as zero width: a missing/truncated bottom could pass. Require a nonempty selection and section-based continuity checks. [Line 1690](cad/desk/rolypoly.py:1690).
   - Logo minimum distance and mean material volume do not bound maximum skin thickness or prove every letter opens inward. Add distributed normal-thickness and cavity-access checks. [Line 1600](cad/desk/rolypoly.py:1600).
   - LED-to-hardware and tool-to-hardware distances are recorded without acceptance assertions; final shifted trim positions are not checked by the earlier segment-intersection loop. Assert these final configurations. [Line 1577](cad/desk/rolypoly.py:1577), [line 1650](cad/desk/rolypoly.py:1650).
   - Zero-clearance checks with `touch_ok=True` cannot reject insufficient clearance, although their overlap checks remain meaningful. [Line 1572](cad/desk/rolypoly.py:1572).

   Fresh STEP remeshing agrees with exported volumes within **0.067%**. The **1e−3 volume tolerance is not evidence of defective solids**. [Remesh results](/tmp/roly-review2/remesh.txt).

5. **Note — #1 mass/stability: resolved for the stipulated cases.** Independent nominal/bad-case margins are **10.090 / 8.366 mm**, and forward limits measured from rest are **31.032 / 29.011°**. The bad case has **0.366 mm reserve above the 8 mm criterion**; actual masses still matter.

   Squaring the keel produces a real gain: using the **same CG**, the study keel’s forward crest is **26.7–27.1°**, versus approximately **31.1°** for the square comparison mesh. The assembled revised housing gives **31.007° from upright**.

   **Fix:** retain the bounded mass checks and weigh the assembled hardware and cured cast. State the angle reference consistently: the report explicitly uses **upright**, not rest. Source: [stability acceptance](cad/desk/rolypoly.py:1679), [independent mass/stability results](/tmp/roly-review2/mass.txt).

6. **Note — #2 pole/plumb: resolved for prototype scale, with qualifications.** STL and freshly tessellated STEP show **no bottom flat**. The closure is not an exact cone or perfect R44: it contains a tiny cusp and shallow reversal around **z≈0.002 mm**. No feature comparable to a **0.12 mm layer** was found. Fine analysis finds rests at **−0.248/+0.252°** and microscopic bad-case facet minima around 95–98°; these do not establish perceptible printed resting traps.

   R44 radial error is **0.0050 mm**, asymmetry **0.0048 mm**. Current body/cup seam mismatch is **≤0.00141 mm**; seam contact starts around **60° sideways**, outside normal rocking. Squaring changes fore-aft depth at the seam, but current body and both cups match each other.

   The trim arithmetic works. With all six lower weights and no bulkhead weight, nominal **Gx=−0.763 mm**—a CG offset, not a 0.8 mm displacement of the housing. The prescribed **5 g at x=27.5**, omission and sliding bring Gx to zero. Its envelope clears the battery by **2.5 mm** and the cup seam by **5.5 mm**. The spare x=15 spot clears the breakout by **0.88 mm**. Nominal/bad plans consume **95%/94% of row travel**, leaving little adjustment reserve.

   **Fix:** trim the fully wired assembly before sticking weights down; preserve the spare spot and wire clearance. Sources: [trim calculation](cad/desk/rolypoly.py:1665), [geometry](/tmp/roly-review2/geom.txt), [alternatives](/tmp/roly-review2/alternatives.txt).

   Checked alternatives, retaining six lower weights: nominal cast-only balance requires **Cx=+2.001 mm**. A cavity-conforming PLA displacement rib occupying **x≤−17.45 mm**, volume **3.016 cm³**, loses **11.64 g** and leaves **9.641 mm margin**. A separately tuned bad-case rib needs **4.259 cm³** and leaves **7.845 mm**, failing 8 mm. A tilted pour capped at **z=17.9** needs **5.19° nominal / 7.42° bad**, leaving **8.407 / 5.955 mm margin**; it also needs a level support for the trim layer. These constrained alternatives offer no demonstrated advantage over the bulkhead weight.

7. **Note — #5 slots: resolved by the accepted decision.** Measured slots remain **66.85 mm**, rods **66.65 mm**; long-side slopes are 45°, ends straight, front thickness 3 mm. Rod centres **x=−15.23/+5.23**, z span **34.00–100.65**, preserve the AA placement and its **+1.90 mm** offset relative to PCB centre. **Action:** retain this geometry and update the contract when documenting round 2. Sources: [slot construction](cad/desk/rolypoly.py:566), [sections](/tmp/roly-review2/geom.txt).

8. **Note — #6 joint: resolved as an assembly/test specification.** Flush-setting instructions and the **0.34 kg proof load** replace the unsupported catalogue safety-factor claim. Nominal cup, cast and five lower segments weigh **172.27 g**, before attached joint hardware. Approximately **1 mm outer ligaments** remain; dowels locate rather than retain the hanging cup.

   **Action:** perform the specified pull/peel test after bore cleanup and adhesive cure; include door magnets in flush-setting inspection. Actual holding strength remains unverified. Source: [joint assembly/proof test](cad/desk/out-rolypoly/build-sheet.txt:32).

9. **Note — #8 architectural departures: resolved by the accepted decisions.** Belly battery, cast ballast, inner flare and PCB-centred door remain mechanically defensible. The switch decision is closed; RST/BOOT require door removal. **Action:** document the final assembly and verify the wired release path. Source: [service sequence](cad/desk/out-rolypoly/build-sheet.txt:46).

**Additional round-2 result — logo thickness resolved.** Dense interior sampling gives **0.788–0.810 mm** normal skin; the completed STEP-floor check gives **0.789–0.807 mm across 275 samples on both letter floors**. Both letters have inward access at sampled locations; no sealed letter was found. The partial summary’s second slab is along the **nominal logo projection direction**, not world y, and does not demonstrate thick skin. It can still shadow one end. **Action:** assess illumination using the tested LED position; no logo relocation is justified by these thickness results. [Construction](cad/desk/rolypoly.py:820), [completed floor check](/tmp/roly-review2/floor_finish.txt).

Values below use the specified densities and hardware masses. “N/B” means nominal/bad case.

| Quantity | Reported | Independent |
|---|---:|---:|
| Printed mass: body / rock / flat / door, g | 55.5 / 16.5 / 12.5 / 7.1 | **55.513 / 16.455 / 12.453 / 7.149** |
| Pourable cast volume, cm³ | 25.65 | **25.65062** |
| Cast mass N/B, g | 131 / 123 | **130.818 / 123.123** |
| Cast centroid xyz, mm | .02 / 1.85 / 11.78 | **.02365 / 1.84927 / 11.77886** |
| Rocking total N/B, g | 339 / 341 | **338.923 / 341.227** |
| Rocking CG xyz, nominal, mm | ≈0 / 1.84 / 33.91 | **≈0 / 1.84326 / 33.90997** |
| Rocking CG xyz, bad, mm | ≈0 / 1.62 / 35.63 | **≈0 / 1.61933 / 35.63449** |
| Under rocking centre N/B, mm | 10.09 / 8.37 | **10.09003 / 8.36551** |
| Ideal period N/B, s | .95 / 1.07 | **.947 / ≈1.073** |
| Righting stiffness N/B, mN·m/° | .59 / .49 | **.58552 / .48875** |
| Nominal forward/back, from upright | 31.00 / 31.54° | **31.007 / 31.537°** |
| Bad forward/back, from upright | 28.98 / 30.02° | **28.986 / 30.028°** |
| Forward/back **from rest**, N; B | — | **31.032/31.512°; 29.011/30.003°** |
| Flat total N/B, g | 234 / 249 | **234.103 / 249.103** |
| Flat CG above desk N/B, mm | 32.1 / 32.9 | **32.108 / 32.891** |
| Flat tips R/L/F/B, nominal | 64/44/36/37° | **≈63–64/43.87/36.49/37.25°** |
| Flat tips R/L/F/B, bad | 53/43/36/37° | **≈53–54/42.85/35.36/36.89°** |

The flat rightward crest is broad and faceted; a single precise angle overstates certainty. Bad-case inertia used a reconstructed, balanced lower-weight layout, so its period is approximate.

**Could not check:** actual component masses/centroids, connector bends and complete service-loop motion, sliced supports and logo extrusion paths, printed bore accuracy, joint strength, epoxy temperature/packing uniformity, cable-induced lean, damping or illumination. Logo checks densely sample both floors but do not mathematically certify every boundary point. No rebuild or physical print was performed.

**Ready to print the prototype: yes—with an anchored back-support cradle, bore cleanup, and the R44 gauge kept unlined for inspection.**
