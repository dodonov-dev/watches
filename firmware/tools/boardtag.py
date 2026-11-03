#!/usr/bin/env python3
"""LCD res tags (rows + tube widths) for the build scripts and host checks; mirrors spec/layout.ts resTag / parseRes and
firmware board.h BOARD_TAG.

  320    both tubes narrow   -DRENDER_H=320
  320f   both wide           -DRENDER_H=320 -DLCD_FILL=1
  320fh  hours wide          -DRENDER_H=320 -DLCD_FILL_H=1
  320fm  minutes wide        -DRENDER_H=320 -DLCD_FILL_M=1

CLI (exit 2 on a bad tag):
  boardtag.py flags RES             the -D flags of an lcd316 res tag ('' = none: layout.h defaults, 320 narrow)
  boardtag.py tag ENV [FLAG ...]    the board tag (`v`) a build of env ENV with these -D flags reports
"""
import re, sys

LCD_RES = (240, 256, 288, 320)
SUFFIX = {'': (False, False), 'f': (True, True), 'fh': (True, False), 'fm': (False, True)}

def parse_res(tag):
    """(rows, hours wide, minutes wide) of an LCD res tag; ValueError if it is not one."""
    m = re.fullmatch(r'(\d+)(f|fh|fm)?', tag or '320')
    if not m or int(m[1]) not in LCD_RES:
        raise ValueError(f'res {tag!r}: rows {" / ".join(map(str, LCD_RES))}, then nothing (narrow) / f (wide) / fh / fm (hours / minutes wide)')
    return (int(m[1]), *SUFFIX[m[2] or ''])

def res_tag(rows, wide_h, wide_m):
    return f'{rows}{"f" if wide_h and wide_m else "fh" if wide_h else "fm" if wide_m else ""}'

def res_flags(tag):
    """The -D flags an lcd316 build of this res tag takes (LCD_FILL=1 for both wide: what builds before the per-tube
    widths read too). No tag: none (layout.h's defaults; an explicit -DRENDER_H / -DLCD_FILL elsewhere stays in force)."""
    if not tag: return []
    rows, h, m = parse_res(tag)
    return [f'-DRENDER_H={rows}'] + (['-DLCD_FILL=1'] if h and m else ['-DLCD_FILL_H=1'] if h else ['-DLCD_FILL_M=1'] if m else [])

def build_tag(env, flags):
    """The board tag a build reports (board.h BOARD_TAG): the -D flags' RENDER_H / LCD_FILL / LCD_FILL_H / LCD_FILL_M,
    later ones winning, defaulted as layout.h does."""
    if env != 'lcd316': return env
    d = {}
    for f in flags:
        m = re.fullmatch(r'-D(RENDER_H|LCD_FILL|LCD_FILL_H|LCD_FILL_M)(?:=(\S*))?', f)
        if m: d[m[1]] = m[2] if m[2] is not None else '1'
    fill = int(d.get('LCD_FILL', '0') or 0)
    h, m = int(d.get('LCD_FILL_H', fill) or 0), int(d.get('LCD_FILL_M', fill) or 0)
    return f'lcd316@{res_tag(int(d.get("RENDER_H", 320)), bool(h), bool(m))}'

if __name__ == '__main__':
    try:
        if len(sys.argv) == 3 and sys.argv[1] == 'flags': print(' '.join(res_flags(sys.argv[2])))
        elif len(sys.argv) >= 3 and sys.argv[1] == 'tag': print(build_tag(sys.argv[2], ' '.join(sys.argv[3:]).split()))
        else: sys.exit(__doc__)
    except ValueError as e:
        print(f'boardtag: {e}', file=sys.stderr); sys.exit(2)
