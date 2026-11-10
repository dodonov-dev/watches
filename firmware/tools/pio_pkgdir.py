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
# Its flash runs at 120 MHz in HPM dummy-cycle mode: the DC-aware bootloader of bootloader-dc/ must stay at 0x0. Every
# flash-writing target of the platform (builder/main.py: upload, erase_upload, uploadfs, uploadfsota share $UPLOADCMD,
# which writes Arduino's bootloader with its header patched to DIO; erase wipes 0x0) is refused: tools/flash.sh instead.
FLASH_TARGETS = {"upload", "erase_upload", "uploadfs", "uploadfsota", "erase"}
blocked = sorted(FLASH_TARGETS & set(COMMAND_LINE_TARGETS))  # noqa: F821 (SCons)
if blocked:
    sys.stderr.write("lcd316: `pio run -t %s` refused: flash with tools/flash.sh / flash-win.sh. pio's uploader would"
                     " replace (or erase) the DC-aware bootloader (bootloader-dc/), and this app wedges without it at the"
                     " next reset\n" % ",".join(blocked))
    env.Exit(1)  # noqa: F821
