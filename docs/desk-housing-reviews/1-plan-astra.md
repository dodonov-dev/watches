1. **[blocker] Insertion clearance is missing.** Pre-glued rods require a swept depth of **4.5 + 9.3 = 13.8 mm**; with the 10 mm battery attached, **23.8 mm** exceeds the **20.5 mm** cavity. Insert the display first, then battery; demonstrate the reverse removal path.

2. **[blocker] The seated depth budget is too tight.** Front + mounting tape + board + battery + back = **22.9–23.0 mm**, leaving only **1.0–1.1 mm** for insulation, padding, tolerances and cell expansion. Start with a **≤8 mm cell**, or increase depth and budget these explicitly.

3. **[blocker] “Then tape” is not an assembly procedure.** Pre-apply tape with release-liner tails accessible through the bottom; align, withdraw liners, then press before installing the battery. Provide accessible adhesive-release tabs or mechanical retention—ordinary thin tape does not guarantee removable glass.

4. **[blocker] USB hardware must precede the first shell print.** The **13 mm** bottom space must contain the seated male connector, stiffener and bend; the female’s internal body and screw ears also need clearance. Select the extension and model its complete installed envelope.

5. **[should] Specify a bend radius, not a “180° fold.”** Use the selected FPC’s minimum radius and keep bends outside stiffeners; reserve the resulting U-loop envelope. A sharp crease is specifically a damage risk. [Minco guidance](https://www.minco.com/resources/flex-circuit-faq/)

6. **[blocker] The wood shell lacks a credible machining route.** A roughly **93 mm-deep** bottom-access cavity with internal locating ribs is not a straightforward CNC pocket. Agree a glue-up or separately machined face/back with the machinist before treating the printed shell as transferable.

7. **[should] PCB clearance is marginal.** A 38 mm shell with 2 mm sides gives **34 mm internally: 0.325 mm per PCB side**, before manufacturing error or projecting controls. Start at **35 mm clear width**—39 mm printed / 41 mm wooden outside—and include plugged connectors in the envelope.

8. **[should] The glass frame locates loosely; it does not self-centre.** Its ±0.3 mm nominal positional freedom already equals the rod-to-slot side clearance. Use defined datum pads and an alignment jig; dimension slots from the AA, and verify rib height against the actual LCD/FPC edge.

9. **[should] Fix the vertical datum explicitly.** With the PCB bottom **13 mm** above the opening, its top is **91.85 mm**, leaving **1.15 mm** under a 2 mm roof. Slot centre is approximately **54.3 mm above the bottom**, not the housing centre.

10. **[should] Rod and slot tolerances need a combined budget.** The nominal allowances are only **0.3 mm/side and 0.4 mm/end**. Specify finished rod length **67.65 ±0.1 mm**, including polishing, and test both slots together at full length; a width-only coupon misses alignment and bow.

11. **[should] R0.5 does not transfer conveniently to wood.** It requires a **Ø1 mm cutter**. Agree a larger radius—e.g. **R1.5 with Ø3 mm tooling**—and relieve the rod end corners accordingly; verify the complete insertion envelope, not just slot width.

12. **[should] Qualify each manufacturing process separately.** A printed coupon cannot settle the CNC wood fit. Make coupons in the actual MJF finish, PETG orientation/settings, and finished wood; for FDM, specify orientation and removable support access before ordering.

13. **[should] Keep the 12 mm bridge, strengthen the wooden face.** Start around **3 mm front thickness**, with straight grain running along the slots and conditioned stock. Allow cross-grain movement without clamping the glass; re-budget depth and optics rather than merely widening the box.

14. **[nit] Protrusion omits the mounting tape.** Printed protrusion is **4 + 0.5 − 1.5 − 0.1…0.2 = 2.8–2.9 mm**; with a 3 mm wooden front it becomes **1.3–1.4 mm**. Parameterize both adhesive thicknesses.

15. **[should] Battery retention needs a protected envelope.** Include pouch seams, protection circuit and lead exit in “70 × 30 × 10”; provide a smooth insulating barrier against components/nuts and positive retention at the open bottom. Reserve the chosen cell’s expansion allowance without compressing it.

16. **[should] The proposed switch is a battery disconnect.** It prevents charging when open and leaves USB-powered operation available. Expose/actuate the board’s existing system switch if ordinary ON/OFF behavior is intended. [Waveshare controls](https://www.waveshare.com/wiki/ESP32-S3-LCD-3.16)

17. **[should] BOOT/RST access should survive a failed firmware flash.** Add approximately **Ø2–3 mm tool holes**, aligned to the side-actuated buttons **10.77 mm apart**, with unobstructed approach paths. Removing an adhesively mounted display is an unnecessarily destructive recovery procedure.

18. **[should] Validate the actual optical stack.** Magnification is unproven with the specified OCA; the cylinder also does not magnify along its length. Test the full-length rods at **0°, ±30° and ±45°**, including the thicker wooden face; relieve aperture edges where clipping occurs.

19. **[should] Stability is marginal before cable forces.** With a centred CG around **50 mm high**, a 24 mm base tips at approximately **13.5°**; bottom fillets and rearward mass reduce that. Preserve flat bearing surfaces and test a **30–32 mm depth** or demonstrate adequate stability with the actual mass layout.

20. **[should] Heat needs a defined acceptance test.** Test the assembled enclosure at maximum intended brightness, radio load and simultaneous charging until temperatures stabilize. Measure the cell and charger against their limits; reserve a low-to-high ventilation path if needed—the desk can obstruct the bottom opening.

21. **[should] Logo geometry and lighting are incomplete.** The side is **24 × 95 mm**, not 30 × 95; a 20 mm logo leaves little edge margin. Bond **opaque counter islands** to a diffuser, and test illumination through the actual veneer before committing to a fragile 0.6–1 mm wood skin.

22. **[should] “3–5 V LEDs” does not establish brightness at 3.3 V.** Select LEDs/resistors for **1–2 mA each at 3.3 V**, reserve their mixing space and wiring, and mask light leakage toward the LCD. Verify UART-TX availability and boot behavior before assigning PWM.

Keep the **20.46 mm centres, 11.86 mm bridge and 4.47 mm outer margins**; their arithmetic is correct.  
The approximately **+1.9 mm AA offset toward the far end** is consistent with the dimensions.  
Keep parameterized clearances, prototype coupons, and deferring the logo until the mechanical fit works.