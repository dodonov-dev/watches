# Sourced by flash.sh / flash-win.sh: env lcd316 builds from its own PlatformIO packages dir (platformio.ini,
# tools/pio_pkgdir.py), created from the stock one on first use. Needs $ENV.
if [ "$ENV" = lcd316 ]; then
    export PLATFORMIO_PACKAGES_DIR="$HOME/.platformio/packages-lcd316"
    [ -d "$PLATFORMIO_PACKAGES_DIR" ] || { echo "first lcd316 build: copying ~/.platformio/packages (the Arduino libs then recompile, ~7 min)"; cp -a "$HOME/.platformio/packages" "$PLATFORMIO_PACKAGES_DIR"; }
else
    unset PLATFORMIO_PACKAGES_DIR
fi
