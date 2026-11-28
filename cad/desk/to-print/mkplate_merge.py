"""One plate from two Bambu Studio projects that share their process / filament / machine settings (checked): every part
of ADD is added to BASE with its own per-object settings; BASE's parts stay where they are, with their seam paint,
support enforcers and settings.

   python mkplate_merge.py BASE.3mf ADD.3mf OUT.3mf  ID=X,Y [ID=X,Y ...]
   ID: an item's object id in ADD's 3D/3dmodel.model; X, Y: its centre on the plate (its turn and height are kept).
   SET:NAME:KEY=VALUE (any number): a per-object setting for every object of OUT whose name contains NAME (replaced or added),
   e.g. SET:rolypoly-r8-body:support_type=tree(manual).
   ENF:ID=ENFORCER.stl,PART.stl: a support-enforcer part for ADD's item ID; ENFORCER.stl is in the frame of PART.stl, the
   STL the item's mesh was made from (the plate scripts centre a mesh on its bounding box)."""
import sys, re, json, uuid, zipfile
import numpy as np

BASE, ADD, OUT = sys.argv[1:4]
PLACE = {a.split("=")[0]: tuple(float(v) for v in a.split("=")[1].split(",")) for a in sys.argv[4:] if a[:4] not in ("SET:", "ENF:")}
ENF = {a[4:].split("=")[0]: a.split("=", 1)[1].split(",") for a in sys.argv[4:] if a.startswith("ENF:")}
SETS = [(a.split(":", 2)[1], *a.split(":", 2)[2].split("=", 1)) for a in sys.argv[4:] if a.startswith("SET:")]
zb, za = zipfile.ZipFile(BASE), zipfile.ZipFile(ADD)
rd = lambda z, n: z.read(n).decode()
pb, pa = (json.loads(rd(z, "Metadata/project_settings.config")) for z in (zb, za))
diff = [k for k in set(pb) | set(pa) if pb.get(k) != pa.get(k)]
assert not diff, f"the two projects' settings differ: {sorted(diff)[:8]}"

model, cfg, rels = rd(zb, "3D/3dmodel.model"), rd(zb, "Metadata/model_settings.config"), rd(zb, "3D/_rels/3dmodel.model.rels")
amodel, acfg = rd(za, "3D/3dmodel.model"), rd(za, "Metadata/model_settings.config")
used = {int(i) for i in re.findall(r'<object id="(\d+)"', model)}
for n in zb.namelist():
    if n.startswith("3D/Objects/"):
        used |= {int(i) for i in re.findall(rb'<object id="(\d+)"', zb.read(n))}
idents = {int(i) for i in re.findall(r'key="identify_id" value="(\d+)"', cfg)}
fresh = lambda pool: next(i for i in range(max(pool) + 1, 10 ** 6) if i not in pool)
files, k = {}, 0

