#!/bin/bash

rm tmp.lzload.trace
./dep-src.py -d src-out/vlc -r

export LZLOAD_LIB=/home/aspire/dep-trace/runtime.txt
export LZLOAD_MODE="STRICT"

# Path points to the real libraries
export LZ_LIBRARY_PATH="src-out/vlc/mod-lib:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu/:/usr/lib/x86_64-linux-gnu/vlc:/usr/lib/x86_64-linux-gnu/pulseaudio"

# Path points to our lzload and fake libraries

while true; do
	export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:src-out/vlc/lib"

	vlc -vvv vlc_formats/mkv_5.mkv

	if [ $? -eq 0 ]; then
		echo "done"
		exit
	fi

	unset LD_LIBRARY_PATH

	./scripts/fold.py -d . -t lzload.trace
	cat lzload.trace >> tmp.lzload.trace

	./dep-src.py -v -d src-out/vlc -p $HOME/var/lib/lzload/symbol-out/packages.txt -i lzload.trace >> install-log.txt

	rm lzload.trace*
done
