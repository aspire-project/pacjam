#!/usr/bin/env python3

import subprocess
import os.path
import sys
import glob

from optparse import OptionParser 

import json

ARCH='x86_64-linux-gnu'

EXCLUDES=["libgcc1", "gcc-8-base", "<debconf-2.0>", "debconf"]

LDD_EXCLUDES=["ld-linux-x86-64.so.2", "libdl.so.2", "libpthread.so.0"]

options = {}

def exclude_symbol(exclude, libs):
    for e in exclude:
        for l in libs:
            if e in l:
                return True
    return False

def exclude_src(dep, excludes):
    for e in excludes:
        if dep in e:
            return True
    return False


class Lib:
    def __init__(self, soname, needed):
        self.soname = soname
        self.needed = needed
        self.symbols = []

    def add_symbol(self, symbol):
        self.symbols.append(symbol)

class Meta:
    def __init__(self,package_name,package_deb,has_symbols,shared_libs, binaries):
        self.package_name = package_name
        self.package_deb = package_deb
        self.has_symbols = has_symbols
        self.shared_libs = shared_libs
        self.binaries = binaries
        self.has_locale = False
        self.has_perlmodules = False
        self.has_man = False

    def add_lib(self, lib):
        if lib not in self.shared_libs:
            self.shared_libs.append(lib)

    def add_binary(self, bin):
        if bin not in self.binaries:
            self.binaries.append(bin)

def read_dependency_list(name):
    deps = {}
    with open(name, 'r') as f:
        for d in f.read().splitlines():
            deps[d] = True
    return deps

def soname_lib(libpath):
    soname = get_soname(libpath)
    if soname is not None:
        soname = soname.decode("utf-8")
    else:
        soname = trim_libname(libpath)
    return soname 

def trim_libname(libpath):
    return libpath.split("/")[-1]

def get_soname(path):
    objdump = subprocess.Popen(['objdump', '-p', path], stdout=subprocess.PIPE)
    out = subprocess.run(['grep','SONAME'], stdout=subprocess.PIPE, stdin=objdump.stdout)
    if len(out.stdout) == 0:
        return None
    return out.stdout.strip().split()[-1] 

def get_needed(path):
    objdump = subprocess.Popen(['objdump', '-p', path], stdout=subprocess.PIPE)
    out = subprocess.run(['grep','NEEDED'], stdout=subprocess.PIPE, stdin=objdump.stdout)
    if len(out.stdout) == 0:
        return []
    deps = []
    for l in out.stdout.decode("utf-8").splitlines():
        deps.append(l.split()[1])
    return deps 

def download_deps(deps):
    debs = {}

    for d in deps: 
        if exclude_src(d, EXCLUDES):
            continue 

        print('fetching ' + d)

        if os.path.exists(os.path.join(options.working_dir, d)):
            home = os.getcwd()
            os.chdir(os.path.join(options.working_dir, d))
            debs[d] = glob.glob(d + '*.deb')[0]
            os.chdir(home)
            continue
        
        try:
            out = subprocess.check_output(['apt-get', 'download', d], stderr=subprocess.STDOUT)
            deb = glob.glob(d + '*.deb')[0]
            debs[d] = deb
            os.rename(deb, options.working_dir + '/' + deb)
        except:
            print("No package found for " + d)

    return debs

def gather_libs(path):
    out = subprocess.run(['find',path, '-name', 'lib*.so*'], stdout=subprocess.PIPE)
    libs = []
    for l in out.stdout.splitlines():
        libs.append(l.decode('utf-8'))
    return libs

def gather_bins(path):
    out = subprocess.run(['find',path, '-perm', '-111', '-type', 'f'], stdout=subprocess.PIPE)
    bins = []
    for b in out.stdout.splitlines():
        bins.append(b.decode('utf-8'))
    return bins 

def has_perl(path):
    out = subprocess.run(['find',path, '-name', '*.pm'], stdout=subprocess.PIPE)
    libs = []
    return len(out.stdout.splitlines()) > 0

def has_locale(path):
    out = subprocess.run(['find',path, '-name', '*.mo'], stdout=subprocess.PIPE)
    libs = []
    return len(out.stdout.splitlines()) > 0 

def has_man(path):
    out = subprocess.run(['find',path, '-name', '*man*'], stdout=subprocess.PIPE)
    libs = []
    return len(out.stdout.splitlines()) > 0 

# This assumes we are in the current directory for an extracted debian package
def read_so(meta, libs):
    for l in meta.raw_libs:
        soname = soname_lib(l)
        if soname in libs:
            continue
        needed = [n for n in get_needed(l) if not exclude_src(n, LDD_EXCLUDES)]
        libs[soname] = Lib(soname, needed) 

