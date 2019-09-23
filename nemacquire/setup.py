# -*- coding: utf-8 -*-
#!/usr/bin/env python2
#
# $Id: setup.py 1428 2018-04-11 20:07:01Z ram_raj $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.
#

"""
Installing opencv with XIMEA on Linux:

There is a dependency on the binaries from XIMEA, so first download and install:
https://www.ximea.com/support/wiki/apis/XIMEA_Linux_Software_Package
./install -cam_usb30

sudo apt-get install libgtk2.0-dev
sudo apt-get install pkg-config

Don't use opencv 3.1.0!!! There is a bug that tries to use 32bit ximea library e.g.:
/usr/bin/ld: cannot find -lxiapi32

cd opencv-3.2.0
mkdir build
cd build

cmake -D WITH_XIMEA=YES ..
make
sudo make install

"""

# Instructions to build a standalone Windows msi installer:
    # svnversion  # to check up-to-date (no M)
    # python setup.py bdist_msi 
    # http://cx-freeze.readthedocs.org/en/latest/distutils.html
    
    # Make sure path to Nemacquire msi from the previous step is correct in the Nemacquire_WIX_Burn_config.wxs
    # Install Wix Tools http://wixtoolset.org/releases/
    # Add Wix\bin path to system environment variables (or you would have to specify absolute paths for candle.exe and light.exe)
    # run 'candle Nemacquire_WIX_Burn_config.wxs -ext WiXBalExtension -ext WiXUtilExtension'
    # run 'light Nemacquire_WIX_Burn_config.wixobj -ext WiXBalExtension -ext WiXUtilExtension'
    # The final bundled exe is Nemacquire_WIX_Burn_config.exe. Rename to desired format
    # This exe includes installation files for dependencies such as bossa and xiapi in addition to nemacquire

# Instructions for Windows build machine setup:
    # Install python 2.7
    # pip install PySide==1.2.2  # because version 1.2.4 (on 64 bit) creates 'squashed graph' bug
    # pip install pyqtgraph==0.10.0 #build modifications are specific to this version
    # pip install pyserial
    # pip install svnversion
    # Navigate to nema_desktop_sw/common/packages
    # pip install numpy-1.12.1+mkl-cp27-cp27m-win_amd64.whl
    # pip install scipy-0.19.0-cp27-cp27m-win_amd64.whl
    # pip install cx_Freeze==4.3.4 # build modifications are specific to this version
    # Edit line 'finder.IncludePackage("scipy.lib")' to 'finder.IncludePackage("scipy._lib")'
    # in C:\Python27\Lib\site-packages\cx_Freeze\hooks.py 
    # opencv-3-1 with XIMEA support was obtained from: http://anki.xyz/opencv-3-1-with-ximea-support/
    #     this build was checked into the folder "64 bit" in case the website went away
    #     to setup build machine copy all files to PYTHON_INSTALL_FOLDER/Lib/site-packages except the ffmpeg dll
    #     install to the PYTHON_INSTALL_FOLDER     
    # Install xiapi and enable xiapipython option !
    # Add following insert to windist.py in cx_Freeze to make Windows Start Menu shortcuts
    # BEGIN INSERT
    # Add shortcut to main program menu folder (nemacquire shortcut appears in start menu and is not nested)
    #            if executable.shortcutDir is not "ProgramMenuFolder":
    #               msilib.add_data(self.db, "Shortcut",
    #                    [("S_APP_START_%s" % index, "ProgramMenuFolder",
    #                            executable.shortcutName, "TARGETDIR",
    #                            "[TARGETDIR]%s" % baseName, None, None, None,
    #                            None, None, None, None)])
    #END OF INSERT

# Instructions for OS X build machine setup:
    # /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
    # brew install cartr/qt4/qt (qt4 not supported by brew anymore)
    # xcode-select --install (To use pre-built brew python distribution this is needed)
        #otherwise if python is built from scratch, it may not work on other machines
        #and might throw "Illegal instruction 4" or similar errors
    # brew install python cmake
    # sudo python2.7 get-pip.py
    # sudo python2.7 ez_setup.py
    # sudo easy_install pip
    # sudo pip install pyserial
    # sudo pip install setuptools -U
    # sudo pip install wheel -U
    # sudo pip2.7 install wheel
    # pip install PySide==1.2.2
    # pip install pyqtgraph
    # pip install numpy==1.12.1
    # pip install scipy==0.19.0
    # pip install cx_Freeze==4.3.4
    # sudo python2 setup.py bdist_mac
    # cp macdist.py /usr/local/lib/python2.7/site-packages/cx_Freeze/
    # Install 'Packages' program


# all
    # pip install sounddevice
    
