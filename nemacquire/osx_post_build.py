# -*- coding: utf-8 -*-
# $Id: osx_post_build.py 1417 2018-03-15 23:25:05Z ram_raj $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.

# ln /usr/local/lib/python2.7/site-packages/PySide/libpyside-python2.7.1.2.dylib /usr/local/Cellar/python/2.7.11/Frameworks/Python.framework/Versions/2.7/lib
# ln /usr/local/lib/python2.7/site-packages/PySide/libshiboken-python2.7.1.2.dylib /usr/local/Cellar/python/2.7.11/Frameworks/Python.framework/Versions/2.7/lib

from subprocess import call
import os
import glob
from shutil import copy
import argparse

l1 = ['PySide.QtCore.so',
     'PySide.QtGui.so',
     'PySide.QtNetwork.so',
     'PySide.QtOpenGL.so',
     'PySide.QtTest.so',
     'PySide.QtSvg.so']

parser = argparse.ArgumentParser()
parser.add_argument('-f', default = "")
args = parser.parse_args()
if args.f is "":
    raise ValueError("Supply filename in commandline !")

r = os.path.join(args.f,'Contents/MacOS/')
print r
#r = 'build/NemAcquire-2.1.app/Contents/MacOS/'

for s in l1:
    p = r + s
    cmd = ['install_name_tool', '-change', '@rpath/libshiboken-python2.7.1.2.dylib', '@executable_path/libshiboken-python2.7.1.2.dylib',  p]
    call(cmd)
    cmd = ['install_name_tool', '-change', '@rpath/libpyside-python2.7.1.2.dylib', '@executable_path/libpyside-python2.7.1.2.dylib',  p]
    call(cmd)

p = r + 'PySide.shiboken.so'
cmd = ['install_name_tool', '-change', '@rpath/libshiboken-python2.7.1.2.dylib', '@executable_path/libshiboken-python2.7.1.2.dylib',  p]
call(cmd)

p = r + 'libpyside-python2.7.1.2.dylib'
cmd = ['install_name_tool', '-change', '@rpath/libshiboken-python2.7.1.2.dylib', '@executable_path/libshiboken-python2.7.1.2.dylib',  p]
call(cmd)

ld = ['scipy.special._ufuncs.so',
      'scipy.special.specfun.so',
      'scipy.linalg._fblas.so']

#rename dylib file paths in all scipy*so files for scipy 0.19.0
ld1 = glob.glob("./build/exe*/scipy*so")
ld1 = ld1 + glob.glob("./build/NemAcquire*/Contents/MacOS/scipy*so")

l2 = ['libgfortran.3.dylib',
      'libquadmath.0.dylib']
for d in ld1:
    for s in l2:
        cmd = ['install_name_tool','-change', '@loader_path/../.dylibs/'+s,'@executable_path/'+s, d]
        call(cmd)
        cmd = ['install_name_tool','-change', '@loader_path/../../../.dylibs/'+s,'@executable_path/'+s, d]
        call(cmd)
        cmd = ['install_name_tool','-change', '@loader_path/../../../../.dylibs/'+s,'@executable_path/'+s, d]
        call(cmd)

plist_path = os.path.join(os.getcwd(), args.f, "Contents", "Info.plist")
copy(os.path.join(os.getcwd(), "resources", "mac_icon.icns"), os.path.join(os.getcwd(),args.f,"Contents", "Resources"))

with open(plist_path, 'r+') as file:
    lines = file.readlines()
    i = 0
    for line in lines:
        i += 1
        if 'nemacquire' in line:
            lines.insert(i, "\t<key>CFBundleName</key>\n\t<string>NemAcquire</string>\n")
    file.truncate(0)
    file.seek(0)
    file.writelines(lines)
file.close() 

