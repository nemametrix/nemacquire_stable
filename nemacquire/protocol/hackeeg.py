# -*- coding: utf-8 -*-
# $Id: hackeeg.py 1428 2018-04-11 20:07:01Z ram_raj $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.
#

from multiprocessing import Process
from multiprocessing import log_to_stderr
from struct import unpack
import sys, time, datetime, base64
import traceback
from serial import serial_for_url
import serial.tools.list_ports
import time
from nema_log import log
from ard_uploader import detect_arduino_port, program_amp_firmware
import numpy as np
import logging

# channel can be 1 to 8
def get_channel_register_string(channel):
    assert (channel >= 1 and channel <=8), channel
    if channel < 6:
        channel_string = "0" + str(channel+4)
    elif channel == 6:
        channel_string = "0A"
    elif channel == 7:
        channel_string = "0B"
    elif channel == 8:
        channel_string = "0C"
    return channel_string


def get_input_command_string(channel, code):
    cmd = "wreg " + get_channel_register_string(channel) + " " + code
    return cmd

def get_input_normal_command_string(channel):
    return get_input_command_string(channel, "50")

def get_input_square_wave_command_string(channel):
    return get_input_command_string(channel, "55")

# every command we send has two lines of response
# except sdatac with will continuously respond

def _patient_readline(ser,logger):

    line = ser.readline()
    attempts = 0
    max_attempts = 3
    while not line.endswith('\n') and attempts <= max_attempts:
        logger.info("last readline timedout, readline again")
        line = line + ser.readline()
        attempts += 1
    return line

def _send(ser, command,logger):
    info_to_log = "command: " + command
    ser.write(bytes(command +'\n'))

    b1 = _patient_readline(ser,logger)
    info_to_log += " b1: " + b1.rstrip()
    if b1[0:6] != "200 Ok":
        log("\nunexpected: " + b1.strip())
    b2 = _patient_readline(ser,logger)
    info_to_log += " b2: " + b2.rstrip()
    logger.info(info_to_log)
    return b2

def send_framerate_cmd(cmd_queue,div):
    framerate_cmd_str = 'framerate ' + str(div)
    cmd_queue.put(framerate_cmd_str)

# keep reading until no more
# (could not get flush to work)
def clear_input_buffer(ser):
    s = ser.readline()
    while s:
        # log("Clearing input buffer: " + s)
        s = ser.readline()

class AmpStatus(object):

    def __init__(self, connected, version_string, sample_rate_hz,
            range_mVpp,updating = False,failed_connection_attempt = False):
        self.connected = connected
        self.firmware_version = version_string
        self.sample_rate_hz = sample_rate_hz
        self.range_mVpp = range_mVpp
        self.updating = updating
        self.failed_connection_attempt = failed_connection_attempt


