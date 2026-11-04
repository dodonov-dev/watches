#!/usr/bin/env python3
"""LCD res tags (rows + tube widths) and tube counts for the build scripts and host checks; mirrors spec/layout.ts
resTag / parseRes / BOARD_TAG and firmware board.h BOARD_TAG.

  320    all tubes narrow     -DRENDER_H=320
  320f   all wide             -DRENDER_H=320 -DLCD_FILL=1
  320fh  hours wide           -DRENDER_H=320 -DLCD_FILL_H=1
  320fm  minutes wide         -DRENDER_H=320 -DLCD_FILL_M=1
  three tubes (-DTUBE_COUNT=3: hours / minutes / seconds, board tag + "+t3") also take the seconds letter, wide tubes in
  h / m / s order: 320fs, 320fhm, 320fhs, 320fms (-DLCD_FILL_S=1 ...); 320f / 320fh / 320fm mean the same there.

CLI (exit 2 on a bad tag):
  boardtag.py flags RES [TUBES]     the -D flags of an lcd316 res tag for a face of TUBES tubes (default 2; '' = none:
                                    layout.h defaults, 320 narrow); the tube count's own flag is tubes_flags
  boardtag.py tubes TUBES           the -D flag of a tube count ('' for 2)
  boardtag.py tag ENV [FLAG ...]    the board tag (`v`) a build of env ENV with these -D flags reports
"""
import re, sys

LCD_RES = (240, 256, 288, 320)
TUBE_COUNTS = (2, 3)
LETTERS = 'hms'   # tube letters in face order
FILL = ('LCD_FILL_H', 'LCD_FILL_M', 'LCD_FILL_S')

def res_tag(rows, *wide):
    """The res tag of rows and one width per tube (True = wide)."""
    n = sum(map(bool, wide))
    return f'{rows}{"" if n == 0 else "f" if n == len(wide) else "f" + "".join(c for c, w in zip(LETTERS, wide) if w)}'

def tube_count(tubes):
    t = int(tubes or 2)
    if t not in TUBE_COUNTS: raise ValueError(f'tubes {tubes!r}: {" / ".join(map(str, TUBE_COUNTS))}')
    return t

def parse_res(tag, tubes=2):
    """(rows, wide per tube ...) of an LCD res tag for a face of `tubes` tubes; ValueError if it is not one."""
    tubes = tube_count(tubes)
    m = re.fullmatch(r'(\d+)(f([hms]*))?', tag or '320')
    bad = ValueError(f'res {tag!r}: rows {" / ".join(map(str, LCD_RES))}, then nothing (narrow) / f (wide) / f + the wide '
                     f'tubes of {LETTERS[:tubes]} in that order (not all of them), for {tubes} tubes')
    if not m or int(m[1]) not in LCD_RES: raise bad
    rows = int(m[1])
    wide = (False,) * tubes if m[2] is None else (True,) * tubes if not m[3] else tuple(c in m[3] for c in LETTERS[:tubes])
    if res_tag(rows, *wide) != (tag or '320'): raise bad   # unknown, repeated, out-of-order or all letters
    return (rows, *wide)

def res_flags(tag, tubes=2):
    """The -D flags an lcd316 build of this res tag takes (LCD_FILL=1 for all wide: what builds before the per-tube
    widths read too). No tag: none (layout.h's defaults; an explicit -DRENDER_H / -DLCD_FILL elsewhere stays in force)."""
    if not tag: return []
    rows, *wide = parse_res(tag, tubes)
    if all(wide): return [f'-DRENDER_H={rows}', '-DLCD_FILL=1']
    return [f'-DRENDER_H={rows}'] + [f'-D{f}=1' for f, w in zip(FILL, wide) if w]

def tubes_flags(tubes):
    """The -D flag of a tube count: none for the default two."""
    return [] if tube_count(tubes) == 2 else [f'-DTUBE_COUNT={tube_count(tubes)}']

def build_tag(env, flags):
    """The board tag a build reports (board.h BOARD_TAG): the -D flags' TUBE_COUNT, RENDER_H, LCD_FILL, LCD_FILL_H /
    _M / _S, later ones winning, defaulted as layout.h does."""
    d = {}
    for f in flags:
        m = re.fullmatch(r'-D(TUBE_COUNT|RENDER_H|LCD_FILL|LCD_FILL_H|LCD_FILL_M|LCD_FILL_S)(?:=(\S*))?', f)
        if m: d[m[1]] = m[2] if m[2] is not None else '1'
    tubes = tube_count(d.get('TUBE_COUNT', '2'))
    suffix = '+t3' if tubes == 3 else ''
    if env != 'lcd316': return env + suffix
    fill = int(d.get('LCD_FILL', '0') or 0)
    wide = [bool(int(d.get(f, fill) or 0)) for f in FILL[:tubes]]
    return f'lcd316@{res_tag(int(d.get("RENDER_H", 320)), *wide)}{suffix}'

if __name__ == '__main__':
    try:
        if len(sys.argv) in (3, 4) and sys.argv[1] == 'flags': print(' '.join(res_flags(sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else 2)))
        elif len(sys.argv) == 3 and sys.argv[1] == 'tubes': print(' '.join(tubes_flags(sys.argv[2])))
        elif len(sys.argv) >= 3 and sys.argv[1] == 'tag': print(build_tag(sys.argv[2], ' '.join(sys.argv[3:]).split()))
        else: sys.exit(__doc__)
    except ValueError as e:
        print(f'boardtag: {e}', file=sys.stderr); sys.exit(2)
