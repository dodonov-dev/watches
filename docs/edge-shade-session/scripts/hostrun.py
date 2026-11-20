# hostrun.py <render.cpp> <look.json> [extra -D...]: build check_board_render's harness with that render.cpp (lcd316 320w8-8), render the look once
import sys, json, subprocess, os
W='/home/andrey/_PROJECTS/watches-edge-shade'
sys.path.insert(0, W+'/firmware/tools')
import check_board_render as cbr, boardtag
tmp=os.path.dirname(os.path.abspath(__file__))
open(tmp+'/esp_heap_caps.h','w').write('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\ninline void *heap_caps_malloc(size_t n, int) { return std::calloc(n, 1); }\n')
open(tmp+'/esp_random.h','w').write('#pragma once\n#include <cstdint>\ninline uint32_t esp_random() { return 0xabcdef01; }\n')
open(tmp+'/h.cpp','w').write(cbr.HARNESS)
extra=sys.argv[3:]
subprocess.run(['c++','-std=c++17','-O2','-ffp-contract=off','-DPUSH_LENS=1',*boardtag.tubes_flags(2),'-DBOARD_LCD316',*boardtag.res_flags('320w8-8',2),*extra,'-I',tmp,'-I',W+'/firmware/src','-I',W+'/spec',tmp+'/h.cpp',sys.argv[1],W+'/firmware/src/physics.cpp','-o',tmp+'/h'],check=True)
p=json.load(open(sys.argv[2])); p['fizz']=False
script=[f'P {k}={cbr.fmt(v)}' for k,v in p.items() if k!='v']+['S 0 0.42 20','S 1 0.71 20','R']
subprocess.run([tmp+'/h'],input=('\n'.join(script)+'\n').encode(),stdout=subprocess.DEVNULL)