for oid, tr in re.findall(r'<item objectid="(\d+)"[^>]*transform="([^"]+)"', amodel):
    assert oid in PLACE, f"no place given for ADD's item {oid}"
    comps = re.findall(r'<component p:path="/([^"]+)" objectid="(\d+)"',
                       re.search(rf'<object id="{oid}"[^>]*>\s*<components>(.*?)</components>', amodel, re.S).group(1))
    assert len(comps) == 1, f"item {oid}: {len(comps)} components (only single-part objects are handled)"
    src, cid = comps[0]
    k += 1
    new_c = fresh(used); used.add(new_c)
    new_o = fresh(used); used.add(new_o)
    fn = f"3D/Objects/object_{30 + k}.model"
    txt = za.read(src)
    assert len(re.findall(rb'<object id="\d+"', txt)) == 1, f"{src}: more than one object"
    files[fn] = re.sub(rb'<object id="\d+" p:UUID="[^"]+"', f'<object id="{new_c}" p:UUID="{uuid.uuid4()}"'.encode(), txt, count=1)
    # its footprint, to say where it lands
    V = np.array(re.findall(rb'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', txt), float)
    T = np.array(tr.split(), float)
    T[9], T[10] = PLACE[oid]
    W = V @ T[:9].reshape(3, 3) + T[9:]
    model = model.replace(" </resources>", f'  <object id="{new_o}" p:UUID="{uuid.uuid4()}" type="model">\n   <components>\n'
                          f'    <component p:path="/{fn}" objectid="{new_c}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
                          f'   </components>\n  </object>\n </resources>', 1)
    model = model.replace(" </build>", f'  <item objectid="{new_o}" p:UUID="{uuid.uuid4()}" transform="{" ".join(f"{v:.9g}" for v in T)}" printable="1"/>\n </build>', 1)
    rels = rels.replace("</Relationships>", f' <Relationship Target="/{fn}" Id="rel-add-{k}" '
                        f'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>')
    o = re.search(rf'  <object id="{oid}">.*?</object>\n', acfg, re.S).group(0)
    o = o.replace(f'<object id="{oid}">', f'<object id="{new_o}">', 1)
    o = re.sub(rf'<part id="{cid}"', f'<part id="{new_c}"', o, count=1)
    assert f'<part id="{new_c}"' in o, f"item {oid}: its part {cid} is not in ADD's settings"
    if oid in ENF:
        import pyvista as pv
        em, ref = (pv.read(f).triangulate() for f in ENF[oid])
        b = np.array(ref.bounds).reshape(3, 2)
        assert np.allclose(b[:, 1] - b[:, 0], V.max(0) - V.min(0), atol=1e-3), f"item {oid}: {ENF[oid][1]} is not its mesh"
        P, F = np.asarray(em.points) - b.mean(1) + (V.max(0) + V.min(0)) / 2, em.faces.reshape(-1, 4)[:, 1:]
        new_e = fresh(used); used.add(new_e)
        mesh = (f'  <object id="{new_e}" p:UUID="{uuid.uuid4()}" type="model">\n   <mesh>\n    <vertices>\n'
                + "".join(f'     <vertex x="{a:.6f}" y="{b_:.6f}" z="{c:.6f}"/>\n' for a, b_, c in P) + "    </vertices>\n    <triangles>\n"
                + "".join(f'     <triangle v1="{a}" v2="{b_}" v3="{c}"/>\n' for a, b_, c in F) + "    </triangles>\n   </mesh>\n  </object>\n")
        assert files[fn].count(b" </resources>") == 1
        files[fn] = files[fn].replace(b" </resources>", mesh.encode() + b" </resources>")
        k0 = model.index(f'    <component p:path="/{fn}" objectid="{new_c}" ')            # the enforcer's component after the part's
        k1 = model.index("\n", k0) + 1
        model = model[:k1] + f'    <component p:path="/{fn}" objectid="{new_e}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n' + model[k1:]
        o = o.replace("  </object>\n", f'    <part id="{new_e}" subtype="support_enforcer">\n      <metadata key="name" value="support enforcer: slot top end walls"/>\n'
                      '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n    </part>\n  </object>\n', 1)
        print(f"enforcer on item {oid}: part {new_e}, {len(F)} triangles, z {P[:, 2].min() - V[:, 2].min():.2f}..{P[:, 2].max() - V[:, 2].min():.2f} above the bed")
    cfg = cfg.replace("  <plate>", o + "  <plate>", 1)
    ident = fresh(idents); idents.add(ident)
    last = cfg.rindex("    </model_instance>") + len("    </model_instance>\n")
    cfg = (cfg[:last] + f'    <model_instance>\n      <metadata key="object_id" value="{new_o}"/>\n      <metadata key="instance_id" value="0"/>\n'
           f'      <metadata key="identify_id" value="{ident}"/>\n    </model_instance>\n' + cfg[last:])
    name = re.search(r'key="name" value="([^"]+)"', o).group(1)
    print(f"added {name}: object {new_o} / part {new_c}, x {W[:, 0].min():.1f}..{W[:, 0].max():.1f}, y {W[:, 1].min():.1f}..{W[:, 1].max():.1f}, "
          f"z {W[:, 2].min():.2f}..{W[:, 2].max():.1f}")

for nm, key, val in SETS:
    hit = 0
    for o in re.findall(r'  <object id="\d+">.*?</object>\n', cfg, re.S):
        if nm not in re.search(r'key="name" value="([^"]+)"', o).group(1):
            continue
        line = f'    <metadata key="{key}" value="{val}"/>\n'
        o2, n = re.subn(rf'    <metadata key="{re.escape(key)}" value="[^"]*"/>\n', line, o, count=1)
        if not n:
            o2 = o.replace('    <metadata key="extruder"', line + '    <metadata key="extruder"', 1)
        assert line in o2, f"{nm}: could not set {key}"
        cfg = cfg.replace(o, o2, 1); hit += 1
    assert hit, f"no object named *{nm}*"
    print(f"set {key} = {val} on {hit} object(s) named *{nm}*")

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zo:
    for n in zb.namelist():
        zo.writestr(n, {"3D/3dmodel.model": model, "Metadata/model_settings.config": cfg, "3D/_rels/3dmodel.model.rels": rels}.get(n) or zb.read(n))
    for n, d in files.items():
        zo.writestr(n, d)
print("written", OUT)
