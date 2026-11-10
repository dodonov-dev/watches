# Minimal ESP-IDF project whose only product is the DC-aware 2nd-stage bootloader of env lcd316 (README.md here;
# built by tools/bootloader-dc.sh). The app side is an empty stub: pioarduino's hybrid build never rebuilds the bootloader.
cmake_minimum_required(VERSION 3.16)
set(COMPONENTS main)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(bootloader-dc)
