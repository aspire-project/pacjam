#!/bin/bash

LD_PRELOAD=/usr/local/lib/liblztrace.so vlc
./dep-symbol.py -d /home/aspire/var/lib/lzload/symbol-out dep-list/vlc.dep
scripts/fold.py -d . -t lztrace.trace
./dep-symbol.py -d /home/aspire/var/lib/lzload/symbol-out -b /usr/bin/vlc -t lztrace.trace
./dep-symbol.py -d /home/aspire/var/lib/lzload/symbol-out -p /home/aspire/srcs/vlc-src-out/symbols.txt

