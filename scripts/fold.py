#!/usr/bin/env python3

import os.path
import glob
from optparse import OptionParser 

usage = "usage: %prog [options]" 
parser = OptionParser(usage=usage)
parser.add_option('-d', '--dir', dest='working_dir', default='.', help='use DIR as working output directory', metavar='DIR') 
parser.add_option('-p', '--preserve', dest='preserve', action='store_true', help='preserve process trace files (do not delete)')
parser.add_option('-t', '--trace-name', dest='tracename', default='lzload.trace', help='use either lzload.trace or lztrace.trace')

(options, args) = parser.parse_args()

files = glob.glob("{}/{}.*".format(options.working_dir, options.tracename))
used = set()
for fn in files:
    print("merging {}".format(fn))
    with open(fn, "r") as f:
        for l in f.readlines():
            used.add(l.strip())
    if not options.preserve:
        os.remove(fn)

with open("{}/{}".format(options.working_dir, options.tracename), "a") as f:
    sep = " " if options.tracename == "lzload.trace" else "\n"
    if len(used) > 0:
        for d in used:
            f.write(d + sep)
        f.write("\n")
    else:
        if options.tracename == "lzload.trace":
            f.write("nodep\n")
