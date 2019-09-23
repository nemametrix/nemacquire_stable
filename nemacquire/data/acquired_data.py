# -*- coding: utf-8 -*-
# $Id: acquired_data.py 1419 2018-03-16 21:57:08Z ram_raj $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.
#

import os
from copy import deepcopy
import numpy as np
from nema_log import log
from filters import Notch, Highpass
from filename_creator import get_new_full_filename

# implementsd circular buffer to hold sampled data for display
# to be used for a strip chart (ECG style) display
# NOT threadsafe and doesn't need locks no problem because used by GUI thread only 
class AcquiredDataOverwriteMode():
    
    def __init__(self, cfg, log_cache, max_metadata_length, buffer_size=4000,
                    display_channel=None,recorded_channels = None):
        #Import here to not cause a CoreFoundations error in Video Process in
        #macOS
        import sounddevice
        self.recorded_channels = recorded_channels
        self.display_channel = display_channel

        self.timestamp_dict = {}
        self.cfg = cfg
        self.log_cache = log_cache
        self.max_metadata_length = max_metadata_length
        # with this class, len(self.buf) will always == self.max_buf_size
        # but for other circular buffer implementations this may not be
        # keeping this way for easy of changing if need be
        self.buf = np.zeros(buffer_size)
        self.max_buf_size = buffer_size 
        self.buf_index = 0               # place to add new samples
        self.sample_rate = 500 # only one supported at the moment
        self.stats_buf = np.array([])    # buffer to for calculating stats
        self.pre_filter_stats_buf = np.array([])    # buffer to for calculating offset
        self.powerline_50Hz_buf = np.array([])  # buffer to calculate powerline noise
        self.powerline_60Hz_buf = np.array([])  # buffer to calculate powerline noise
        # calculate every 1 second to give 1Hz but more responsive
        self.stats_buf_max_size = 500
        # calculate freq every four seconds to give 0.25Hz fft resolution
        self.freq_buf_max_size = 2000
        # plus 1 for stepMode = True
        self.fft_x = np.arange(self.sample_rate/4 + 1) # with ADC .25 bandwidth
        self.fft_x = self.fft_x - 0.5 # to center on bins
        self.freq_buf = np.array([])
        self.dominant_freq = 0
        self.vpp = 0
        self.powerline_noise_V = 0
        self.pre_filter_offset = 0
        self.highpass_filter = None
        self.notch_filter = None
        self.out_of_band_filter = None
        self.out_of_band_filter_2nd = None
        self.pass_filter_50Hz = Notch((49,51), bandpass=True)
        self.pass_filter_60Hz = Notch((59,61), bandpass=True)
        self.recording = False
        self._amp_dict = {}
        self.fft_data = np.array([])
        self.freq = np.fft.fftfreq(self.freq_buf_max_size)
        self.bin40Hz = 40 * self.freq_buf_max_size/self.sample_rate
        self.output_file = None
        self.frame_sample_alignment_found = False
        self.sample_offset = 0
        self.packet_offset = 0
        # hard coded for now
        self._amp_dict = {'amp_sample_rate_hz' : 500,
                          'amp_range_mVpp'     : 750 }
        #self.dev = AudioDevice(0, bits=16, rate=505, channels=1)
        
        self.full_fn = ''

    def enable_highpass_filter(self, enable):
        if enable:
            self.highpass_filter = Highpass(1)
        else:
            self.highpass_filter = None

    def enable_notch_filter(self, enable, freq=None):
        if enable:
            self.notch_filter = Notch((freq-1,freq+1))
        else:
            self.notch_filter = None

    def enable_out_of_band_filter(self, enable, freq=None):
        if enable:
            print "Enabling 125Hz notch (width of 30Hz) with 2nd harmonic of 250Hz"
            self.out_of_band_filter = Notch((freq-15,freq+15))
            self.out_of_band_filter_2nd = Notch((freq*2-15,freq*2+15))            
        else:
            print "Disabling 125Hz and 2nd harmonic notch"
            self.out_of_band_filter = None
            self.out_of_band_filter_2nd = None

    def set_buffer_size(self, new_size):
        if new_size < len(self.buf):
            self.buf = self.buf[:new_size]
            # when scaling down time axis don't through away data unnecessarily
            if self.buf_index > new_size:
                self.buf_index = 0 
        else:
            self.buf = np.append(self.buf,
                                 np.zeros(new_size-self.max_buf_size))

            # don't need update buf_index
            assert self.buf_index < new_size
        self.max_buf_size = new_size
        assert self.max_buf_size == len(self.buf) 

    def get_data(self):
        b = np.copy(self.buf)
        return self.buf_index, b

    # update buffer with newly acquired data
    # samples must be an np array num_of_samples x num_channels
    # exposure starts:
    # on every drdy, Arduino checks to see if the if the GPO (exposure start)
    # from the camera is set, if so Arduino sets an exposure_start bit to 1,
    # otherwise 0
    # each sample has an exposure bit
    def add_samples(self, samples, timestamp, exposure_starts):
        
        #Write all samples
        #Display one
        samples = np.array(samples)
        exposure_starts = np.array(exposure_starts)
        display_data = samples[:, self.display_channel-1]

        if self.recording:
            # write data unfiltered
            self.timestamp_dict[self.timestamp_dict_count] = timestamp
            self.timestamp_dict_count = self.timestamp_dict_count + 1
            self.write_new_data(samples)

            if not self.frame_sample_alignment_found :
                #print exposure_starts
                try :
                    self.sample_offset = np.nonzero(exposure_starts)[0][0]
                except : 
                    
                    self.packet_offset = self.packet_offset + 1
                else :
                    self.frame_sample_alignment_found = True

        self.pre_filter_stats_buf = np.append(self.pre_filter_stats_buf,
            display_data)

        powerline_50Hz_samples = self.pass_filter_50Hz.next_sample(display_data)
        powerline_60Hz_samples = self.pass_filter_60Hz.next_sample(display_data)
        
        self.powerline_50Hz_buf = np.append(self.powerline_50Hz_buf, powerline_50Hz_samples)
        self.powerline_60Hz_buf = np.append(self.powerline_60Hz_buf, powerline_60Hz_samples)

        if self.highpass_filter:
            display_data = self.highpass_filter.next_sample(display_data)

        if self.notch_filter:
            display_data = self.notch_filter.next_sample(display_data)

        if self.out_of_band_filter:
            display_data = self.out_of_band_filter.next_sample(display_data)

        if self.out_of_band_filter_2nd:
            display_data = self.out_of_band_filter_2nd.next_sample(display_data)

        self.stats_buf = np.append(self.stats_buf, display_data)
        self.freq_buf = np.append(self.freq_buf, display_data)

        if len(self.stats_buf) >= self.stats_buf_max_size:
            # stats buf needs to be exact size for fft, but other bufs don't matter
            self.stats_buf = self.stats_buf[-self.stats_buf_max_size:]

            if False:
                # @todo: there are few issues that need to be resolved before
                # real-time audio playback works
                # (1) sounddevice supports minimum sampling rate of 1000Hz
                #     - a good workaround for this might be to modulate white noise
                #       with volume (as Bill had done for a paper)
                # (2) pauses in the sound happen after play is finished.
                #     e.g. for i in range(10): sd.play(d1000, 1000)
                #     - a solution might be to use the callback feature:
                #     https://stackoverflow.com/questions/36988920/how-to-gracefully-stop-python-sounddevice-from-within-callback
                # scale so that +250/+-250 uV is max volume of +1.0/-1.0 
                s500 = self.stats_buf / 250e-6
                s1000 = np.repeat(s500, 2)
                print(len(s1000))
                sounddevice.play(s1000, 1000, 1)
            
            self.vpp = self.stats_buf.ptp()
            self.post_filter_offset = self.stats_buf.mean()
            self.pre_filter_offset = self.pre_filter_stats_buf.mean()
            self.powerline_noise_V = max(np.ptp(self.powerline_50Hz_buf), np.ptp(self.powerline_60Hz_buf))
            #print self.powerline_noise_V * 1000000, np.ptp(self.powerline_50Hz_buf) * 1000000, np.ptp(self.powerline_60Hz_buf) * 1000000
            # temp avoid inconsistency protocol thread updates
            temp_fft = np.fft.fft(self.stats_buf)
            # take the absolute value of half the real half because the
            # bandwidth of the ADC at 500Hz sampling is 125Hz
            self.fft_data = np.abs(temp_fft[:len(temp_fft)/4])
            self.stats_buf = np.array([])
            self.pre_filter_stats_buf = np.array([])
            self.powerline_50Hz_buf = np.array([])
            self.powerline_60Hz_buf = np.array([])

        if len(self.freq_buf) >= self.freq_buf_max_size:
            self.freq_buf = self.freq_buf[-self.freq_buf_max_size:]
            fft_d = np.fft.fft(self.freq_buf)
            # get index of bin with greatest power
            # limit index to positive frequencies only below common noise levels of 50/60Hz and their harmonics
            dominant_index = np.argmax(np.abs(fft_d[1:self.bin40Hz]))
            # must multiply by samplerate to convert to Hz
            self.dominant_freq = self.freq[dominant_index+1] * 500
            self.freq_buf = np.array(self.freq_buf[500:])  # lop off the oldest second of data
            
        space_left = self.max_buf_size - self.buf_index
        if space_left > len(display_data):
            self.buf[self.buf_index:self.buf_index + len(display_data)] = display_data
            self.buf_index += len(display_data)
        else:
            self.buf[self.buf_index:self.buf_index + space_left] = display_data[:space_left]
            self.buf_index = 0
            display_data = display_data[space_left:]
            self.buf[0:len(display_data)] = display_data             

    def get_current_full_filename(self):
        return self.full_fn

    def write_new_data(self, samples):
        if self.csv_header_written == False:
            for channel_num in self.recorded_channels:
                csv_header = ("channel_%d (uV)"%channel_num) 
                self.output_file.write(csv_header)
            self.output_file.write("\n")
            self.csv_header_written = True
        # write sample to file
        for all_channel_data in samples:
            for num, channel_data in enumerate(all_channel_data):
                if (num + 1) in self.recorded_channels:
                    channel_data *= 1000000
                    self.output_file.write("%.1f " % channel_data)

            self.output_file.write("\n")


    def get_video_time_offset(self):

        if self.frame_sample_alignment_found :
            time_offset = 0.002*6*self.packet_offset + self.sample_offset*0.002 
            return time_offset
      
        else:
            return 0
       
    def get_video_sample_offset_raw(self):

        if self.frame_sample_alignment_found :
            return self.packet_offset*6 + self.sample_offset
        else :
            return -1
        # in a future refactor, may move file writing code to here
    
    def start_recording(self):
        self.sample_offset = 0
        self.packet_offset = 0
        self.frame_sample_alignment_found = False
        self.timestamp_dict_count = 0
        self.timestamp_dict = {}
        assert self.output_file == None
        self.full_fn = get_new_full_filename("nema", "txt", self.cfg)
        try:
            self.output_file = open(self.full_fn, 'w')
        except IOError:
            last_type, last_value, last_traceback = sys.exc_info()
            log('Could not open: %s' % traceback.format_exception_only(last_type,last_value)[0],
                cache=self.log_cache)
            # re-raise exception (and re-catch to display to user rather than allowing the
            # QT framework to swallow exception
            raise
        #log('Opened file: %s' % self.output_file.name, cache=self.log_cache)
        self.csv_header_written = False
        # reserve space at the beginning for metadata
        # this space will be filled by non printable null characters
        self.output_file.seek(self.max_metadata_length) 
        self.output_file.write('\n')
        # assign object attributes on after we are ready to write (open file etc)
        # because the writing thread is already running
        self.recording = True

    def stop_recording(self):
        # let the recieve thread know to stop writing
        # no system calls made between checks and writes so no chance of attempted write to closed file
        self.recording = False

    def discard_recording(self):
        assert self.recording == False
        self.output_file.close()
        os.remove(self.output_file.name)
        self.output_file = None
    
    def close_file(self, metadata_string):
        assert self.recording == False
        assert self.output_file
        assert len(metadata_string) <= self.max_metadata_length
        self.output_file.seek(0)
        self.output_file.write(metadata_string)
        self.output_file.close()
        self.output_file = None
        self.full_fn = None
                    
    def get_amplifier_settings(self):
        return deepcopy(self._amp_dict)

# implements circular buffer to hold sampled data for display
# to be used for a scrolling display
class AcquiredDataScrollingMode():
    pass

        
  
