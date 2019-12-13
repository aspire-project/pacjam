#!/bin/bash

export LZLOAD_LIB=`realpath ./runtime.txt`

# Path points to the real libraries
export LZ_LIBRARY_PATH="../srcs/firefox-esr-src-out/mod-lib:../srcs/firefox-esr-src-out/mod-lib/lib/x86_64-linux-gnu:../srcs/firefox-esr-src-out/mod-lib/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/"

# Path points to our lzload and fake libraries
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:../srcs/firefox-esr-src-out/lib"


firefox-esr 2> out


