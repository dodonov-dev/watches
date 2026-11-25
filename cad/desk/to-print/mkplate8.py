"""Round-8 plate from the printed round-7 plate (_7_plate_roly_poly_pebble_ringE.3mf): its body / cup-rock settings kept,
meshes swapped; cup-flat, pebble parts, rings and test strip dropped; roly-poly logo stencils and the cast plug added.
   python mkplate8.py OUT.3mf OUTDIR   (OUTDIR = cad/desk/out-rolypoly)
Cup-rock lies on its back as round 7, then tipped CUP_TILT (-35 deg) about the plate's x toward its rim: the near-flat top patch
that printed topographic rings on round 7's front moves to the lower front by the keel (hidden, not a rocking contact),
and the support area on the back drops (874 -> ~330 mm2). At -35 its centre of mass stays over its own contact strip (at -40 it hangs 2.5 past it, on the supports)."""
import zipfile, re, sys, uuid, numpy as np, pyvista as pv

BASE = "/home/andrey/_PROJECTS/watches-rolypoly/cad/desk/to-print/_7_plate_roly_poly_pebble_ringE.3mf"
OUT, SRC = sys.argv[1], sys.argv[2].rstrip("/")
import os
CUP_TILT = float(os.environ.get("CUP_TILT", "-35"))
z = zipfile.ZipFile(BASE)
model = z.read("3D/3dmodel.model").decode()
cfg = z.read("Metadata/model_settings.config").decode()
rels = z.read("3D/_rels/3dmodel.model.rels").decode()
files = {}

def Rx(d):
    t = np.radians(d); return np.array([[1, 0, 0], [0, np.cos(t), -np.sin(t)], [0, np.sin(t), np.cos(t)]])

def Rz(d):
    t = np.radians(d); return np.array([[np.cos(t), -np.sin(t), 0], [np.sin(t), np.cos(t), 0], [0, 0, 1]])

def load(stl):
    m = pv.read(stl).triangulate().clean()
    P = m.points.astype(float); P -= (P.min(0) + P.max(0)) / 2
    return m, P, m.faces.reshape(-1, 4)[:, 1:]

