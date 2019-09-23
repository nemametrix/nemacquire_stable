# -*- coding: utf-8 -*-
# $Id: filters.py 1197 2017-05-01 18:43:44Z carl_turner $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.
#

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi
# workaround for cx_freeze not including these scipy libaries:
import scipy.special._ufuncs_cxx
import scipy.integrate.vode
import scipy.integrate.lsoda
import scipy.sparse.csgraph._validation


"""
https://en.wikipedia.org/wiki/Low-pass_filter#math_I

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import freqz

plt.interactive(True)
plt.figure
plt.plot(t, wave, 'b', alpha=0.75)

delta_t = 1/500
t = np.arange(0,1,delta_t)
wave = 10 + (75 * np.sin(2*np.pi*5*t)) + (20 * np.sin(2*np.pi*60*t))

w, h = freqz(b, a)

"""

# for testing
def single_pole_low_pass(input_, cutoff_hz, delta_t):
    RC = 1/(2*np.pi*cutoff_hz)
    alpha = 2*np.pi*delta_t*cutoff_hz / (2*np.pi*delta_t*cutoff_hz + 1)
    print cutoff_hz, RC, alpha
    y = []
    for x in input_:
        if len(y) == 0:
            y.append(x)
        else:
            y.append(alpha*x + (1-alpha)*y[-1])
    return y

class RealTimeLfilter:
    # input: array of samples
    # returns: array of filtered samples 
    def next_sample(self, samples):
        if len(self.zi) == 0:
            # scale to uV range to avoid huge transient 
            self.zi = lfilter_zi(self.b, self.a) * samples[0] 
        y, zf = lfilter( self.b, self.a, samples, zi=self.zi)
        self.zi = zf
        return y

    def reset(self):
        self.zi = []

class Highpass(RealTimeLfilter):
    def __init__(self, cutoff_hz, sample_rate=500):
        nyq = 0.5 * sample_rate
        order = 2
        self.b, self.a = butter(order, cutoff_hz/nyq, btype='high', analog=False)
        self.reset()

class Notch(RealTimeLfilter):
    def __init__(self, corners_hz, sample_rate=500, bandpass=False):
        nyq = 0.5 * sample_rate
        order = 2
        c1 = corners_hz[0]/nyq
        c2 = corners_hz[1]/nyq
        if c2 > 1:
            # this can be the case in removing the 2nd stim harmonic which is right at 250 Hz
            print "Creating filter right up to nyquist:", nyq
            c2 = 1
        if bandpass:
            self.b, self.a = butter(order, (c1, c2), btype='bandpass', analog=False)
        else:
            self.b, self.a = butter(order, (c1, c2), btype='bandstop', analog=False)
        self.reset()

class RClowpass(RealTimeLfilter):
    def __init__(self, cutoff_hz, sample_rate=500):
        # https://en.wikipedia.org/wiki/Low-pass_filter#math_I
        alpha = 2*np.pi*delta_t*cutoff_hz / (2*np.pi*delta_t*cutoff_hz + 1)
        # not sure exactly why the coefficients are this but it seems to work out
        # https://www.mathworks.com/help/signal/ug/filter-implementation-and-analysis.html
        # http://www.earlevel.com/main/2012/12/15/a-one-pole-filter/
        # http://dsp.stackexchange.com/questions/6456/why-is-the-gain-of-my-iir-filter-positive
        # https://en.wikipedia.org/wiki/Infinite_impulse_response#Example
        # https://docs.scipy.org/doc/scipy-0.18.1/reference/generated/scipy.signal.lfilter.html
        # http://stackoverflow.com/questions/11812490/time-discrete-implementation-of-1st-order-rc-filter
        # https://www.dsprelated.com/showcode/199.php
        # http://stackoverflow.com/questions/1783633/matlab-apply-a-low-pass-or-high-pass-filter-to-an-array
        self.b = [alpha]           # not sure why not 1
        self.a = [1, -(1-alpha)]   # not sure why not [1, (1-alpha)]
        self.reset()