# This assumes we are in the current directory for an extracted debian package
def read_binary(meta):
    bindirs = ["bin", "sbin", "usr/bin", "usr/sbin"]

    binaries = set()

    for b in bindirs:
        for (dirpath, dirnames, filenames) in os.walk(os.path.join("tmp",b)):
            for f in filenames:
                binaries.add(trim_libname(f))

    if len(binaries) == 0:
        # Sanity check
        findbins = gather_bins("tmp")
        if len(findbins) > 0:
            print("warning: find found executable files while manual search did not for package {}".format(meta.package_name))
            print(findbins)

        # For debugging  
        meta.has_perlmodules = has_perl("tmp")
        meta.has_locale = has_locale("tmp")
        meta.has_man = has_man("tmp")

    for b in binaries:
        meta.add_binary(b)

# This assumes we are in the current directory for an extracted debian package
def build_symbols(meta):
    added = set()
    with open("symbols", "w") as f:
        try:
            subprocess.check_call(['dpkg', '-x', meta.package_deb, 'tmp']) 
            libs = gather_libs("tmp")
            for l in libs:
                if os.path.islink(l):
                    continue
                n = soname_lib(l)
                if n in added:
                    continue
                subprocess.check_call(['dpkg-gensymbols', '-v0', '-p' + meta.package_name, '-e{}'.format(l), '-Osymbols-t'], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                with open("symbols-t") as f2:
                    f.write(f2.read())
                added.add(n)
                os.remove("symbols-t")
            meta.has_symbols = True
            meta.raw_libs = [l for l in libs if not os.path.islink(l)]
        except subprocess.CalledProcessError as err:
            print(err)
            print('failed to build symbols file for ' + meta.package_deb)

def extract_debs(debs):
    # Create some metadata about our little repository
    home = os.getcwd()
    metas = {}
    libs = {}

    for dep,deb in debs.items():
        debhome = os.path.join(options.working_dir,dep)

        if not os.path.exists(debhome):
            os.mkdir(debhome)
            os.rename(os.path.join(options.working_dir,deb),os.path.join(debhome,deb))
            os.chdir(debhome)

            print('Extracting ' + deb)
            out = subprocess.check_output(['ar', '-xv', deb])

            if os.path.exists("control.tar.xz"):
                out = subprocess.check_output(['tar', 'xf', 'control.tar.xz'])
            elif os.path.exists("control.tar.gz"):
                out = subprocess.check_output(['tar', '-xzf', 'control.tar.gz']) 
        else:
            os.chdir(debhome)

        # Test for symbol file
        if (os.path.exists('symbols')):
            os.remove('symbols')
        meta = Meta(dep, deb, False, [], [])
        build_symbols(meta)

        read_so(meta, libs)
        read_binary(meta)

        metas[deb] = meta

        os.chdir(home) 

    return metas, libs

def parse_symbols(meta,libs):
    # We'll point every symbol to its metadata for now
    # Build a true repo later

    with open(os.path.join(options.working_dir, meta.package_name, "symbols")) as f:
        current_lib = ""
        for l in f.readlines():
            if l[0] != " " and l[0] != "|" and l[0] != '*':
                current_lib = l.split()[0]
                meta.add_lib(current_lib)
                if current_lib not in libs:
                    print("Warning, lib {} not in lib table!".format(current_lib))
            else:
                toks = l.split()
                if toks[0] == "|" or toks[0] == "*":
                    pass
                else:
                    name = toks[0].split("@")[0]
                    libs[current_lib].add_symbol(name)

def save_packages(meta):
    with open(os.path.join(options.working_dir,'packages.txt'), 'w') as f:
        for k,m in metas.items():
            for l in m.shared_libs:
                f.write("{} {}\n".format(l, m.package_name)) 

def save_binaries(meta):
    with open(os.path.join(options.working_dir,'binaries.txt'), 'w') as f:
        for k,m in metas.items():
            for l in m.binaries:
                f.write("{} {}\n".format(l, m.package_name)) 

def save_extra(meta):
    with open(os.path.join(options.working_dir,'extra.txt'), 'w') as f:
        for k,m in metas.items():
            if len(m.shared_libs) > 0 or len(m.binaries) > 0:
                continue
            if m.has_perlmodules:
                f.write("{} {}\n".format(m.package_name, "perl-module"))
                continue
            if m.has_locale:
                f.write("{} {}\n".format(m.package_name, "locale"))
                continue 
            if m.has_man:
                f.write("{} {}\n".format(m.package_name, "man"))
                continue 

def save_libs(libs):
    meta_dir = os.path.join(options.working_dir, "meta")
    if not os.path.exists(meta_dir):
        os.mkdir(meta_dir) 

    with open(os.path.join(options.working_dir, "libraries.txt"), 'w') as f:
        for k,l in libs.items():
            f.write("{}\n".format(l.soname))

    for k,l in libs.items():
        with open(os.path.join(meta_dir, l.soname + ".libraries"), 'w') as f:
            for d in l.needed:
                f.write("{}\n".format(d)) 

def load_symbols(metas, libs):
    for k,m in metas.items():
        if m.has_symbols:
            parse_symbols(m, libs)

def save_symbols(libs):
    meta_dir = os.path.join(options.working_dir, "meta")
    if not os.path.exists(meta_dir):
        os.mkdir(meta_dir)
    for k,l in libs.items():
        with open(os.path.join(meta_dir, l.soname + ".symbols"), 'w') as f:
            for s in l.symbols:
                f.write("{} {}\n".format(l.soname, s))

def read_trace(path):
    deps = []
    with open(path, 'r') as f:
        # See if we have it
        for d in f.read().splitlines():
            deps.append(d)
    return deps

def read_needed(l):
    deps = []

    if '/' not in l:
        if os.path.exists(os.path.join(options.working_dir, "meta", l + ".libraries")):
            with open(os.path.join(options.working_dir, "meta", l + ".libraries"), 'r') as f:
                for d in f.read().splitlines():
                    deps.append(d)
    else:
        deps = [n for n in get_needed(l) if not exclude_src(n, LDD_EXCLUDES)]

    return deps 

def read_binaries(path):
    bmap = {}
    with open(path, 'r') as f:
        for l in f.read().splitlines():
            toks = l.split()
            package = toks[1]
            bin = toks[0]
            bmap[bin] = package
    return bmap


def produce_runtime_dep(bmap):
    print(options.binary)
    binary_needed = [n for n in get_needed(options.binary) if not exclude_src(n, LDD_EXCLUDES)]
    runtime_deps = set(binary_needed)
    if options.trace is not None:
        runtime_deps.update(set(read_trace(options.trace)))
    workset = runtime_deps.copy()
    analyzed = set()

    while len(workset) > 0:
        l = workset.pop()
        if l not in analyzed:
            more = set(read_needed(l))
            runtime_deps.update(more)
            for l2 in more:
                if l2 not in analyzed:
                    workset.add(l2)
            analyzed.add(l)

    runtime_deps2 = set()
    for l in runtime_deps:
        tl = trim_libname(l)
        if not os.path.exists(os.path.join(options.working_dir, "meta", tl + ".libraries")) and tl not in bmap:
            print("warning: {} not in symbol repository".format(tl))
            continue
        runtime_deps2.add(tl)            

    with open(options.outfile, "w") as f:
        f.write("{}\n".format(len(runtime_deps2)))
        for l in runtime_deps2:
            f.write("{}\n".format(l))

def produce_binary_trace(bmap):
    trace = set(read_trace(options.trace))

    with open("binary.trace", "a") as f:
        for t in trace:
            name = trim_libname(t)
            if name in bmap:
                f.write(name + " ")
        f.write("\n") 

def patch_symbols():
    if not os.path.exists(options.patch):
        print("{} does not exist".format(options.pathc))
        return
    tab = {}
    with open(options.patch, "r") as f:
        for line in f.readlines():
            tok = line.split()
            sym, lib = tok[0], tok[1]
            if lib not in tab:
                tab[lib] = []
            tab[lib].append(sym)
    for l,syms in tab.items():
        symrepo = os.path.join(options.working_dir, "meta", l + ".symbols")
        if not os.path.exists(symrepo):
            print("warning: no symbol repository for library {}".format(l))
            continue
        with open(symrepo, "a") as sf:
            for s in syms:
                sf.write("{} {}\n".format(l, s)) 

usage = "usage: %prog [options] dependency-list"
parser = OptionParser(usage=usage)
parser.add_option('-d', '--dir', dest='working_dir', default='symbol-out', help='use DIR as working output directory', metavar='DIR')
parser.add_option('-t', '--trace', dest='trace', default=None, help='supply lztrace file', metavar='LZTRACE-FILE')
parser.add_option('-b', '--bin', dest='binary', default=None, help='binary used to produce lztrace file', metavar='BINARY')
parser.add_option('-o', '--outfile', dest='outfile', default="runtime.txt", help='output file for runtime deps', metavar='PATH')
parser.add_option('-p', '--patch', dest='patch', default=None, help='patch symbols.txt from src repo onto symbol repo', metavar='PATH')

(options, args) = parser.parse_args()

if options.patch is not None:
    patch_symbols()
    sys.exit(0)

if options.binary is not None:
    bmap = read_binaries(os.path.join(options.working_dir, "binaries.txt"))

    produce_runtime_dep(bmap)
    produce_binary_trace(bmap)
    sys.exit(0)

if len(args) < 1:
    print("error: must supply dependency-list")
    parser.print_usage()
    sys.exit(1)

deps=read_dependency_list(args[0])
debs=download_deps(deps)
metas, libs = extract_debs(debs)

load_symbols(metas, libs)

save_libs(libs)
save_packages(metas)
save_binaries(metas)
save_extra(metas)
save_symbols(libs)
