# -*- coding: utf-8 -*-
# $Id: test_wave_generator.py 1406 2018-03-12 23:22:04Z ram_raj $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.
#

import numpy as np
import PySide
import pyqtgraph as pg

class TestWaveGenerator():
    # units are in volts, default is +/-75uV 5Hz Sine with +/-10uV 60Hz noise, 500Hz sampling
    def __init__(self, freq1=5, amp1=0.000075, freq2=60, amp2=0.000010,
                        sample_rate=500,channels=8):
        # generate reference waveform, 
        self.ts = 1.0/sample_rate               # sampling interval (defult every 2 ms)
        self.t = np.arange(0,300,self.ts)       # create a 300 second time vector 
        offset = -0.00004
        self.reference_wave = offset + \
                              (amp1 * np.sin(2*np.pi*freq1*self.t)) + \
                              (amp2 * np.sin(2*np.pi*freq2*self.t))
        #self.reference_wave = self.offset + \
        #                      (0.000075 * np.sin(2*np.pi*5*self.t)) + \
        #                      (0.000020 * np.sin(2*np.pi*60*self.t)) + \
        #                      (0.003000 * np.sin(2*np.pi*125*self.t))
        self.ref_index = 0
        self.batch_size = 20
        self.channels = channels
        # values must be a values x n array, i.e. from eight channel amp values x n
        self.values = np.reshape(np.array([]), (-1,self.channels))
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        
    def update(self):
        # first get batch size samples
        if self.ref_index + self.batch_size >= len(self.reference_wave):
            self.ref_index = 0
        r = self.reference_wave[self.ref_index:self.ref_index + self.batch_size]
        # fixme: if len(ref wave) % batch_size != 0, then we loose some data, causing slight discontinuity
        self.ref_index += self.batch_size

        # next update values with new data
        new_values = np.tile(np.reshape(r,(-1,1)),self.channels)
        self.values = np.concatenate((self.values,new_values))
        
    def get_values(self):
        t = self.values
        self.values = np.reshape(np.array([]), (-1,self.channels))
        return t

    # start the QTimer
    def start(self):
        self.timer.start(self.ts * self.batch_size * 1000)
        self.connected = True

    def stop(self):
        self.timer.stop()
        self.connected = False