class RChighpass(RealTimeLfilter):
    # http://stackoverflow.com/questions/1783633/matlab-apply-a-low-pass-or-high-pass-filter-to-an-array
    def __init__(self, cutoff_hz, sample_rate=500):
        tau = 1 / (2*np.pi*cutoff_hz)
        a = 1./sample_rate/tau
        self.b = [1-a, a-1]
        self.a = [1, a-1]
        self.reset()
        
class RClowpass(RealTimeLfilter):
    # http://stackoverflow.com/questions/1783633/matlab-apply-a-low-pass-or-high-pass-filter-to-an-array
    def __init__(self, cutoff_hz, sample_rate=500):
        tau = 1 / (2*np.pi*cutoff_hz)
        a = 1./sample_rate/tau
        self.b = [1-a, a-1]
        self.a = [1, a-1]
        self.reset()

# Returns equivalent IIR coefficients for a first order analog RC filter
# 'high' or 'low'
def rc_filter_coefficients(cutoff_hz, filter_type, sample_rate=500):
    # https://www.dsprelated.com/showcode/199.php
    # "Conversion of Analog to Digital Transfer Functions" by C. Sidney Burrus, page 6.
    t  = 1. / sample_rate;
    w = cutoff_hz * 2 * np.pi # convert to angular freq
    alpha = 1 / (np.tan((w*t) / 2));
    b = [1, 0]
    a = [1, 0]
    if filter_type == 'high':
        b[0] = alpha / (1 + alpha);
        b[1] = -b[0]
        a[1] = (1 - alpha) / (1 + alpha);
    if filter_type == 'low':
        b[0] = 1 / (1 + alpha);
        b[1] = b[0];
        a[1] = (1 - alpha) / (1 + alpha);
    return b, a

# http://mpastell.com/2010/01/18/fir-with-scipy/
def plot_freq_phase_impulse_and_step_response(b,a=1,sample_rate=500):
    w,h = freqz(b,a)
    h_dB = 20 * np.log10 (abs(h))
    plt.subplot(111)
    plt.semilogx(w, h_dB)
    plt.margins(0, 0.1)
    plt.grid(which='both', axis='both')
    plt.ylabel('Magnitude (db)')
    plt.xlabel('Frequency (Hz)')
    plt.title('Frequency response')
    """
    plt.subplot(412)
    h_Phase = np.unwrap(np.arctan2(np.imag(h),np.real(h)))
    plt.plot(w*0.5*sample_rate/np.pi, h_Phase)
    plt.ylabel('Phase (Hz)')
    plt.xlabel('Frequency (Hz)')
    plt.title('Phase response')
    impulse = np.zeros(sample_rate)
    impulse[0] = 1.
    x = np.arange(0,500) # x is samples
    response = lfilter(b,a,impulse)
    plt.subplot(413)
    plt.plot(x, response)
    plt.ylabel('Amplitude')
    plt.xlabel('n (samples)')
    plt.title('Impulse response')
    step = np.cumsum(response)
    plt.subplot(414)
    plt.plot(x, step)
    plt.ylabel('Amplitude')
    plt.xlabel('n (samples)')
    plt.title('Step response')
    plt.subplots_adjust(hspace=.5)
    plt.show()
    """
"""
To compare digital and analog filters:

b, a = signal.butter(1, 1., 'high', analog=True)
w, h = signal.freqs(b, a)
plt.semilogx(w, 20*np.log10(abs(h)))

b, a = signal.butter(1, 1./250, 'high')
w, h = signal.freqz(b, a)
plt.semilogx(w*500/(2*np.pi), 20*np.log10(abs(h)))

Note cooeffiecitents are completely different
lfilter takes digital coefficients
scipy.signal.bilinear converts digital coefficients from analog coefficients

"""

