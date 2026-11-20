import sys, time
sys.path.insert(0, 'tools')
import device
with device.Device(None) as d:
    for c in ['g -0.5 0']: d.talk(c)
    time.sleep(4); d.talk('g 0 0'); time.sleep(4)
    d.talk('t 10:09:30'); d.talk('d0'); d.set('inputGain', 0)
    for v in ["0", "0"]:
        d.set('edgeShade', v); time.sleep(3); d.talk('f'); time.sleep(2.2)
        r = d.talk('f', end='tile-prof m')
        print('== edgeShade', v); print('\n'.join(l for l in r.split('\n') if l.startswith(('fps', 'tube-prof', 'tile-prof')) or 'push-verify' in l))
    d.talk('g'); d.talk('d1')