# Instructions to build a standalone OS X dmg installer:
    # svnversion  # to check up-to-date (no M)
    # python setup.py bdist_mac
    # http://cx-freeze.readthedocs.org/en/latest/distutils.html
    # Drag .app to Applications folder
    # Open Nemacquire-PKG.pkgproj and build a .pkg installer
    # with Ximea dependencies

# NemAcquire Build dependenies:
    # Python 2.7.11, PSF
    # PySide 1.2.2, LGPL
    # pyqtGraph 0.10.0, MIT
    # Qt 4.8.5, LGPL (Windows), Qt 4.8.7 LGPL (Mac)
    # numpy+mkl 1.12.1, BSD-New License (Windows), numpy 1.12.1, BSD (Mac)
    # scipy 0.19.0, BSD
    # cx_Freeze 4.3.4, PSF
    # svnversion 1.9.2 command-line tool must be installed, Apache
    # Mac OS X ONLY: 
        # must install xcode command line tools
    # Ximea C++ shared libraries, python library, and camera drivers (obtain from Ximea API installer)
    # opencv


# With no excludes, build size on Win64 was ~134mb
import pdb
import sys
import subprocess
import os
import platform
from time import localtime, strftime, sleep
from cx_Freeze import setup, Executable
import PySide
import pyqtgraph
import numpy
import PySide.QtCore
import cx_Freeze
import glob
from shutil import copy, rmtree
from subprocess import call


rmtree("build", ignore_errors=True)
rmtree("dist", ignore_errors=True)

sys.path.append('data')
sys.path.append('protocol')
sys.path.append('resources')
sys.path.append('ui')
sys.path.append('utility')

software_revision = subprocess.check_output(['svnversion'])
software_revision = software_revision.rstrip() # strip off newline

if (not software_revision.isdigit()) : # Reset version.py to latest svn version to prevent version mismatch
    print("reverting and updating svn to fix version.py")
    call(['svn','revert','version.py'])
    call(['svn','update','version.py'])
    sleep(2) #Allow user to process whats happening
    software_revision = subprocess.check_output(['svnversion'])
    software_revision = software_revision.rstrip() # strip off newline

svn = subprocess.check_output(['svnversion', '--version', '--quiet'])
svn = svn[:-2]
b = strftime("%Y-%m-%d %H:%M:%S", localtime())
c = platform.uname()

with open('version.py', 'w') as f:
    f.write('svnversion = "%s"\n' % software_revision)
    f.write('build_date = "%s"\n' % b)
    f.write('build_computer = %s\n' % str(c))
    s = sys.version # on OS X and Linux, this is multiline
    s = s.replace('\n', ' ')
    f.write('Python_version = "%s"\n' % s)
    f.write('PySide_version = "%s"\n' % PySide.__version__)
    f.write('pyqtgraph_version = "%s"\n' % pyqtgraph.__version__)
    f.write('Qt_version = "%s"\n' % PySide.QtCore.__version__)
    f.write('numpy_version = "%s"\n' % numpy.version.version)
    f.write('cx_Freeze_version = "%s"\n' % cx_Freeze.version)
    f.write('svn_version = "%s"\n' % svn)



mac_specific_files = [('external/xiArrOps.so','libs/x64/xiArrOps.so'),
                      ('external/_sounddevice_data/portaudio-binaries/libportaudio.dylib','_sounddevice_data/portaudio-binaries/libportaudio.dylib'),
                      ('arduino/bossac_osx','arduino/bossac_osx'),]

windows_specific_files = [('external/openh264-1.6.0-win64msvc.dll','openh264-1.6.0-win64msvc.dll'),
                          ('external/opencv_ffmpeg340_64.dll','opencv_ffmpeg340_64.dll'),
                          ('external/xiapi64.dll','libs/x64/xiapi64.dll'),
                          ('external/xiArrOps64.dll','libs/x64/xiArrOps64.dll'),
                          ('arduino/bossac.exe','arduino/bossac.exe'),
                          ('external/_sounddevice_data/portaudio-binaries/libportaudio64bit.dll','_sounddevice_data/portaudio-binaries/libportaudio64bit.dll'),]

common_files = ['NemAcquireUserGuide.pdf',
                ('../common/ui/dark_stylesheet.css','ui/dark_stylesheet.css'),
                ('arduino/ads129x_driver.ino.bin','arduino/ads129x_driver.ino.bin'),
                ('resources/shutter.wav','resources/shutter.wav'),
                ('external/_sounddevice_data/__init__.py','_sounddevice_data/__init__.py'),]

#include files specific to platform
if sys.platform.startswith('win32'):
    include_file_list = common_files + windows_specific_files

