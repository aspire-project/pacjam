# Overview

Repository is a suite of tools for manipulating debian packages. At a high level, dep-find generates a dependency list for use with dep-symbol and dep-src. 

# dep-find

This tool (written by Kihong) builds a dependency graph of the debian packages cached by apt. I have incluced the files ``direct.txt`` and ``transitive.txt`` which show the direct and transitive dependencies for debian packages respectively. 

For the time being, you can grab a dependency list for a package with:

```
./dep-find.py -p PACKAGE
```

which will create a file ``PACKAGE.dep`` in the current working directory. This can then be feed into ``dep-symbols``. For example, ``./dep-find.py -p wget`` will get the dependencies for ``wget`` and create ``wget.dep``.

You might also find it useful to search for dependencies and packages with ``apt``: ``apt-cache depends PACKAGE`` and ``apt-cache search PACKAGE``.  

# dep-symbol

Tool uses a dependency list for a package (built from dep-find.py) to download all dependencies and build a small repository of those dependency that contain symbol information.

## Install

All that is required for ``dep-symbol`` itself is a working python installation. Once you've pulled the repository, you can kickoff the ``test.sh`` script to make sure ``dep-symbol`` works. I've done my work on fir02, and have hardcoded the test script to use a copy of ``jq`` in my local installation directory (``/home/acanino/local``). If you do not run on fir02, you'll have to setup ``jq`` yourself and modify the test script. 

## Usage

### 1. Generate symbol repository for dependency list

```
mkdir symbol-out
./dep-symbol.py -d symbol-out wget.dep
```

### 2. Map list of libraries to packages 

```
./dep-symbol.py -d symbol-out -m list.txt
```

where list.txt is a lise of SONAME libraries one per line.

# lzload

lzload is a C library that does the actual shim / dummy library loading at runtime. Separately, clone https://github.com/petablox/lzload and build and install with cmake:

```
git@github.com:petablox/lzload.git
mkdir build && cd build
cmake .. -DCMAKE_C_COMPILER=/path/to/clang 
make
sudo make install
```


# dep-src

## Install

Run setup.sh to install dependencies and place the necessary make/dpkg-buildflags files on the system (this will require root). This will also setup a local symbol repository for lzload to use at runtime at $HOME/var/symbol-out.

## Usage

### 1. Building a dependency list

dep-src downloads and builds debian source packages from a dependency list. 

```
./dep-find.py -p wget
mkdir src-out
./dep-src.py -d src-out wget.dep
```

# End-to-End System Useage

### 1. Generate symbol repository

Generate a symbol repository for lzload to use to help find the correct symbol / library mapping at runtime: 

```
./dep-symbol.py -d $HOME/var/symbol-out wget.dep
```

This will produce a number of important files:

* packages.txt : map of shared libraries found in the repository to their packages

* binaries.txt : map of binaries found in the repository to their packages

* meta/ : directory containing symbol and dependency information for each library

  * meta/libz.so.SONAME.symbols contains all public symbols for libz
  
  * meta/libz.so.SONAME.symbols contains all of libz library dependencies 

### 2. Generate source repository

Generate a source repository for use with lzload:. 

```
mkdir src-out
./dep-src.py -d src-out wget.dep
```

This will produce a number of important directories and files:

* src-out/lib : contains all of the successfully erased shared libraries

* src-out/mod-lib : contains all original libraries instrumented with special functions to handle variadic function if present in the original library

* src-out/symbols.txt : contains the instrumented variadic functions for all libraries in mod-lib. This will need to be patched to the symbol repository in the next step.

* src-out/wget.dep.stat : contains status information about the build

### 3. Patch symbol repository with the source modified libraries

```
./dep-symbol.py -d $HOME/var/symbol-out -p src-out/symbols.txt
```

### 4. Check symbol repository against the source repository

Perform the following check to measure the matchup between symbol repository and the source repository:

```
./dep-src -d src-out -c $HOME/var/symbol-out wget.dep
```

You should see output similar to the following (with different numbers):

```
=========================================================
Total dependencies: 92
Packages with libraries 56
Packages with binaries 16
Reachable packages (upper bound) 70
Packages without libraries or binaries 17
Missing packages 5
Observable packages 61
Observable libraries 47
=========================================================
[UNOBSERVABLE]: libzstd1 unobservable: excluded from build
[UNERASED LIBRARIES]: library libzstd.so.1 from package libzstd1 not erased
...
=========================================================
dumped full details on all dependencies to details.csv
```

Packages that are _reachable_ either contains .so libraries or executable binaries that would be installed to /bin, /sbin, /usr/bin, /usr/sbin) and packages that are _observable_ are ones that our system can observe either because it has binaries or successfully erased libraries.  I do not discriminate packages that we exclude during build; instead, I will report this in details.csv file. This has the nice side effect that we now have complete information about whether packages are excluded, or build, or are missing etc:

```
package,type,reachable,observable,erased,excluded,unerased
libgpg-error-l10n,misc,False,False,False,False,0
```

### 4. Use lztrace to pre-run for lzload

```
LD_PRELOAD=/usr/local/lib/liblztrace.so wget google.com
```

This will produce several lztrace.trace files that help us create an upper bound on the libraries that should be loaded by lzload at runtime.

### 5. Generate runtime information with dep-symbols

First, execute fold.py to merge the lztrace.trace file information into one file:
```
scripts/fold.py -d . -t lztrace.trace
```

Then, run dep-symbol to build a list of runtime dependencies for all observed binaries and dlopened libraries:

```
dep-symbol.py -d $HOME/var/symbol-out -b `which wget` -t lztrace.trace
```

This will produce a number of important files:

* runtime.txt : contains the set of libraries for lzload to load symbol information at runtime

* binary.trace : contains the binaries used during the lztrace run (can be merged with lzload library usage)

* dlopen.package.trace : contains the packages that we dynamically loaded via dlopen (can be merged with lzload library usage)

* dlopen.library.trace : contains the libraries that we dynamically loaded via dlopen (can be merged with lzload library usage)

### 6. Run lzload

There is a script at the top level, wget.sh, that demonstrates what environment variables need to be set to hook into the dummy libs. We need to set three environment variables: LZLOAD_LIB, LZ_LIBRARY_PATH, and LD_LIBRARY_PATH.

LZLOAD_LIB simple points to the runtime.txt generated in the step above. LZ_LIBRARY_PATH points to the actual path of the real libraries that lzload should load on a fault. LD_LIBRARY_PATH must point to the dummy libraries.

### 7. Extra

Because some libraries cause execution issues, we sometimes remove them from lib and mod-lib. Our spreadsheet contains a list of libraries that should be pulled out of the lib and mod-lib directories.
