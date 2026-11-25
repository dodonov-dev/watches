# Desk Clock Shell Concepts (Neon)

## 1. Oblique (`neon-1-oblique`)
- **Idea:** Pure canted oval monolith — takes the exact bar-of-soap oval column and leans the whole body back 15°, keeping slender calm proportions with zero wedge bulk and a softly glowing `EH` centered below the rods.
- **Side profile & 15° mechanism:** Parallel front and back walls leaning back 15° together between a flat horizontal base and softly rounded flat top; tilting the entire oval extrusion gives the 15° face while keeping a uniform ~38 mm perpendicular depth for the 26 mm electronics stack.
- **Risks:** Center of gravity shifts slightly rearward (needs the battery mounted low/forward or a weighted bottom lid to resist rear tip-over), and the 15° slanted walls can show subtle FDM stair-stepping if printed upright.

## 2. Pebble (`neon-2-pebble`)
- **Idea:** Faceted river stone — replaces `tilt15`'s boxy doorstop with a full, plump ovoid pebble sliced cleanly on the front, with a softly glowing `EH` tucked into the curved lower-left flank.
- **Side profile & 15° mechanism:** Straight 15°-leaning flat oval front backed by a continuous convex pillowed arc tapering to a soft rounded crown; the bulbous back naturally clears the 26 mm perpendicular board/battery depth behind the entire 36 × 75 mm face while giving the widest, steadiest base.
- **Risks:** Doubly-curved convex back will show FDM layer contour rings across the shallow upper crown (needs fine layers, fuzzy skin, or light sanding), and the ovoid interior requires custom internal ribs to index a rectangular PCB.

## 3. Cove (`neon-3-cove`)
- **Idea:** Upright oval with carved alcove — keeps the beloved vertical bar-of-soap silhouette completely intact outside while recessing the display into a softly filleted front niche whose upper brow acts as a glare hood, with glowing `EH` on the front chin.
- **Side profile & 15° mechanism:** Vertical rounded oval body (~58 mm deep) with a planar 15° diagonal step carved inward from the chin up beneath the rounded top brow (note: the single-pass render drew the recess nearly vertical; in CAD the alcove face tilts back 15°, leaving ~35 mm perpendicular depth behind the upper tubes while staying clear of a 30° downward sightline).
- **Risks:** The overhanging brow above the alcove needs a generous ≥45° internal/underside transition or supports on FDM to print cleanly, and the recessed cheeks push total depth close to the 60 mm ceiling while narrowing extreme side viewing angles.

---
*Image file note: Shell commands are disabled and the image generator saves directly into the artifact directory as `.jpg` (and text file tools cannot write binary image files), so the three single-pass renders are saved at:*
- `/home/andrey/.gemini/antigravity-cli/brain/e363e47d-6007-4a8b-8dca-a825dc3253da/neon_1_oblique_1795195822704.jpg` (intended: `desk-housing-v3/agy/neon-1-oblique.png`)
- `/home/andrey/.gemini/antigravity-cli/brain/e363e47d-6007-4a8b-8dca-a825dc3253da/neon_2_pebble_1795195832781.jpg` (intended: `desk-housing-v3/agy/neon-2-pebble.png`)
- `/home/andrey/.gemini/antigravity-cli/brain/e363e47d-6007-4a8b-8dca-a825dc3253da/neon_3_cove_1795195822595.jpg` (intended: `desk-housing-v3/agy/neon-3-cove.png`)
