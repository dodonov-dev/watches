import json, sys, time
sys.path.insert(0, 'tools')
import device
from bench import fmt
look = json.load(open(sys.argv[1]))
with device.Device(sys.argv[2]) as d:
    bad = []
    for k, v in look.items():
        if k == 'v': continue
        r = d.talk(f'p{k}={fmt(v)}')
        if not r.startswith('ok'): bad.append((k, r))
    print('writes', len(look) - 1, 'not ok', bad)
    time.sleep(3)
    cur = json.loads([l for l in d.talk('p?', end='}').split('\n') if l.startswith('{')][0])
    diff = {k: (look[k], cur.get(k)) for k in look if cur.get(k) != look[k]}
    print('p? keys', len(cur), 'diff vs look', diff)
