cmake_minimum_required(VERSION 3.13)

# Also:
# export PICO_SDK_PATH=/home/pi/pico/src/pico-sdk
# ln -s ~/pico/src/pico-sdk/external/pico_sdk_import.cmake .
# mkdir build
# cd build
# cmake ..
# make

# Defaulting PICO_PLATFORM to rp2040 since not specified.
# Values found in pico-sdk/cmake/preload/platforms/*.cmake

include(pico_sdk_import.cmake)

# Disables color in progress...
set(CMAKE_COLOR_MAKEFILE 0)

project(psst_demo_project C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKEE_CXX_STANDARD 17)

# Works (keep after project)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -fdiagnostics-color=never -g")

pico_sdk_init()

add_executable(psst_demo)

#pico_enable_stdio_usb(psst_demo 1)
pico_enable_stdio_uart(psst_demo 1)

pico_generate_pio_header(psst_demo ${CMAKE_CURRENT_LIST_DIR}/psst.pio)

target_sources(psst_demo PRIVATE psst-demo.c)

target_link_libraries(psst_demo PRIVATE pico_stdlib hardware_pio)
pico_add_extra_outputs(psst_demo)