def body_xml(P, F):
    return ("\n" + "\n".join(f'     <vertex x="{a:.6f}" y="{b:.6f}" z="{d:.6f}"/>' for a, b, d in P)
            + "\n    </vertices>\n    <triangles>\n" + "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{d}"/>' for a, b, d in F))

def transform(M, P, x, y):
    """3MF item transform (row vectors: world = v @ R + t) for column matrix M, object at (x, y) on the plate."""
    W = P @ M.T
    return " ".join(f"{v:.9g}" for v in M.T.reshape(-1)) + f" {x} {y} {-W[:, 2].min():.6f}"

def set_cfg(item_id, name, nf, kv=None):
    global cfg
    o = re.search(rf'<object id="{item_id}">.*?</object>', cfg, re.S).group(0)
    o2 = re.sub(r'(key="(?:name|source_file)" value=")[^"]+"', rf'\g<1>{name}"', o)
    o2 = re.sub(r'face_count="\d+"', f'face_count="{nf}"', o2)
    o2 = re.sub(r'\s*<metadata key="source_offset_[xyz]"[^>]*/>', "", o2)
    o2 = re.sub(r'(key="matrix" value=")[^"]+"', r'\g<1>1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"', o2)
    for k, v in (kv or {}).items():
        if f'key="{k}"' in o2:
            o2 = re.sub(rf'(key="{k}" value=")[^"]*"', rf'\g<1>{v}"', o2)
        else:
            o2 = o2.replace('    <metadata key="extruder"', f'    <metadata key="{k}" value="{v}"/>\n    <metadata key="extruder"', 1)
    cfg = cfg.replace(o, o2)

def swap(item_id, file_n, stl, name, M, x, y, kv=None):
    """Replace item's mesh; place it with column rotation M at (x, y), resting on the plate."""
    global model
    m, P, F = load(stl)
    old = z.read(f"3D/Objects/object_{file_n}.model").decode()
    head = old[:old.index("<vertices>") + len("<vertices>")]
    tail = old[old.index("</triangles>"):]
    files[f"3D/Objects/object_{file_n}.model"] = (head + body_xml(P, F) + "\n    " + tail).encode()
    model = re.sub(rf'(<item objectid="{item_id}"[^>]*transform=")[^"]+"', rf'\g<1>{transform(M, P, x, y)}"', model)
    model = re.sub(rf'(<component p:path="/3D/Objects/object_{file_n}.model"[^>]*transform=")[^"]+"',
                   r'\g<1>1 0 0 0 1 0 0 0 1 0 0 0"', model)
    set_cfg(item_id, name, len(F), kv)

def drop(item_id, file_n):
    global model, cfg, rels
    model = re.sub(rf'\s*<item objectid="{item_id}"[^>]*/>', "", model)
    model = re.sub(rf'\s*<object id="{item_id}"[^>]*>\s*<components>.*?</object>', "", model, flags=re.S)
    cfg = re.sub(rf'\s*<object id="{item_id}">.*?</object>', "", cfg, flags=re.S)
    cfg = re.sub(rf'\s*<model_instance>\s*<metadata key="object_id" value="{item_id}"/>.*?</model_instance>', "", cfg, flags=re.S)
    cfg = re.sub(rf'\s*<assemble_item object_id="{item_id}"[^>]*/>', "", cfg)
    rels = re.sub(rf'\s*<Relationship Target="/3D/Objects/object_{file_n}.model"[^>]*/>', "", rels)
    return f"3D/Objects/object_{file_n}.model"

def add(k, stl, name, M, x, y, kv):
    global model, rels, cfg
    fn, oid, cid = 20 + k, 40 + 2 * k, 39 + 2 * k
    m, P, F = load(stl)
    hdr = z.read("3D/Objects/object_1.model").decode(); hdr = hdr[:hdr.index("<vertices>") + len("<vertices>")]
    hdr = re.sub(r'<object id="\d+"', f'<object id="{cid}"', hdr)
    files[f"3D/Objects/object_{fn}.model"] = (hdr + body_xml(P, F)
        + "\n    </triangles>\n   </mesh>\n  </object>\n </resources>\n <build/>\n</model>\n").encode()
    model = model.replace(" </resources>", f'  <object id="{oid}" p:UUID="{uuid.uuid4()}" type="model">\n   <components>\n    <component p:path="/3D/Objects/object_{fn}.model" objectid="{cid}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n   </components>\n  </object>\n </resources>', 1)
    model = model.replace(" </build>", f'  <item objectid="{oid}" p:UUID="{uuid.uuid4()}" transform="{transform(M, P, x, y)}" printable="1"/>\n </build>', 1)
    rels = rels.replace("</Relationships>", f' <Relationship Target="/3D/Objects/object_{fn}.model" Id="rel-{fn}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>')
    md = "".join(f'    <metadata key="{a}" value="{b}"/>\n' for a, b in kv.items())
    src = stl.rsplit("/", 1)[-1]
    cfg = cfg.replace("  <plate>", f'  <object id="{oid}">\n    <metadata key="name" value="{name}"/>\n{md}    <metadata key="extruder" value="1"/>\n    <part id="{cid}" subtype="normal_part">\n      <metadata key="name" value="{name}"/>\n      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n      <metadata key="source_file" value="{src}"/>\n      <metadata key="source_object_id" value="0"/>\n      <metadata key="source_volume_id" value="0"/>\n    </part>\n  </object>\n  <plate>', 1)
    cfg = cfg.replace("  </plate>", f'    <model_instance>\n      <metadata key="object_id" value="{oid}"/>\n      <metadata key="instance_id" value="0"/>\n      <metadata key="identify_id" value="{500 + k}"/>\n    </model_instance>\n  </plate>', 1)

# --- the plate
dropped = [drop(8, 3), drop(12, 6), drop(14, 7), drop(16, 8), drop(18, 9), drop(22, 11)]   # cup-flat, pebble, rings, strip
BODY_ROT = 60.0                                                     # round 7's body turn on the plate, kept
swap(2, 1, f"{SRC}/body.stl", "rolypoly-r8-body.stl", Rz(BODY_ROT), 170, 170)
ON_BACK = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]])             # model y -> -z: front up, back on the plate
swap(4, 2, f"{SRC}/cup-rock.stl", "rolypoly-r8-cup-rock.stl", Rx(CUP_TILT) @ ON_BACK, 70, 75)
swap(20, 10, f"{SRC}/logo-stencil.stl", "rolypoly-r8-logo-stencil.stl", np.eye(3), 70, 190)
# cast plug on its sloped face (handle up, leaning with the slope): turn the big bottom face's normal to -z
pm = pv.read(f"{SRC}/cast-plug.stl").compute_normals(cell_normals=True, point_normals=False)
n = pm.cell_data["Normals"][np.argmax(pm.compute_cell_sizes()["Area"])]
plug_rot = Rx(np.degrees(np.arctan2(-n[1], -n[2])))
assert np.allclose(plug_rot @ n, [0, 0, -1], atol=1e-3), plug_rot @ n
add(1, f"{SRC}/cast-plug.stl", "rolypoly-r8-cast-plug", plug_rot, 110, 205, {})

cfg = re.sub(r'\s*<metadata key="(?:thumbnail_file|thumbnail_no_light_file|top_file|pick_file)"[^>]*/>', "", cfg)
skip = set(dropped) | {"Metadata/cut_information.xml"} | {n_ for n_ in z.namelist() if n_.endswith(".png")}
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zo:
    for n_ in z.namelist():
        if n_ in skip:
            continue
        if n_ in files: zo.writestr(n_, files[n_])
        elif n_ == "3D/3dmodel.model": zo.writestr(n_, model)
        elif n_ == "Metadata/model_settings.config": zo.writestr(n_, cfg)
        elif n_ == "3D/_rels/3dmodel.model.rels": zo.writestr(n_, rels)
        else: zo.writestr(n_, z.read(n_))
    for n_, d in files.items():
        if n_ not in z.namelist(): zo.writestr(n_, d)
# footprints (world boxes)
for oid, t in re.findall(r'<item objectid="(\d+)"[^>]*transform="([^"]+)"', model):
    f = re.search(rf'<object id="{oid}"[^>]*>\s*<components>\s*<component p:path="/([^"]+)"', model).group(1)
    V = np.array(re.findall(rb'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', files.get(f) or z.read(f)), float)
    T = np.array(t.split(), float); W = V @ T[:9].reshape(3, 3) + T[9:]
    print(oid, f, W.min(0).round(1), W.max(0).round(1))
print("written", OUT)
