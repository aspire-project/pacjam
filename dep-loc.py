#!/usr/bin/env python3

import json
import os, os.path
import sys
from os import walk
import shutil
import logging
import subprocess

from optparse import OptionParser 

log = logging.getLogger('dep-loc')

file_handler = logging.FileHandler('log_deploc.txt')
file_handler.setLevel(logging.DEBUG)
log.addHandler(file_handler)

console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setLevel(logging.INFO)
log.addHandler(console_handler)

log.setLevel(logging.DEBUG)

def load_deplist(depfile):
    deplist = []
    with open(depfile, 'rt') as infile:
        for line in infile:
            line = line.strip()
            if len(line) > 0:
                deplist.append(line)

    return deplist


def enumerate_source_files(packagedir):
    args=['find', packagedir, '-iregex', '.*\\.\\(c\\|cc\\|cxx\\|h\\|hh\\|hxx\\|hpp\\)']
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    output, error = proc.communicate()

    if proc.returncode != 0:
        log.error("Error on %s" % (" ".join(args),))
        log.error(error.decode())
        sys.exit(-1)

    if len(output) == 0:
        log.debug("No C/C++ source files")
        return []
    
    srcfiles = output.decode().strip().split('\n')
    log.debug("Source-files: %s" % ("\n".join(srcfiles),))

    return srcfiles


def loc_of_sources_actual(srcfiles):
    if len(srcfiles) == 0:
        return 0

    args=['wc', '-l']
    args.extend(srcfiles)
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    output, error = proc.communicate()

    if proc.returncode != 0:
        log.error("Error on %s" % (" ".join(args),))
        log.error(error.decode())
        sys.exit(-1)

    if len(output) == 0:
        return 0

    lines = output.decode().strip().split('\n')
    log.debug("wc -l result:")
    log.debug("\n".join(lines))
    
    return int(lines[-1].split()[0].strip())


def loc_of_sources(srcfiles):
    if len(srcfiles) <= 100:
        return loc_of_sources_actual(srcfiles)

    count = (len(srcfiles) + 99) // 100
    total_loc = 0
    for idx in range(count):
        sub_srcfiles = srcfiles[idx*100:(idx+1)*100]
        total_loc += loc_of_sources_actual(sub_srcfiles)

    return total_loc


actual_packages = {}
def loc_of_package(basedir, package):
    global actual_packages

    packagedir="%s/%s" % (basedir, package)
    log.debug("Package-dir: %s" % (packagedir,))

    if os.path.exists(packagedir):
        try:
            base_dir, dir_list, _ = next(walk(packagedir))
            if len(dir_list) == 1:
                src_package = dir_list[0]
                log.info("    src-pkg: %s" % (src_package,))

                if src_package not in actual_packages:
                    actual_packages[src_package] = {
                            'packages': [package],
                            'lines-of-code': 0}

                    srcfiles = enumerate_source_files(packagedir)

                    loc = loc_of_sources(srcfiles)

                    log.info("    LoC: %d" % (loc,))
                    actual_packages[src_package]['lines-of-code'] = loc

                    return loc
                else:
                    actual_packages[src_package]['packages'].append(package)
                    log.info("    LoC: already processed")
                    return 0

        except StopIteration:
            pass

    log.info("    Not-exist")
    return -1


def loc_of_application(application):
    # retrive source code
    args = ['apt-get', 'source', application]
    pwd = os.getcwd()
    workdir = '/tmp/%s' % (application,)
    os.makedirs(workdir, exist_ok=True)
    os.chdir(workdir)
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    output, error = proc.communicate()
    os.chdir(pwd)

    if proc.returncode != 0:
        log.error("Error on apt-get source")
        log.error(error.decode())
        sys.exit(-1)

    loc = loc_of_package('/tmp', application)

    shutil.rmtree(workdir, ignore_errors=True)

    return loc

    
def calculate_loc(application, deplist, basedir, outfilename):
    global actual_packages

    # get LoC of main application first
    log.info("Main Package: %s" % (application,))
    total_loc = loc_of_application(application)

    for package in sorted(deplist):
        log.info("Package: %s" % (package,))
        loc = loc_of_package(basedir, package)
        if loc == -1:
            continue

        total_loc += loc

    refdata = {
            'application': application,
            'lines-of-code': total_loc,
            'source-packages': actual_packages
    }
    with open(outfilename, 'wt') as outfile:
        json.dump(refdata, outfile, indent=2)

    log.info("Total LoC: %d" % (total_loc,))


parser = OptionParser(usage="%s [options] main-application" % (sys.argv[0],))
parser.add_option('-d', '--base-dir', dest='basedir', default=None, help='set base-directory for searching packages')
parser.add_option('-D', '--dep-list', dest='deplist', default=None, help='give dependancy-list for the application, default=<main-application>.dep')
parser.add_option('-o', '--out-file', dest='outfile', default=None, help='set output-file [default=loc-<main-application>.json]')

(options, args) = parser.parse_args()
if options.basedir is None or len(args) != 1:
    parser.print_help()
    sys.exit(0)

application = args[0]

basedir = options.basedir
outfile = options.outfile if options.outfile is not None else "loc-%s.json" % (application,)
deplist = options.deplist if options.deplist is not None else "%s.dep" % (application,)

if not os.path.exists(deplist):
    log.error("Dependency list is not existing: %s" % (deplist,))
    sys.exit(-1)

if not os.path.exists(basedir):
    log.error("Base directory is not existing: %s" % (basedir,))
    sys.exit(-1)

dep_list = load_deplist(deplist)

calculate_loc(application, dep_list, basedir, outfile)

