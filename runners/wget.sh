#!/bin/bash

export LZLOAD_LIB=`realpath ./runtime.txt`

# Path points to the real libraries
export LZ_LIBRARY_PATH="../srcs/wget-src-out/mod-lib:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/"

# Path points to our lzload and fake libraries
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:../srcs/wget-src-out/lib"

wget https://ftp.gnu.org/gnu/wget/wget-latest.tar.gz
