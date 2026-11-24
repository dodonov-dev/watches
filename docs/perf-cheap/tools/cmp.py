# cmp.py OLD NEW ROWS0 ROWS1: frames of two runs on one input (noise.cpp FRAMES_OUT: the shown rows, the push-lens map
# applied, native little-endian RGB565): per frame new vs old (same instant), and new against the old frames of the last
# 50 steps (1 s) per pixel and channel (the envelope)
import sys, numpy as np
r0, r1 = int(sys.argv[3]), int(sys.argv[4]); W = 820; n = (r0 + r1) * W
def load(f):
    a = np.fromfile(f, dtype='<u2'); return a.reshape(-1, n)
def ex(a):
    a = a.astype(np.int32)
    r = (a >> 11 & 31); g = (a >> 5 & 63); b = a & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1)
O, N = load(sys.argv[1]), load(sys.argv[2]); F = len(O)
d = np.abs(ex(O) - ex(N)).max(-1)
print('frames %d: new vs old same instant: px differ %.1f/frame, max %d/255, >12/255 %d px total' % (F, (d > 0).sum() / F, d.max(), (d > 12).sum()))
out = []; mx = 0
EO, EN = ex(O), ex(N)
for k in range(50, F):
    lo = EO[k - 49:k + 1].min(0); hi = EO[k - 49:k + 1].max(0); v = EN[k]
    e = np.maximum(lo - v, v - hi).clip(0).max(-1); out.append((e > 0).sum()); mx = max(mx, e.max())
print('new outside the old 1-s envelope: %.2f px/frame, max %d/255 past it (frames %d)' % (np.mean(out), mx, len(out)))
