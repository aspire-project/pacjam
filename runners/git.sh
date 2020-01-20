#!/bin/bash

export LZLOAD_MODE="STRICT"

export LZLOAD_LIB=`realpath ./runtime.txt`

# Path points to the real libraries
export LZ_LIBRARY_PATH="../srcs/git-src-out/mod-lib:../srcs/git-src-out/mod-lib/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/"

# Path points to our lzload and fake libraries
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:../srcs/git-src-out/lib"

git clone https://github.com/pm-test-dev/test-private


