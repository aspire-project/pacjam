#!/bin/bash

export LZLOAD_LIB=/home/aspire/dep-trace/runtime.txt

# Path points to the real libraries
export LZ_LIBRARY_PATH=/home/aspire/src-out/mod-lib:/home/aspire/src-out/mod-lib/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu

# Path points to our lzload and fake libraries
export LD_LIBRARY_PATH=/home/aspire/src-out/lib:

chromium --no-sandbox &> out

