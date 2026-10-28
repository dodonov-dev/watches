# PlatformIO pre-script of env lcd316 (platformio.ini): its Arduino libs are recompiled with a custom sdkconfig,
# which rewrites the libs package in place. Built from the shared ~/.platformio/packages it would knock the AMOLED's
# stock libs out (and every switch back and forth would reinstall and recompile). Build it through tools/flash.sh /
# flash-win.sh, or with PLATFORMIO_PACKAGES_DIR=~/.platformio/packages-lcd316 (a copy of ~/.platformio/packages).
import os, sys
Import("env")  # noqa: F821 (SCons)
pkg = os.environ.get("PLATFORMIO_PACKAGES_DIR", "")
if os.path.basename(os.path.normpath(pkg)) != "packages-lcd316":
    sys.stderr.write("lcd316: build with PLATFORMIO_PACKAGES_DIR=~/.platformio/packages-lcd316 (tools/flash.sh does);"
                     " the shared packages dir would get the LCD's recompiled Arduino libs\n")
    env.Exit(1)  # noqa: F821
