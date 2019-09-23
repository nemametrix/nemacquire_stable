# -*- coding: utf-8 -*-
#
# $Id: nema_config.py 1446 2018-05-11 22:04:13Z ram_raj $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.
#
from collections import OrderedDict
import codecs
import ConfigParser
from nema_log import log
from ast import literal_eval
import os

class NemaConfig(object):
    cfg_path = os.path.expanduser(os.path.join('~', 'NemaMetrix', 'NemAcquire', 'Preferences'))
    if not os.path.isdir(cfg_path):
        try:
            os.makedirs(cfg_path)
        except os.error:
            configfile = os.path.join(os.path.expanduser(os.path.join('~', 'Desktop', 'nemacquire_config.txt')))
    if os.path.isdir(cfg_path):
        configfile = os.path.join(cfg_path, 'nema_config.txt')
    section_display_options = 'DisplayOptions'
    section_labnotes = 'LabNotes'
    section_recording_options = 'RecordingOptions'
    section_camera_options = 'CameraOptions'
    
    # Set default values for case where there is no config file
    vpp = True
    freq = True
    offset = False
    highpass = True
    notch_50Hz = False
    notch_60Hz = False
    grid = True
    power_spectrum = False
    fonts = False
    show_fps = False
    flip_vertically = False
    flip_horizontally = False
    time_test = False
    show_scope = False
    show_epg = True
    powerline = True
    powerline_threshold = 50
   
    #camera_options
    framerate_div = 3
    white_balance = False
    exposure_time = 9
    triggered = False
    framerate_free = 30
    gain = 0.0 #gain is in db
    auto_exp_gain = True
    roi_enabled = False
    roi_state = {'angle': 0.0, 'pos': (446, 390), 'size': (1160, 318)}
    video_fourcc = 'H264' # FourCC of desired encoding
    video_format = 'mp4' # Video Container
    
    #Bounds section

    # Making the assumption that the user's Desktop folder is writable
    recording_folder = os.path.expanduser(os.path.join('~', 'Desktop'))
    display_epg_channel = 1
    recorded_epg_channels = (1,)
    # programatic id, text id, enabled, value - could be strings or numbers
    labnotes_items = OrderedDict({})
    
    # Key -> Name, Enabled, Value
    labnotes_items['orientation'] = ["Worm Orientation", True, ""]
    labnotes_items['pumping_stimulus'] = ["Pumping Stimulus", True, ""]
    labnotes_items['stimulus_concentration'] = ['Stimulus Concentration', True, ""]
    labnotes_items['stimulus_prep_time'] = ['Stimulus Preparation Date/Time', True, ""]
    labnotes_items['drug_name'] = ['Drug Name', False, ""]
    labnotes_items['drug_concentration'] = [ 'Drug Concentration (mM)',False,""]
    labnotes_items['species'] = ["Worm Species", False, ""]
    labnotes_items['strain'] = ['Worm Strain', True, ""]
    labnotes_items['temperature'] = [u"Temperature (°C)", True, ""]
    labnotes_items['worm_number'] = ['Worm Number', True, 1]
    labnotes_items['experiment_number'] = ['Experiment Number', True, 1]
    labnotes_items['chip_design'] = ['Chip Lot', False, ""]
    labnotes_items['experimenter'] = ['Experimenter', True, ""]
    labnotes_items['protocol'] = ["Protocol",False,""]
    labnotes_items['notes'] = ["Additional Notes", True, ""]


    #These are not brought out in nema config txt file. Nemacquire depends on
    #labnotes items having any keys used below

    #Labnotes items with discrete values
    restricted_choices_labnotes_items_fields = {}
    restricted_choices_labnotes_items_fields['orientation'] = ["Head First","Tail First"]
    restricted_choices_labnotes_items_fields['pumping_stimulus'] = ["None (Buffer)",
    "OP50","Serotonin","Other"]
    
    #These have to be set
    mandatory_labnotes_items_fields = ['orientation',
                                        'pumping_stimulus']
    
    #Since these are always shown, we don't bring it out in nemacquire note
    #field selection
    always_shown_labnotes_items_fields = ['orientation',
                                        'pumping_stimulus',
                                        'worm_number',
                                        'experiment_number']
    #Tooltips for labnotes items
    labnotes_items_tool_tips = {}
    labnotes_items_tool_tips['pumping_stimulus'] = \
            "Method used to stimulate pharyngeal pumping in <i>C. elegans</i>"
    def load(self):
        config = ConfigParser.RawConfigParser()
        config.optionxform = str # have options case sensitive
        try:
            f = codecs.open(self.configfile, "r", "utf8")
        except IOError:
            log('No config found, creating one')
            self.save()
        else:
            try:
                config.readfp(f)
                
                self.vpp = config.getboolean(self.section_display_options, 'vpp')
                self.offset = config.getboolean(self.section_display_options, 'offset')
                self.powerline = config.getboolean(self.section_display_options, 'powerline')
                self.powerline_threshold = config.getint(self.section_display_options,'powerline_threshold')
                self.freq = config.getboolean(self.section_display_options, 'freq')
                self.highpass = config.getboolean(self.section_display_options, 'highpass')
                self.notch_50Hz = config.getboolean(self.section_display_options, 'notch_50Hz')
                self.notch_60Hz = config.getboolean(self.section_display_options, 'notch_60Hz')
                self.grid = config.getboolean(self.section_display_options, 'grid')
                self.fonts = config.getboolean(self.section_display_options, 'fonts')
                self.time_test = config.getboolean(self.section_display_options, 'time_test')
                self.show_fps = config.getboolean(self.section_display_options, 'show_fps')
                self.flip_vertically = config.getboolean(self.section_display_options, 'flip_vertically')
                self.flip_horizontally = config.getboolean(self.section_display_options, 'flip_horizontally')
                self.power_spectrum = config.getboolean(self.section_display_options, 'power_spectrum')
                self.show_scope = config.getboolean(self.section_display_options, 'show_scope')
                self.show_epg = config.getboolean(self.section_display_options,
                        'show_epg')
                self.labnotes_item_temp = config.items(self.section_labnotes)
                self.display_epg_channel = config.getint(self.section_recording_options, 'display_epg_channel')
                self.recorded_epg_channels_text = config.get(self.section_recording_options,
                'recorded_epg_channels')
                self.recording_folder = config.get(self.section_recording_options, 'recording_folder')

                self.framerate_div =\
                config.getint(self.section_camera_options,'framerate_div')
                self.triggered =\
                config.getboolean(self.section_camera_options, 'triggered')
                self.exposure_time =\
                config.getint(self.section_camera_options,'exposure_time')
                self.white_balance =\
                config.getboolean(self.section_camera_options,'white_balance')
                self.framerate_free =\
                config.getint(self.section_camera_options,'framerate_free')
                self.gain = config.getfloat(self.section_camera_options,'gain')
                self.auto_exp_gain =\
                config.getboolean(self.section_camera_options,'auto_exp_gain')
                self.roi_state_temp = config.get(self.section_camera_options,'roi_state')
                self.roi_enabled = config.getboolean(self.section_camera_options,'roi_enabled')
                self.video_fourcc = config.get(self.section_camera_options,'video_fourcc')
                self.video_format = config.get(self.section_camera_options,'video_format')
                
                self.labnotes_items_temp_dict = OrderedDict({})
                
                for i in range(len(self.labnotes_item_temp)):
                    self.labnotes_items_temp_dict[self.labnotes_item_temp[i][0]] =\
                    literal_eval(self.labnotes_item_temp[i][1])
                
                #Raise an error if a required field is absent in labnotes
                for labnotes_item in self.mandatory_labnotes_items_fields:
                    if not labnotes_item in self.labnotes_items_temp_dict:
                        raise ConfigParser.NoOptionError(
                        str(labnotes_item),self.section_labnotes)
                        
                for labnotes_item in self.always_shown_labnotes_items_fields:
                    if not labnotes_item in self.labnotes_items_temp_dict:
                        raise ConfigParser.NoOptionError(
                        str(labnotes_item),self.section_labnotes)
                
                self.roi_state_temp = literal_eval(self.roi_state_temp)
                self.recorded_epg_channels_temp = literal_eval(self.recorded_epg_channels_text)
                #Check if roi_state is correctly set
                if not isinstance(self.recorded_epg_channels_temp,tuple):
                    if isinstance(self.recorded_epg_channels,temp,int):
                        self.recorded_epg_channels =\
                        (self.recorded_epg_channels,)
                    else:
                        raise ValueError(
                        "Invalid value for recorded epg channels")
            except:
                log('Problem loading config')
                f.close()   # close corrupt configfile so it can be renamed and replaced
                raise
            else:
                # convert the strings to python lists
                self.labnotes_items = self.labnotes_items_temp_dict
                self.roi_state = self.roi_state_temp
                self.recorded_epg_channels = self.recorded_epg_channels_temp
                

    def save(self):
        config = ConfigParser.RawConfigParser()
        config.optionxform = str # have options case sensitive

        config.add_section(self.section_display_options)
        config.set(self.section_display_options, 'vpp', str(self.vpp))
        config.set(self.section_display_options, 'offset', str(self.offset))
        config.set(self.section_display_options, 'powerline', str(self.powerline))
        config.set(self.section_display_options, 'powerline_threshold',str(self.powerline_threshold))
        config.set(self.section_display_options, 'freq', str(self.freq))
        config.set(self.section_display_options, 'highpass', str(self.highpass))
        config.set(self.section_display_options, 'notch_50Hz', str(self.notch_50Hz))
        config.set(self.section_display_options, 'notch_60Hz', str(self.notch_60Hz))
        config.set(self.section_display_options, 'grid', str(self.grid))
        config.set(self.section_display_options, 'power_spectrum', str(self.power_spectrum))
        config.set(self.section_display_options, 'fonts', str(self.fonts))
        config.set(self.section_display_options, 'show_fps', str(self.show_fps))
        config.set(self.section_display_options, 'flip_vertically', str(self.flip_vertically))
        config.set(self.section_display_options, 'flip_horizontally', str(self.flip_horizontally))
        config.set(self.section_display_options, 'time_test', str(self.time_test))
        config.set(self.section_display_options, 'show_scope', str(self.show_scope))
        config.set(self.section_display_options, 'show_epg', str(self.show_epg))
        config.add_section(self.section_recording_options)
        config.set(self.section_recording_options, 'recording_folder', str(self.recording_folder))
        config.set(self.section_recording_options, 'recorded_epg_channels',
                str(self.recorded_epg_channels))
        config.set(self.section_recording_options, 'display_epg_channel', str(self.display_epg_channel))
        config.add_section(self.section_camera_options)
        config.set(self.section_camera_options, 'framerate_div',
                str(self.framerate_div))
        config.set(self.section_camera_options, 'triggered',
                str(self.triggered))
        config.set(self.section_camera_options, 'exposure_time',
                str(self.exposure_time))
        config.set(self.section_camera_options, 'white_balance',
                str(self.white_balance))
        config.set(self.section_camera_options, 'framerate_free',
                str(self.framerate_free))
        config.set(self.section_camera_options, 'gain',
                str(self.gain))
        config.set(self.section_camera_options, 'auto_exp_gain',
                str(self.auto_exp_gain))
        config.set(self.section_camera_options, 'roi_state',
                str(self.roi_state))
        config.set(self.section_camera_options, 'roi_enabled',
                str(self.roi_enabled))
        config.set(self.section_camera_options, 'video_fourcc',
                str(self.video_fourcc))
        config.set(self.section_camera_options, 'video_format',
                str(self.video_format))
        
        # labnotes
        config.add_section(self.section_labnotes)
        # Always enable mandatory labnotes item fields
        for k in self.labnotes_items:
            if k in self.mandatory_labnotes_items_fields:
                self.labnotes_items[k][1] == True
            if k in self.always_shown_labnotes_items_fields:
                self.labnotes_items[k][1] == True
            config.set(self.section_labnotes, k, str(self.labnotes_items[k]))
            
        with codecs.open(self.configfile, 'wb', "utf8") as cf:
            config.write(cf)
        cf.close()
        return
        
