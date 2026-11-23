"""Round-7 plate from the printed round-5/6 plate: body mesh swapped, door + arc gauge dropped, cups verbatim,
optional pebble shell + lid swapped in.   python mkplate7.py OUT.3mf BODY.stl [SHELL.stl LID.stl] [k=v body settings]"""
import zipfile, re, sys, numpy as np, pyvista as pv

BASE = "/home/andrey/_PROJECTS/watches-rolypoly/cad/desk/to-print/_5_plate_roly_poly_pebble.3mf"
args = [a for a in sys.argv[1:] if "=" not in a]
extra = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
OUT, BODY = args[0], args[1]
PEB = args[2:4] if len(args) >= 4 else None
z = zipfile.ZipFile(BASE)
model = z.read("3D/3dmodel.model").decode()
cfg = z.read("Metadata/model_settings.config").decode()
rels = z.read("3D/_rels/3dmodel.model.rels").decode()
files = {}

def mesh_xml(stl, oid):
    m = pv.read(stl).triangulate().clean()
    P = m.points.astype(float); c = (P.min(0) + P.max(0)) / 2; P -= c
    F = m.faces.reshape(-1, 4)[:, 1:]
    old = z.read(f"3D/Objects/object_{oid}.model").decode()
    head = old[:old.index("<vertices>") + len("<vertices>")]
    tail = old[old.index("</triangles>"):]
    vx = "\n".join(f'     <vertex x="{a:.6f}" y="{b:.6f}" z="{d:.6f}"/>' for a, b, d in P)
    tr = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{d}"/>' for a, b, d in F)
    return (head + "\n" + vx + "\n    </vertices>\n    <triangles>\n" + tr + "\n    " + tail).encode(), P, len(F)

def swap(item_id, file_n, stl, name):
    global model, cfg
    data, P, nf = mesh_xml(stl, file_n)
    files[f"3D/Objects/object_{file_n}.model"] = data
    h = P[:, 2].max()
    # item: keep rotation + xy, z = half height (rotation is about z only for these items)
    def fix(mo):
        t = mo.group(2).split(); t[11] = f"{h:.6f}"; return mo.group(1) + " ".join(t) + '"'
    model = re.sub(rf'(<item objectid="{item_id}"[^>]*transform=")([^"]+)"', fix, model)
    # the component offset (Bambu's 3.8e-06 etc.) -> 0
    model = re.sub(rf'(<component p:path="/3D/Objects/object_{file_n}.model"[^>]*transform=")[^"]+"', r'\g<1>1 0 0 0 1 0 0 0 1 0 0 0"', model)
    o = re.search(rf'<object id="{item_id}">.*?</object>', cfg, re.S).group(0)
    o2 = re.sub(r'(key="(?:name|source_file)" value=")[^"]+"', rf'\g<1>{name}"', o)
    o2 = re.sub(r'face_count="\d+"', f'face_count="{nf}"', o2)
    o2 = re.sub(r'\s*<metadata key="source_offset_[xyz]"[^>]*/>', "", o2)
    o2 = re.sub(r'(key="matrix" value=")[^"]+"', r'\g<1>1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"', o2)
    cfg = cfg.replace(o, o2)
    return P

def drop(item_id, file_n):
    global model, cfg, rels
    model = re.sub(rf'\s*<item objectid="{item_id}"[^>]*/>', "", model)
    model = re.sub(rf'\s*<object id="{item_id}"[^>]*>\s*<components>.*?</object>', "", model, flags=re.S)
    cfg = re.sub(rf'\s*<object id="{item_id}">.*?</object>', "", cfg, flags=re.S)
    cfg = re.sub(rf'\s*<model_instance>\s*<metadata key="object_id" value="{item_id}"/>.*?</model_instance>', "", cfg, flags=re.S)
    cfg = re.sub(rf'\s*<assemble_item object_id="{item_id}"[^>]*/>', "", cfg)
    rels = re.sub(rf'\s*<Relationship Target="/3D/Objects/object_{file_n}.model"[^>]*/>', "", rels)
    return f"3D/Objects/object_{file_n}.model"

dropped = [drop(6, 4), drop(10, 5)]                      # door, arc gauge
import os
if os.environ.get("NOCUPS"): dropped += [drop(4, 2), drop(8, 3)]
swap(2, 1, BODY, "rolypoly-r7-body.stl")
def setkv(item_id, kv):
    global cfg
    o = re.search(rf'<object id="{item_id}">.*?</object>', cfg, re.S).group(0)
    o2 = o
    for k, v in kv.items():
        if f'key="{k}"' in o2:
            o2 = re.sub(rf'(key="{k}" value=")[^"]*"', rf'\g<1>{v}"', o2)
        else:
            o2 = o2.replace('    <metadata key="extruder"', f'    <metadata key="{k}" value="{v}"/>\n    <metadata key="extruder"', 1)
    cfg = cfg.replace(o, o2)
