from concepts import *
from draw import *
import subprocess, os
OUT = "fable-svg"; os.makedirs(OUT, exist_ok=True)
def tip(r): return f"tips at ~{r['back']:.0f}° back / {r['fwd']:.0f}° forward (worst direction {r['worst'][0]:.0f}°)"
def size(r): return f"{r['W']:.0f} W x {r['D']:.0f} D x {r['H']:.0f} H"
R = {}
def make(key, fn, title, notes, contours, **kw):
    bodies, yt, akw = fn(); r = analyse(key, bodies, yt, **akw); R[key] = r
    F = r["F"]
    sub = [f"{size(r)} mm (lid included);  flat foot {F[:,0].max()-F[:,0].min():.0f} x {F[:,1].max()-F[:,1].min():.0f};  shell ~{r['shell_cm3']:.0f} cm3, ~{r['mass']:.0f} g with board 30 g + battery 55 g (assumed)",
           f"centre of mass {r['com'][1]-F[:,1].min():.0f} behind the foot's front edge, {r['com'][2]:.0f} up;  {tip(r)};  tilt15: 22 / 29, oval: 18 / 17"]
    es = kw.pop("section", None); usb = kw.pop("usb", "auto")
    if usb == "auto": usb = float(max(b_.yb(LID + 2) for b_ in bodies if b_.has(LID + 2)))
    sheet(key, title, sub, notes, bodies, yt, r, contours, path=f"{OUT}/{key}.svg", usb=usb, extra_section=(pebble_section(bodies[0], yt) if es else None), **kw)
    return r

make("pebble-true", pebble, "Leaning pebble, true size (refined d)",
     ["One soft stone: egg outline in front, long convex back, the underside rounds in to a small flat foot.",
      "Front: straight along the 15° lean over the slots, bowed across the width like the oval's (4.55 on the centre line, 3.0 at the glass edge); inner face flat.",
      "Underside R7.5: its first 45° are the lid's edge (the lid prints flat), the shell starts at the rim at 45°, so it prints standing on the rim without supports.",
      "Dome: outside free; inside a 45° tent and a small flat bridge, so the top wall grows from 3 to about 7 without a step."],
     [3, 30, 60, 85, 100], logo_xy=(0, 11.6, 12), section=True, top_note="front edges of the contours show the bow (1.55 at x 15.9)")
make("found-stone", found, "Found stone (asymmetric pebble)",
     ["The pebble made a real stone: apex 3 left of the tubes, a fuller, lower hip on the right (the board's plug side) that carries the logo, plan skewed to the right at the back.",
      "The front panel (|x| < 19) keeps the oval's symmetric bow, so both slots stay identical; the asymmetry lives outside it."],
     [3, 30, 60, 85, 100], logo_xy=(10.2, 11.6, 12))
make("soft-cairn", cairn, "Soft cairn (a pear: belly low, head leaning back)",
     ["#13 at true size. Belly 64 wide and 62 deep at z 18; above z 60 it slims to 52 x 30 and the back leans 6° the same way as the face, so the head nods back over the waist;",
      "soft top (R12). Front as the pebble: straight along the lean over the slots, bowed across the width. Same underside: first 45° of the round in the lid, the rest in the shell."],
     [3, 18, 50, 80, 100], logo_xy=(0, 11.6, 12))
make("leaning-stones", stones, "Leaning stones (oval slab propped by a small stone)",
     ["From the front and the seat: the pure oval, 56 x 33 in plan, leaning 15° with parallel front and back. Behind its heel a small round stone props it:",
      "that is the foot, the cable garage (USB notch at its back) and room for ballast. Prop 46 wide, 36 deep, 29 high.",
      "One shell and one lid: the slab's back wall starts on the prop's roof (45° inside); the slab's back does not exist inside the prop."],
     [3, 11, 60, 95], logo_xy=(0, 6.6, 14))
make("menhir", menhir, "Menhir (the oval with a bowed back)",
     ["The calm one: every section the oval's superellipse, 56 wide; front 15°; the back is one slow concave bow, vertical at the desk, 6° back at the top, so the top",
      "overhangs the foot by 5 and the body reads as leaning, not as a wedge. Flat top 42 x 12, R7. 3 less base depth than the wedge (a), ~3° less tipping margin."],
     [3, 60, 100], logo_xy=(0, 6.6, 14))
