#!/usr/bin/env bash
# User-owned tools. Normally invoked by linux-sudo.sh after system packages.
set -euo pipefail
trap 'echo "User setup failed at line $LINENO; rerun after fixing the reported error." >&2' ERR
[ "$(id -u)" -ne 0 ] || { echo "Run this script as your normal user, without sudo." >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
MODE="${1:-all}"
case "$MODE" in all|--install-only|--check) ;; *) echo "Usage: $0 [--install-only|--check]" >&2; exit 1 ;; esac
[ "$#" -le 1 ] || { echo "Too many arguments" >&2; exit 1; }
export PATH="$HOME/.local/bin:$PATH"
# Keep the existing nvm default when present; apt provides Node 22 on a fresh host.
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    # shellcheck source=/dev/null
    . "$HOME/.nvm/nvm.sh" --no-use
    nvm use --silent default
fi
node -e 'if (+process.versions.node.split(".")[0] < 22) process.exit(1)'
PIO="$HOME/.platformio/penv/bin/pio"
PIO_PY="$HOME/.platformio/penv/bin/python"
CAD_PY="$HOME/.venvs/cad/bin/python"
ORCA="$HOME/.local/opt/orcaslicer/OrcaSlicer-2.5.0.AppImage"

pin_pio() {
    # The platform's own bootstrap can overwrite the core. Check the running
    # version, since platformio and pioarduino share the same Python module.
    if [ ! -x "$PIO" ] || [ "$("$PIO" --version)" != 'PlatformIO Core, version 6.1.19' ]; then
        uv pip install --python "$PIO_PY" --reinstall pioarduino==6.1.19
    fi
    [ "$("$PIO" --version)" = 'PlatformIO Core, version 6.1.19' ]
}

if [ "$MODE" != --check ]; then
    mkdir -p "$HOME/.local/bin" "$HOME/.venvs" "$HOME/.platformio"
    if ! command -v uv >/dev/null; then
        python3 -m venv "$HOME/.venvs/watch-setup"
        "$HOME/.venvs/watch-setup/bin/python" -m pip install uv==0.13.8
        ln -s "$HOME/.venvs/watch-setup/bin/uv" "$HOME/.local/bin/uv"
    fi
    [ -x "$CAD_PY" ] || uv venv --python /usr/bin/python3 "$HOME/.venvs/cad"
    uv pip install --python "$CAD_PY" -r "$HERE/requirements-cad.txt"
    [ -x "$PIO_PY" ] || uv venv --python /usr/bin/python3 "$HOME/.platformio/penv"
    pin_pio
    uv pip install --python "$PIO_PY" esptool==5.3.0
    ln -sfn "$PIO" "$HOME/.local/bin/pio"
    ln -sfn "$HOME/.platformio/penv/bin/platformio" "$HOME/.local/bin/platformio"

    # Download both boards' toolchains and libraries; never upload to hardware.
    "$PIO" pkg install -d "$REPO/firmware" -e amoled191
    pin_pio
    mkdir -p "$HOME/.platformio/packages-lcd316"
    PLATFORMIO_PACKAGES_DIR="$HOME/.platformio/packages-lcd316" \
        "$PIO" pkg install -d "$REPO/firmware" -e lcd316
    pin_pio
    "$PIO_PY" - <<'PY'
from pathlib import Path
import subprocess
import sys
from platformio.package.manager.tool import ToolPackageManager
from platformio.platform.factory import PlatformFactory

platform = PlatformFactory.new("espressif32")
manager = ToolPackageManager()
for name, binary in (
    ("tool-openocd-esp32", "openocd"),
    ("tool-xtensa-esp-elf-gdb", "xtensa-esp32s3-elf-gdb"),
):
    executable = Path(platform.packages_dir) / name / "bin" / binary
    if executable.is_file():
        continue
    # Registry ZIPs contain metadata. The pinned platform's installer resolves
    # and verifies the matching Espressif binary archive for this host.
    subprocess.run([str(Path(sys.executable).with_name("pio")), "pkg", "install",
                    "--global", "--tool", platform.packages[name]["version"]], check=True)
    if not platform.install_tool(name):
        raise SystemExit(f"Debug tool installation failed: {executable}")
    # Register the resolved binary package, including when an earlier install
    # left it under a source-qualified directory rather than the documented path.
    source = Path.home() / ".platformio" / "tools" / name
    manager.install(source.as_uri(), force=True)
    if not executable.is_file():
        raise SystemExit(f"Debug tool binary missing: {executable}")
