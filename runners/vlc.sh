#!/bin/bash

export LZLOAD_LIB=/home/aspire/dep-trace/runtime.txt


# Path points to the real libraries
export LZ_LIBRARY_PATH="../vlc-src-out/mod-lib:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/:/usr/lib/x86_64-linux-gnu/vlc:/usr/lib/x86_64-linux-gnu/pulseaudio"

# Path points to our lzload and fake libraries
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:../vlc-src-out/lib"

vlc

