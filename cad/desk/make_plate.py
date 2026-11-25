#!/usr/bin/env python3
"""Bambu Studio project (.3mf) from to-print STLs, print settings copied from a template plate (TPL).
Shells (enf=true) get a support-enforcer part over the pebble's two slot top end walls (the middle 6 mm of each); with
SUP: tree(manual) supports from the build plate only, branch angle 10 deg (the trees cannot escape out of the front
opening: the face leans 15 deg), 0.7 xy distance. Lids are flipped (inner face down).
    PLATE_OUT=_N_name.3mf PLATE_OBJECTS='[["name","file.stl",{per-object settings},x,y,enf], ...]' \\
        ~/.venvs/cad/bin/python cad/desk/make_plate.py
"""
import sys, uuid, zipfile, numpy as np, pyvista as pv
from xml.sax.saxutils import escape
TP = "/home/andrey/_PROJECTS/watches/cad/desk/to-print/"
TPL = "/home/andrey/_PROJECTS/watches-rolypoly/cad/desk/to-print/_7_plate_roly_poly_pebble.3mf"
SUP = {"enable_support": "1", "support_type": "tree(manual)", "support_on_build_plate_only": "1", "enable_overhang_speed": "0,0",
       "tree_support_branch_angle": "10", "support_object_xy_distance": "0.7"}   # 10 deg: trees cannot escape out of the front opening (face leans 15)
NOSUP = {"enable_overhang_speed": "0,0"}
import os; OUT = os.environ.get("PLATE_OUT", None)

def enforcer():
    """body frame box over the top end walls (plane s 91.55, |x| 2.27..14.98, t 0.01..3.39), kept 0.14 off the inner face"""
    bs = [pv.Box(bounds=(sx * 9.0 - 3.0, sx * 9.0 + 3.0, -0.8, 3.25, 90.9, 92.0), level=0).triangulate() for sx in (-1, 1)]
    return pv.merge(bs).rotate_x(-15, point=(0, 0, 0))   # the middle 6 of each 8.1 end wall; body -> world

def obj_xml(parts):
    body = []
    for pid, m, c in parts:
        p = m.points - c; f = m.faces.reshape(-1, 4)[:, 1:]
        v = "\n".join(f'     <vertex x="{a:.5f}" y="{b:.5f}" z="{z:.5f}"/>' for a, b, z in p)
        t = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{z}"/>' for a, b, z in f)
        body.append(f'  <object id="{pid}" p:UUID="{uuid.uuid4()}" type="model">\n   <mesh>\n    <vertices>\n{v}\n    </vertices>\n'
                    f'    <triangles>\n{t}\n    </triangles>\n   </mesh>\n  </object>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
            'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
            'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n'
            ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n' + "\n".join(body) + '\n </resources>\n <build/>\n</model>\n')

def main():
    global OBJECTS, OUT
    import json; OBJECTS = [tuple(o) for o in json.loads(os.environ["PLATE_OBJECTS"])]; OUT = TP + os.environ["PLATE_OUT"]
    zt = zipfile.ZipFile(TPL); res, build, settings, inst, rels, files = [], [], [], [], [], {}
    nid = 1
    for i, (name, stl, cfg, x, y, enf) in enumerate(OBJECTS):
        m = pv.read(TP + stl).triangulate().clean()
        if 'lid' in stl: m = m.rotate_x(180, point=(0, 0, 0))   # lids print flipped: inner face down (as the oval lid on plate 3)
        bd = m.bounds
        c = np.array([(bd[0] + bd[1]) / 2, (bd[2] + bd[3]) / 2, (bd[4] + bd[5]) / 2]); hz = (bd[5] - bd[4]) / 2
        parts = [(nid, m, c)]; nid += 1
        if enf:
            parts.append((nid, enforcer(), c)); nid += 1
        oid = nid; nid += 1; k = i + 1
        files[f"3D/Objects/object_{k}.model"] = obj_xml(parts)
        rels.append(f' <Relationship Target="/3D/Objects/object_{k}.model" Id="rel-{k}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
        comps = "\n".join(f'    <component p:path="/3D/Objects/object_{k}.model" objectid="{pid}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>' for pid, _, _ in parts)
        res.append(f'  <object id="{oid}" p:UUID="{uuid.uuid4()}" type="model">\n   <components>\n{comps}\n   </components>\n  </object>')
        build.append(f'  <item objectid="{oid}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 {x} {y} {hz:.5f}" printable="1"/>')
        md = "\n".join(f'    <metadata key="{kk}" value="{escape(vv)}"/>' for kk, vv in cfg.items())
        ps = []
        for j, (pid, pm, _) in enumerate(parts):
            sub, pn = ("normal_part", name) if j == 0 else ("support_enforcer", "support enforcer: slot top end walls")
            ps.append(f'    <part id="{pid}" subtype="{sub}">\n      <metadata key="name" value="{escape(pn)}"/>\n'
                      '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                      f'      <metadata key="source_file" value="{stl}"/>\n      <metadata key="source_object_id" value="0"/>\n'
                      f'      <metadata key="source_volume_id" value="{j}"/>\n    </part>')
        settings.append(f'  <object id="{oid}">\n    <metadata key="name" value="{escape(name)}"/>\n' + (md + "\n" if md else "") +
                        f'    <metadata key="extruder" value="1"/>\n    <metadata face_count="{sum(pm.n_cells for _, pm, _ in parts)}"/>\n' + "\n".join(ps) + '\n  </object>')
        inst.append(f'    <model_instance>\n      <metadata key="object_id" value="{oid}"/>\n      <metadata key="instance_id" value="0"/>\n'
                    f'      <metadata key="identify_id" value="{100 + i}"/>\n    </model_instance>')
        print(name, "parts", len(parts), "height", round(2 * hz, 2))
    head = zt.read("3D/3dmodel.model").decode().split("<resources>")[0]
    files["3D/3dmodel.model"] = (head + "<resources>\n" + "\n".join(res) + "\n </resources>\n" f' <build p:UUID="{uuid.uuid4()}">\n' + "\n".join(build) + "\n </build>\n</model>\n")
    files["3D/_rels/3dmodel.model.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n' + "\n".join(rels) + "\n</Relationships>\n")
    files["Metadata/model_settings.config"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + "\n".join(settings) +
        '\n  <plate>\n    <metadata key="plater_id" value="1"/>\n    <metadata key="plater_name" value=""/>\n    <metadata key="locked" value="false"/>\n'
        '    <metadata key="filament_map_mode" value="Auto For Flush"/>\n' + "\n".join(inst) + "\n  </plate>\n</config>\n")
    for n in ("[Content_Types].xml", "_rels/.rels", "Metadata/project_settings.config", "Metadata/filament_sequence.json", "Metadata/slice_info.config"):
        files[n] = zt.read(n)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in files.items(): z.writestr(n, d)
    print(OUT)

main()
