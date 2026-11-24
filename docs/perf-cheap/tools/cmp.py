# cmp.py OLD NEW ROWS: frames of two runs on one input (noise.cpp FRAMES_OUT: the shown rows of both tubes, ROWS in all,
# the push-lens map applied, native little-endian RGB565): per frame new vs old (same instant), and new against the old
# frames of the last 50 steps (1 s) per pixel and channel (the envelope). Streams the files (a 50-frame ring in memory).
# --json: one line of the numbers.
import sys, json, numpy as np
old, new, rows = sys.argv[1], sys.argv[2], int(sys.argv[3]); n = rows * 820
def ex(a):
    a = a.astype(np.int16)
    r = a >> 11 & 31; g = a >> 5 & 63; b = a & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.int16)
fo, fn = open(old, 'rb'), open(new, 'rb')
ring = []; F = 0; diffPx = 0; mx = 0; big = 0; outs = []; omx = 0
while True:
    bo, bn = fo.read(n * 2), fn.read(n * 2)
    if len(bo) < n * 2 or len(bn) < n * 2:
        assert len(bo) == 0 and len(bn) == 0, 'cmp.py: the two runs differ in length (or end in a partial frame)'
        break
    EO, EN = ex(np.frombuffer(bo, '<u2')), ex(np.frombuffer(bn, '<u2'))
    d = np.abs(EO - EN).max(-1); diffPx += int((d > 0).sum()); mx = max(mx, int(d.max())); big += int((d > 12).sum())
    ring.append(EO); ring = ring[-50:]
    if F >= 49:
        st = np.stack(ring); lo, hi = st.min(0), st.max(0)
        e = np.maximum(lo - EN, EN - hi).clip(0).max(-1); outs.append(int((e > 0).sum())); omx = max(omx, int(e.max()))
    F += 1
assert F > 0, 'cmp.py: no frames'
res = {'frames': F, 'diffPerFrame': diffPx / max(1, F), 'max': mx, 'over12': big, 'outPerFrame': float(np.mean(outs)) if outs else 0, 'outMax': omx}
if '--json' in sys.argv: print(json.dumps(res))
else:
    print('frames %d: new vs old same instant: px differ %.1f/frame, max %d/255, >12/255 %d px total' % (F, res['diffPerFrame'], mx, big))
    print('new outside the old 1-s envelope: %.2f px/frame, max %d/255 past it (frames %d)' % (res['outPerFrame'], omx, len(outs)))
