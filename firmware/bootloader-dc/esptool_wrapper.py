# IDF calls `$PYTHON $ESPTOOL_WRAPPER <idf>/components/esptool_py/esptool/esptool.py ARGS...`: the IDF venv of
# pioarduino has no esptool, so run PlatformIO's (penv, esptool 5.3) with IDF's own arguments instead.
import os, sys
py = os.path.expanduser("~/.platformio/penv/bin/python")
os.execv(py, [py, "-m", "esptool"] + sys.argv[2:])
