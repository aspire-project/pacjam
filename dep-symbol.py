#!/usr/bin/env python3

import subprocess
import os.path
import sys
import glob

from optparse import OptionParser 

import json

ARCH='x86_64-linux-gnu'
working_dir = ""

EXCLUDES=["libc6", "libgcc1", "gcc-8-base", "<debconf-2.0>", "debconf"]

LDD_EXCLUDES=["libc.so.6", "ld-linux-x86-64.so.2"]

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
    def __init__(self,package_name,package_deb,has_symbols,shared_libs):
        self.package_name = package_name
        self.package_deb = package_deb
        self.has_symbols = has_symbols
        self.shared_libs = shared_libs

    def add_lib(self, lib):
        if lib not in self.shared_libs:
            self.shared_libs.append(lib)

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

        if os.path.exists(os.path.join(working_dir, d)):
            home = os.getcwd()
            os.chdir(os.path.join(working_dir, d))
            debs[d] = glob.glob(d + '*.deb')[0]
            os.chdir(home)
            continue
        
        try:
            out = subprocess.check_output(['apt-get', 'download', d], stderr=subprocess.STDOUT)
            deb = glob.glob(d + '*.deb')[0]
            debs[d] = deb
            os.rename(deb, working_dir + '/' + deb)
        except:
            print("No package found for " + d)

    return debs

def gather_libs(path):
    out = subprocess.run(['find',path, '-name', 'lib*.so*'], stdout=subprocess.PIPE)
    libs = []
    for l in out.stdout.splitlines():
        libs.append(l.decode('utf-8'))
    return libs

def read_so(meta, libs):
    for l in meta.raw_libs:
        soname = soname_lib(l)
        if soname in libs:
            continue
        needed = [n for n in get_needed(l) if not exclude_src(n, LDD_EXCLUDES)]
        libs[soname] = Lib(soname, needed) 

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
        debhome = os.path.join(working_dir,dep)

        if not os.path.exists(debhome):
            os.mkdir(debhome)
            os.rename(os.path.join(working_dir,deb),os.path.join(debhome,deb))
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
        meta = Meta(dep, deb, False, [])
        build_symbols(meta)

        read_so(meta, libs)

        metas[deb] = meta

        os.chdir(home) 

    return metas, libs

def parse_symbols(meta,libs):
    # We'll point every symbol to its metadata for now
    # Build a true repo later

    with open(os.path.join(working_dir, meta.package_name, "symbols")) as f:
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
    with open(os.path.join(working_dir,'packages.txt'), 'w') as f:
        for k,m in metas.items():
            for l in m.shared_libs:
                f.write("{} {}\n".format(l, m.package_name)) 

def save_libs(libs):
    with open(os.path.join(working_dir,'libraries.txt'), 'w') as f:
        for k,l in libs.items():
            for d in l.needed:
                f.write("{} {}\n".format(l.soname, d)) 

def load_symbols(metas, libs):
    for k,m in metas.items():
        if m.has_symbols:
            parse_symbols(m, libs)

def save_symbols(libs):
    symbols_dir = os.path.join(working_dir, "symbols")
    if not os.path.exists(symbols_dir):
        os.mkdir(symbols_dir)
    for k,l in libs.items():
        with open(os.path.join(symbols_dir, l.soname + ".symbols"), 'w') as f:
            for s in l.symbols:
                f.write("{} {}\n".format(l.soname, s))

def load_trace(name):
    calls = []
    if os.path.exists(name):
        with open(name, 'r') as f:
            for line in f:
                try:
                    j = json.loads(line)
                    calls.append(j)
                except json.decoder.JSONDecodeError:
                    continue
    else:
        return {}

    return calls

def check_deps(metas,deps,symbols,calls):
    stats = {}
    for d in deps:
        stats[d] = None

    for c in calls:
        if c["indirect"]:
            continue
        fname = c["fnptr"][1:]
        sym = symbols.get(fname)
        if sym is not None:
            stats[sym.metas[0].package_name] = sym.libs[0]

    return stats

def dump_deps(stats,outfile):
        
    # Just for nice output
    used = []
    notused = []

    for d,t in stats.items():
        if t is not None:
            used.append({"package_name":d, "shared_lib":t})
        else:
            notused.append(d)

    print('Package has ' + str(len(stats)) + ' tracked dependencies')
    print('Using ' + str(len(used)) + ':')
    for d in used:
        print('\t' + d["package_name"] + ' ===> ' + d["shared_lib"])

    print('Not using ' + str(len(notused)) + ':')
    for d in notused:
        print('\t' + d)

    if outfile is not None:
        j = {}
        j["used"] = used
        j["notused"] = notused

        with open(outfile, 'w') as f:
            json.dump(j,f,indent=2)

usage = "usage: %prog [options] dependency-list"
parser = OptionParser(usage=usage)
parser.add_option('-d', '--dir', dest='working_dir', default='symbol-out', help='use DIR as working output directory', metavar='DIR')
parser.add_option('-t', '--trace', dest='trace', help='load trace file DIR', metavar='TRACE')
parser.add_option('-o', '--outfile', dest='outfile', default=None, help='dump json data to OUTFILE for post-processing', metavar='OUTFILE')
parser.add_option('-s', '--src', action='store_true', default=None, help='download source packages from dep file', metavar='SRC')

(options, args) = parser.parse_args()

working_dir = options.working_dir

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
save_symbols(libs)

if options.trace is not None:
    calls = load_trace(options.trace)
    stats = check_deps(metas,deps,symbols,calls) 
    dump_deps(stats, options.outfile)
   