if extra:                                                # body + pebble shell settings
    setkv(2, extra)
    setkv(12, extra)
if PEB:
    swap(12, 6, PEB[0], PEB[0].rsplit("/", 1)[-1])
    swap(14, 7, PEB[1], PEB[1].rsplit("/", 1)[-1])

import uuid, json
def add(k, stl, name, x, y, kv):
    """k-th added object: file object_{7+k}.model, ids 14+2k / 13+2k, at (x, y) in its STL orientation."""
    global model, rels, cfg
    fn, oid, cid = 7 + k, 14 + 2 * k, 13 + 2 * k
    m = pv.read(stl).triangulate().clean()
    P = m.points.astype(float); P -= (P.min(0) + P.max(0)) / 2; F = m.faces.reshape(-1, 4)[:, 1:]; h = P[:, 2].max()
    hdr = z.read("3D/Objects/object_7.model").decode(); hdr = hdr[:hdr.index("<vertices>") + len("<vertices>")]
    hdr = re.sub(r'<object id="\d+"', f'<object id="{cid}"', hdr)
    files[f"3D/Objects/object_{fn}.model"] = (hdr + "\n" + "\n".join(f'     <vertex x="{a:.6f}" y="{b:.6f}" z="{d:.6f}"/>' for a, b, d in P)
        + "\n    </vertices>\n    <triangles>\n" + "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{d}"/>' for a, b, d in F)
        + "\n    </triangles>\n   </mesh>\n  </object>\n </resources>\n <build/>\n</model>\n").encode()
    model = model.replace(" </resources>", f'  <object id="{oid}" p:UUID="{uuid.uuid4()}" type="model">\n   <components>\n    <component p:path="/3D/Objects/object_{fn}.model" objectid="{cid}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n   </components>\n  </object>\n </resources>', 1)
    model = model.replace(" </build>", f'  <item objectid="{oid}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 {x} {y} {h:.6f}" printable="1"/>\n </build>', 1)
    rels = rels.replace("</Relationships>", f' <Relationship Target="/3D/Objects/object_{fn}.model" Id="rel-{fn}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>')
    md = "".join(f'    <metadata key="{a}" value="{b}"/>\n' for a, b in kv.items())
    src = stl.rsplit("/", 1)[-1]
    cfg = cfg.replace("  <plate>", f'  <object id="{oid}">\n    <metadata key="name" value="{name}"/>\n{md}    <metadata key="extruder" value="1"/>\n    <part id="{cid}" subtype="normal_part">\n      <metadata key="name" value="{name}"/>\n      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n      <metadata key="source_file" value="{src}"/>\n      <metadata key="source_object_id" value="0"/>\n      <metadata key="source_volume_id" value="0"/>\n    </part>\n  </object>\n  <plate>', 1)
    cfg = cfg.replace("  </plate>", f'    <model_instance>\n      <metadata key="object_id" value="{oid}"/>\n      <metadata key="instance_id" value="0"/>\n      <metadata key="identify_id" value="{400 + k}"/>\n    </model_instance>\n  </plate>', 1)
# ADD='[["stl", "name", x, y, {settings}], ...]'
for k, (stl, name, x, y, kv) in enumerate(json.loads(os.environ.get("ADD", "[]")), start=1):
    add(k, stl, name, x, y, kv)
# plate thumbnails are stale: drop them and their references
cfg = re.sub(r'\s*<metadata key="(?:thumbnail_file|thumbnail_no_light_file|top_file|pick_file)"[^>]*/>', "", cfg)
skip = set(dropped) | {"Metadata/cut_information.xml"} | {n for n in z.namelist() if n.endswith(".png")}
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zo:
    for n in z.namelist():
        if n in skip:
            continue
        if n in files: zo.writestr(n, files[n])
        elif n == "3D/3dmodel.model": zo.writestr(n, model)
        elif n == "Metadata/model_settings.config": zo.writestr(n, cfg)
        elif n == "3D/_rels/3dmodel.model.rels": zo.writestr(n, rels)
        else: zo.writestr(n, z.read(n))
    for n, d in files.items():
        if n not in z.namelist(): zo.writestr(n, d)
# footprint report (world xy boxes)
for oid, t in re.findall(r'<item objectid="(\d+)"[^>]*transform="([^"]+)"', model):
    f = re.search(rf'<object id="{oid}"[^>]*>\s*<components>\s*<component p:path="/([^"]+)"', model).group(1)
    s = files.get(f, None) or z.read(f)
    V = np.array(re.findall(rb'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', s), float)
    T = np.array(t.split(), float); W = V @ T[:9].reshape(3, 3) + T[9:]
    print(oid, f, W.min(0).round(1), W.max(0).round(1))
print("written", OUT)
