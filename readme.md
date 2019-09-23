# requirments


[python 2.7](https://www.python.org/ftp/python/2.7.16/python-2.7.16.amd64.msi)


- Install xiapi from 'nemacquire/external/XIMEA_API_Installer.exe' and enable xiapipython option.
- Go through the following instructions to install the [xiapi for python](https://www.ximea.com/support/wiki/apis/Python_inst_win), step 4 is critical.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install dependencies.

```bash
pip install requirments.txt
```

Linux Dev Environment Setup
===========================

- 2018-08-10 Fresh install of Ubuntu 18.04
```bash
sudo apt-get install python python-pip # Install Python2.7 and pip
sudo apt-get install python python-pip cmake qmake build-essential
sudo apt-get install subversion
sudo apt-get install python-pyside
sudo apt-get install libportaudio2

# Install XIMEA - for using camera
wget https://www.ximea.com/downloads/recent/XIMEA_Linux_SP.tgz
tar xzf XIMEA_Linux_SP.tgz
cd package
./install
# Give user access to usb camera
sudo gpasswd -a $USER_NAME plugdev
# Increase USB buffer memory 
# Ubuntu default usb buffer memory is 16MB, it may be too small - https://www.ximea.com/support/wiki/apis/Linux_USB30_Support#Increase-the-USB-Buffer-Size-in-Linux
# This may have led to a 'malloc(): memory corruption' issue after 'xiAPI: CalculateResources : Context 54DCB000 ID 10874551 m_maxBytes=1024 m_maxBufferSize=1048576'
# sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb >/dev/null <<<0 # This is XIMEA's solution but did not work
# Solution adapted from https://importgeek.wordpress.com/2017/02/26/increase-usbfs-memory-limit-in-ubuntu/
sudo sh -c 'echo 1000 > /sys/module/usbcore/parameters/usbfs_memory_mb'
#To confirm that you have successfully updated the memory limit, run the following command:
cat /sys/module/usbcore/parameters/usbfs_memory_mb

# Permanent enable user to access serial port - for connecting Arduino
sudo usermod -a -G dialout $USER_NAME 

# To install OpenCV builded with ffmpeg
sudo apt-get update
sudo apt-get upgrade
## Remove any previous installations of x264</h3>
sudo apt-get remove x264 libx264-dev
## Install dependencies 
sudo apt-get install build-essential checkinstall cmake pkg-config yasm
sudo apt-get install git gfortran
sudo apt-get install libjpeg8-dev libjasper-dev libpng12-dev
sudo apt-get install libtiff5-dev
sudo apt-get install libavcodec-dev libavformat-dev libswscale-dev libdc1394-22-dev
sudo apt-get install libxine2-dev libv4l-dev
sudo apt-get install libgstreamer0.10-dev libgstreamer-plugins-base0.10-dev
sudo apt-get install qt5-default libgtk2.0-dev libtbb-dev
sudo apt-get install libatlas-base-dev
sudo apt-get install libfaac-dev libmp3lame-dev libtheora-dev
sudo apt-get install libvorbis-dev libxvidcore-dev
sudo apt-get install libopencore-amrnb-dev libopencore-amrwb-dev
sudo apt-get install x264 v4l-utils
## Download OpenCV source code from https://opencv.org/releases.html and unpack. go into the unpack directory and run
mkdir build
cd build/
cmake -D WITH_FFMPEG=ON ..
make
sudo make install
```

XIMEA LINUX INSTRUCTIONS
------------------------
- Installing opencv with XIMEA on Linux:
    - There is a dependency on the binaries from XIMEA, so first download and install:
    - https://www.ximea.com/support/wiki/apis/XIMEA_Linux_Software_Package
    - `./install -cam_usb30`
    - `sudo apt-get install libgtk2.0-dev`
    - `sudo apt-get install pkg-config`

    - Don't use opencv 3.1.0!!! There is a bug that tries to use 32bit ximea library e.g.: /usr/bin/ld: cannot find -lxiapi32

    - `cd opencv-3.2.0`
    - `mkdir build`
    - `cd build`

    - `cmake -D WITH_XIMEA=YES ..`
    - `make`
    - `sudo make install`

- Finding the version of python ximea api in use
`python -c 'from ximea import xiapi; cam = xiapi.Camera(); print(cam.get_api_version())'`