class ReceiveDataWorker(Process):

    def __init__(self, channel, samples_queue, status_queue, command_queue):
        Process.__init__(self)
        self.channel_register_string = get_channel_register_string(channel)
        self.buf = samples_queue
        self.status_queue = status_queue
        self.command_queue = command_queue
        self.s = None # serial object
        self.number_of_channels = 8 
        self.number_of_samples = 6
        #Has to be equal to number of channels output by arduino
        #and in acquired_data.py        

    def _connect_to_amp(self, port):
        self.s = serial_for_url(port.device, baudrate=115200, timeout=1)
        self.logger.info("using device: %s" % self.s.portstr)
        for i in range(3): # send multiple because sometimes garbage on first open
            # stop continuous data
            b1 = _send(self.s, "sdatac",self.logger)
            clear_input_buffer(self.s)

        # ensure amp is at correct version
        version_string = _send(self.s, "version", self.logger).strip()
        if version_string != "v18.01.25" :
            self.status_queue.put(AmpStatus(False, version_string, 500, 750,updating = True))
            self.s.close()
            program_amp_firmware(port)
            return False

        self.status_queue.put(AmpStatus(False,version_string, 500, 750, updating=False))
        log("Amp connected. Firmware version: " + version_string)
        self.status_queue.put(AmpStatus(True, version_string, 500, 750))
        return True

    def _disconnect_amp(self) :
        self.s.close()
        self.logger.info("disconnecting amp")

    def _initialize_amp(self):
        
        # if version_string != "v17.10.25" :

            # self.status_queue.put(AmpStatus(False, version_string, 500,
                # 750,updating = True))
            # self._disconnect_amp()
            # ard_uploader = ArdUploader()
            # ard_uploader.run()
            # self.status_queue.put(AmpStatus(False,version_string,500,750,
                # updating=False))
            # return False
            ##TODO send signal to nemacquire to say amp is updating


        #_send(self.s, "wreg 01 95",self.logger) # 500Hz sampling
        _send(self.s, "wreg 01 B5", self.logger) # 500 Hz with CLK_EN set to 1
        _send(self.s, "wreg 03 EC", self.logger) # power on ref buf and BIAS     
        #_send(self.s, "wreg 03 60",self.logger)#power off refbuf and bias buffer

        code = " 50" # electrodes normal to start
        
        for channel in range(1,9):
            cmd = "wreg " + get_channel_register_string(channel) + code
            _send(self.s, cmd,self.logger)
        _send(self.s, "wreg 0D 00", self.logger) # bias_sensp
        _send(self.s, "wreg 0E 00", self.logger) # bias_sensn
        
        #Sleep to allow time for main process to send framerate_div command
        #framerate_div is not stored in this process 
        time.sleep(0.5)
        if not self.command_queue.empty():
            command_string = self.command_queue.get()
            _send(self.s, command_string, self.logger)
            
            
            
        _send(self.s, "rdatac", self.logger)
        
        
        return True        

    def run(self):
        self.logger = log_to_stderr()
        self.logger.setLevel(logging.DEBUG)
        time_before_commands_are_processed = 2
        start_time = None
        connected = False
        while 1:
            if connected == True:
                self.status_queue.put(AmpStatus(False, "", None, None))
                connected = False
            n = 0
            # wait a second before trying again after any exception or not finding port
            # sometimes on Windows the device is detected before it can read from
            # in that case, it used to "recieved nothing"
            time.sleep(0.5)
            p = None
            try: 
                p = detect_arduino_port()
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                t = traceback.format_exception(exc_type, exc_value, exc_traceback)
                print t
                #Let nemacquire know that something went wrong
                self.status_queue.put(AmpStatus(False, "", None, None, False, True))
            time.sleep(0.5)
            start_time = None
            if p:
                try:
                    if self._connect_to_amp(p) == False:
                        continue
                    if not self._initialize_amp():
                        log("Could not initialize amp")
                        continue
                    connected = True
                    prev_sample_number = None
                    samples_lost = 0
                    start_time = time.time()
                    while 1:
                        line = self.s.readline()
                        timestamp = time.time()
                        n += 1
                        if len(line) == 0:
                            log("Received nothing, diconnecting amp")
                
                            break # something went wrong - on Windows this can happen
                        # self.check_input_type()
                        if n == 5:
                            # send the keep alive every 5 * 50ms = 250ms to keep LED on
                            # can't send too fast or arduino will block
                            # there is no reply to this so no need for extra readline
                            self.s.write(bytes('ping\n'))
                            n = 0
                        if line.startswith("200"):
                            self.logger.info(': ' + line)
                        else:
                            try:
                                decoded = base64.b64decode(line)
                            except TypeError:
                                decoded = ""
                                log('TypeError in base64 decoding')
                            # check for commands to be issued
                            while not self.command_queue.empty():
                                #Don't process commands right after amp is initialized and defer them, on windows
                                #command responses can sometimes read in sample data resulting in a dropped data error
                                if time.time() < start_time + time_before_commands_are_processed:
                                    break
                                command_string = self.command_queue.get()
                                _send(self.s, command_string, logger =self.logger)
                            if len(decoded) != self.number_of_samples*(7+3*self.number_of_channels+1):
                                log("corrupt packet: %d, %s" % (len(decoded), line))
                                continue
                            values = []
                            exposure_starts = []

                       
                            for i in range(self.number_of_samples):

                                
                                sample_multiplier =\
                                7+3*self.number_of_channels+1
                                sample_number = unpack(
                                        '!I',
                                        decoded[i*sample_multiplier:i*sample_multiplier+4])[0]
                                status_bits = unpack(
                                        'B',
                                         decoded[i*sample_multiplier+4])[0]
                                if status_bits != 0xC0:
                                    #log("Status bits:" + hex(status_bits))
                                    continue
                                if prev_sample_number and sample_number != prev_sample_number + 1:
                                    log("dropped data: %d %d" % (prev_sample_number, sample_number))
                                    samples_lost += sample_number - prev_sample_number
                                    self.buf.put(samples_lost) # one value
                                prev_sample_number = sample_number
                                # the '\0' is because python cannot unpack a 24-bit type
                                channel_values = []
                                for channel_num in range(1,9):
                                    
                                    sample_offset = 7+3*(channel_num-1)
                                    value = unpack('!i',decoded[
                                        i*sample_multiplier+sample_offset:
                                        i*sample_multiplier+sample_offset+3]+'\0')[0]

                                    value = value >> 8 # convert from 32 bit back to 24 bit
                                    value = value * .750 / 2**24  # convert to V
                                    channel_values.append(value)
                                values.append(channel_values)
                                sync_offset = 7+3*(self.number_of_channels)
                                exposure_start =\
                                unpack('!i',decoded[
                                    i*sample_multiplier+sync_offset:
                                    i*sample_multiplier+sync_offset+1]+'\0\0\0')[0]

                                exposure_start = exposure_start >> 24
                                exposure_starts.append(exposure_start)
                            self.buf.put((values,timestamp,exposure_starts)) # 24 values
                except:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    t = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    for l in t:
                        self.logger.error(l)
                        pass
                    if self.s:
                        log("Closing connection to amp")
                        self.s.close()
                    self.s = None


        if hasattr(self, "s"):
            try:
                if self.s:
                    self.s.close()
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                t = traceback.format_exception(exc_type, exc_value, exc_traceback)
                for l in t:
                    log(l)
