from serial import serial_for_url
import serial.tools.list_ports
import time
import subprocess
import sys
import os
import re

def _bossac_call(port):
    device_name = None
    if sys.platform.startswith('linux'):
        executable_name = 'bossac'
        device_name = re.split("/",port.device)[-1]
    elif sys.platform.startswith('win32'):
        executable_name = 'bossac.exe'
        device_name = port.device
    elif sys.platform.startswith('darwin'):
        # "--port=cu.usbmodem1421",#+self.p.split('/')[-1],
        executable_name = 'bossac_osx'
        device_name = re.split("/",port.device)[-1]
    else:
        raise EnvironmentError
    base = os.path.dirname(sys.argv[0])
    executable_fullpath = os.path.join(base, 'arduino', executable_name)
    datafile_fullpath = os.path.join(base, 'arduino', 'ads129x_driver.ino.bin')

    cmd = [executable_fullpath,
           "-i",
           "--port="+device_name,
           "-U","true",
           "-e",
           "-w",
           "-v",
           "-b",
           datafile_fullpath,       
           "-R"]

    print subprocess.list2cmdline(cmd)
    print subprocess.check_output(cmd)

def detect_arduino_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if not hasattr(p, "pid"):
            continue # not a usb port
        if p.pid == 0x6124:
            print "arduino detected in programming mode"
            _bossac_call(p)
            time.sleep(1) # wait a second for arduino to reboot
        elif p.pid == 0x003E:
            print "arduino detected in normal mode"
            return p
    return None

def program_amp_firmware(port):
    # put adruino into programming mode
    s = serial_for_url(port.device, baudrate=1200,timeout = 1)
    s.close()
    time.sleep(1)
    # arduino is now in programming mode so the next time
    # detect_arduino_port() is called it will reprogram
    
if __name__ == "__main__":
    # to test move to same dir as nemacquire
    port = detect_arduino_port()
    assert(port.pid == 0x003E)
    program_amp_firmware(port)
    port = detect_arduino_port()
    assert(port == None)
    port = detect_arduino_port()
    assert(port.pid == 0x003E)