PY
    pin_pio

    cd "$REPO/sim"
    npm ci
    ./node_modules/.bin/playwright install chromium

    # Same official release as docs/desk-housing-reviews/6-rolypoly-slicer.md.
    # SHA256 is published in GitHub's release asset metadata (v2.5.0).
    ORCA_SHA=d13eb0a9cd618ed080ab6b82c64c0a60c4501aac91e88d5ac2c3b526fb141a7c
    mkdir -p "$(dirname "$ORCA")" "$HOME/.local/share/applications"
    if [ ! -f "$ORCA" ] || ! printf '%s  %s\n' "$ORCA_SHA" "$ORCA" | sha256sum --check --status; then
        curl --fail --location --retry 3 --connect-timeout 30 \
            'https://github.com/OrcaSlicer/OrcaSlicer/releases/download/v2.5.0/OrcaSlicer_Linux_AppImage_Ubuntu2404_V2.5.0.AppImage' \
            --output "$ORCA.part"
        printf '%s  %s\n' "$ORCA_SHA" "$ORCA.part" | sha256sum --check
        chmod 0755 "$ORCA.part"
        mv "$ORCA.part" "$ORCA"
    fi
    ln -sfn "$ORCA" "$HOME/.local/bin/orca-slicer"
    cat > "$HOME/.local/share/applications/orcaslicer.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=OrcaSlicer
Comment=Prepare the watch housing for 3D printing
Exec="$HOME/.local/bin/orca-slicer" %F
Icon=applications-engineering
Terminal=false
Categories=Graphics;3DGraphics;Engineering;
MimeType=model/stl;model/3mf;
EOF
fi

if [ "$MODE" != --install-only ]; then
    python3 -c 'import serial, PIL, numpy, bleak; print("Host Python imports OK")'
    "$CAD_PY" -c 'import build123d, OCP, pyvista, vtk, trimesh, svgelements, cv2, PIL; print("CAD Python imports OK")'
    "$PIO" --version
    [ "$("$PIO" --version)" = 'PlatformIO Core, version 6.1.19' ]
    "$PIO_PY" -m esptool version
    "$HOME/.platformio/packages/tool-openocd-esp32/bin/openocd" --version
    "$HOME/.platformio/packages/tool-xtensa-esp-elf-gdb/bin/xtensa-esp32s3-elf-gdb" --version
    cd "$REPO/sim"
    npm run build
    node --input-type=module <<'JS'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
try {
    const page = await browser.newPage();
    await page.setContent('<canvas id="c" width="8" height="8"></canvas>');
    const pixel = await page.evaluate(() => {
        const ctx = document.getElementById('c').getContext('2d');
        ctx.fillStyle = '#ff0000'; ctx.fillRect(0, 0, 8, 8);
        return [...ctx.getImageData(0, 0, 1, 1).data];
    });
    if (String(pixel) !== '255,0,0,255') throw new Error(`Canvas rendering failed: ${pixel}`);
    console.log('Playwright Chromium canvas OK');
} finally { await browser.close(); }
JS
    SMOKE_DIR="$(mktemp -d /tmp/watches-setup-XXXXXX)"
    xvfb-run -a "$CAD_PY" "$HERE/cad_preview.py" --smoke "$SMOKE_DIR"
    (cd "$SMOKE_DIR" && xvfb-run -a "$HOME/.local/bin/orca-slicer" --help > orca-help.txt)
    echo "CAD exports / preview and OrcaSlicer CLI OK: $SMOKE_DIR"
    echo "User tools ready. Simulator: cd $REPO/sim && npm run dev"
fi
