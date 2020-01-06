#!/bin/bash

{
	echo "set env LZLOAD_LIB=/home/aspire/dep-trace/runtime.txt"
	echo "set env LZ_LIBRARY_PATH=/home/aspire/src-out/mod-lib:/home/aspire/src-out/mod-lib/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu"
	echo "set env LD_LIBRARY_PATH=/home/aspire/src-out/lib"
	echo "file /usr/lib/chromium/chromium"
	echo "run --no-sandbox"
	echo "backtrace"
} | gdb &> out


