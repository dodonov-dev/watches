"""The edge shade's ray tables of a build, generated on the build host into a header (rod_rays_gen.h: ROD_GEN, const,
so in flash; render.cpp uses them with -DROD_RAYS_GEN instead of building them in PSRAM at boot).

PlatformIO pre-script (platformio.ini extra_scripts): compiles tools/gen_rod_rays.cpp with the build's -D flags,
writes $BUILD_DIR/rodgen/rod_rays_gen.h (only when it changed) and adds -DROD_RAYS_GEN and that include path.
Host tools: generate(defines, out_dir) with the -D flags of their own build (tools/check_shade_rows.py).
"""
import os, shlex, subprocess, sys, tempfile
from pathlib import Path
try:
    FW = Path(__file__).resolve().parents[1]
except NameError:   # run by SCons (exec without __file__): from the project dir
    FW = Path(os.getcwd()).resolve()

def generate(defines, out_dir):
    """defines: ['-DNAME', '-DNAME=V', ...]; writes out_dir/rod_rays_gen.h, returns its path."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rodgen-') as t:
        exe = Path(t) / 'gen'
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffp-contract=off', *defines,
                        '-I', str(FW / 'src'), '-I', str(FW.parent / 'spec'), str(FW / 'tools' / 'gen_rod_rays.cpp'), '-o', str(exe)], check=True)
        text = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
    out = out_dir / 'rod_rays_gen.h'
    if not out.exists() or out.read_text() != text: out.write_text(text)
    return out

def _pio():
    Import("env")  # noqa: F821 (SCons)
    flags = []
    for f in list(env.get("BUILD_FLAGS", [])) + shlex.split(os.environ.get("PLATFORMIO_BUILD_FLAGS", "")):  # noqa: F821
        flags += shlex.split(env.subst(f)) if isinstance(f, str) else []  # noqa: F821
    defines = list(dict.fromkeys(f for f in flags if f.startswith('-D')))
    out_dir = Path(env.subst("$BUILD_DIR")) / "rodgen"  # noqa: F821
    try:
        generate(defines, out_dir)
    except subprocess.CalledProcessError as e:
        sys.stderr.write("gen_rod_rays: the host generator failed (%s)\n" % e)
        env.Exit(1)  # noqa: F821
    env.Append(CPPPATH=[str(out_dir)], CPPDEFINES=["ROD_RAYS_GEN"])  # noqa: F821

if __name__ != '__main__':
    try:
        Import  # noqa: F821 (only defined inside SCons)
    except NameError:
        pass
    else:
        _pio()