elif sys.platform.startswith('darwin'):
    include_file_list = common_files + mac_specific_files

build_exe_options = {

#    'include_files':['NemAcquireUserGuide.pdf', ('../common/ui/dark_stylesheet.css','ui/dark_stylesheet.css'),
#                     ('external/openh264-1.6.0-win64msvc.dll','openh264-1.6.0-win64msvc.dll'),
#                     ('external/opencv_ffmpeg340_64.dll','opencv_ffmpeg340_64.dll'),
#                     ('external/xiapi64.dll','libs/x64/xiapi64.dll'),
#                     ('external/xiArrOps64.dll','libs/x64/xiArrOps64.dll'),
#                     ('external/xiArrOps.so','libs/x64/xiArrOps.so'),
#                     ('arduino/ads129x_driver.ino.bin','arduino/ads129x_driver.ino.bin'),
#                     ('arduino/bossac','arduino/bossac'),
#                     ('arduino/bossac.exe','arduino/bossac.exe'),
#                     ('resources/shutter.wav','resources/shutter.wav'),
#                     ('external/_sounddevice_data/portaudio-binaries/libportaudio64bit.dll','_sounddevice_data/portaudio-binaries/libportaudio64bit.dll'),
#                     ('external/_sounddevice_data/portaudio-binaries/libportaudio.dylib','_sounddevice_data/portaudio-binaries/libportaudio.dylib'),
#                     ('external/_sounddevice_data/__init__.py','_sounddevice_data/__init__.py'),
#                     ],
#
    'include_files': include_file_list,
    'optimize':0,                                                                                                  
    'excludes':['collections.abc']} # to prevent collections.sys error on mac
    
#Upgrade code has to stay the SAME in all future releases of nemacquire for proper update functionality !!
#The uuid is generated from the uuidgen.exe tool in Windows SDK. Braces are added to show up right in the msi tables
bdist_msi_options = {'upgrade_code':'{dd2edf7f-6183-4857-b013-615610e39dc6}'}

base= None
if sys.platform == "win32":
    base = "Console"         # "Console" or "Win32GUI"

#For windows installers (exe constructed from WiX Burn), version attribute in setup determines installer behaviour in the following ways:
#1. If newer version, an upgrade is instantiated (Probably a major upgrade)
#2. If older version, installers informs that a newer version is already installed and doesn't allow installation
#3. If same version, ???

setup (
    name = "NemAcquire",
    version = "2.1."+str(software_revision[:4]),
    options = {"build_exe":build_exe_options , "bdist_msi":bdist_msi_options},
    executables = [Executable("nemacquire.py", 
                              base=base, 
                              icon="resources/nema_icon_transparent.ico", 
                              shortcutName="NemAcquire",
                              shortcutDir="DesktopFolder")])

#post-install for macs
if sys.platform == 'darwin':
    os.rename(os.path.join("build","NemAcquire-2.1."+str(software_revision[:4])+".app"),
              os.path.join("build","NemAcquire-2.1.app"))
    relative_build_path = os.path.join("build","NemAcquire-2.1.app")
    call(['python', 'osx_post_build.py','-f',relative_build_path]) #fixes path problems
    build_path = os.path.join(os.getcwd(),"build")
    app_path = glob.glob(build_path + "/*.app")[0]
    #call(['sudo','dropdmg',app_path]) #command line must be enabled for dropdmg
    #dmg_path = glob.glob(build_path+"/*.dmg")[0]
    #append_str = "/NemAcquire-2.1_" + software_revision + "_OSX_" + platform.mac_ver()[0] + ".dmg"
    #os.rename(dmg_path,build_path + append_str)

#post-install for windows
if sys.platform == "win32":
    #run 'candle Nemacquire_WIX_Burn_config.wxs -ext WiXBalExtension -ext WiXUtilExtension'
    
    call(['candle','Nemacquire_WIX_Burn_config.wxs', '-ext', 'WiXBalExtension', '-ext', 'WiXUtilExtension','-dnem_ver=2.1.'+str(software_revision[:4])])
    #run 'light Nemacquire_WIX_Burn_config.wixobj -ext WiXBalExtension -ext WiXUtilExtension'
    #execve replacing current python process with this call, for some reason python holds on to the msi file handle and so we need to exit it
    n = "NemAcquire-2.1_" + software_revision[:4] + "_" + c[0] + "_" + c[2] + ".exe"
    os.execve('C:\\Program Files (x86)\\WiX Toolset v3.11\\bin\\light.exe',['light','Nemacquire_WIX_Burn_config.wixobj', '-ext', 'WiXBalExtension', '-ext', 'WiXUtilExtension','-o',n],os.environ)
