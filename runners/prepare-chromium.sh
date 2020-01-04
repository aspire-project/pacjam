#!/bin/bash

LD_PRELOAD=/usr/local/lib/liblztrace.so chromium --no-sandbox
./dep-symbol.py -d /home/aspire/var/lib/lzload/symbol-out dep-list/chromium.dep
scripts/fold.py -d . -t lztrace.trace
./dep-symbol.py -d /home/aspire/var/lib/lzload/symbol-out -b /usr/lib/chromium/chromium -t lztrace.trace
./dep-symbol.py -d /home/aspire/var/lib/lzload/symbol-out -p /home/aspire/src-out/symbols.txt

