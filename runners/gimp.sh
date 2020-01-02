#!/bin/bash

export LZLOAD_LIB=~/src-out/runtime.txt

# Path points to the real libraries
export LZ_LIBRARY_PATH=~/src-out/mod-lib:~/src-out/mod-lib/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/

# Path points to our lzload and fake libraries
export LD_LIBRARY_PATH=~/src-out/lib:$LD_LIBRARY_PATH

gimp

