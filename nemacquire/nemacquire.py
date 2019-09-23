#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# $Id: nemacquire.py 1445 2018-05-11 21:55:01Z ram_raj $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.
#

from time import time, localtime, strftime,sleep
from multiprocessing import freeze_support,Array#, log_to_stderr
from multiprocessing.queues import SimpleQueue
from threading import Thread
#import logging

#Importing any library that uses usb or has GUI elements before instantiation
#of the Video Process can potentially
#cause a CoreFoundations error on macOS X. Take care to import them after
#instantiation

from PySide import QtCore, QtGui

import pyqtgraph as pg # sets graphics system to raster on darwin
import pyqtgraph.console as console
QtGui.QApplication.setGraphicsSystem('native') # avoids blinking
import ConfigParser

import numpy as np
import platform
import traceback
import sys, os
import subprocess
import math
import json
import cv2

sys.path.append('data')
sys.path.append('protocol')
sys.path.append('resources')
sys.path.append('ui')
sys.path.append('utility')
sys.path.append('../common/ui')

from video_view import VideoView, State
from custom_pyqtgraph_classes import RectROICustom
from nema_log import log
from video import VideoProcess, Command, CamPrm, get_framerate
from test_wave_generator import TestWaveGenerator
from ui_mainwindow import Ui_MainWindow
from ui_comm_stats import Ui_CommStats
from nema_config import NemaConfig
from acquired_data import AcquiredDataOverwriteMode
from hackeeg import ReceiveDataWorker, get_input_normal_command_string,\
get_input_square_wave_command_string,send_framerate_cmd
from nema_log import LogCache
from camera_settings import CameraSettings
from camera_info import CameraInfo
from update_dialog import ArdUpdateDialog
from noise_test_dialog import NoiseTestDialog
from timeout_warning_dialog import TimeoutWarningDialog
import frameutils as fu
from filename_creator import get_new_full_filename

import version

def customizeDialogFlags(d, title=None, close=False):
    # Using WindowsSystemMenuHint will place a nice icon on windows, but then
    # on OS X fails to adhere to the closeButtonHint
    flags = QtCore.Qt.Dialog | QtCore.Qt.CustomizeWindowHint
    if title:
        flags |= QtCore.Qt.WindowTitleHint
        d.setWindowTitle(title)
    if close:
        flags |= QtCore.Qt.WindowCloseButtonHint
    d.setWindowFlags(flags)

def qt_revert_fixed_size(obj):
    
    max_value = 1677215
    
    obj.setMaximumHeight(1677215)
    obj.setMaximumWidth(1677215)
    obj.setMinimumWidth(0)
    obj.setMinimumHeight(0)



class NemaMainWindow(QtGui.QMainWindow, Ui_MainWindow):

    animation_finished_signal = QtCore.Signal()

    def __init__(self, img_queue, img_cmd_queue, img_status_queue,
            shared_img_array, cfg):
        #Import here to not cause a CoreFoundations error in Video Process in
        #macOS
        import sounddevice
        import scipy.io.wavfile
        
        #Allow sounddevice library to be accessed from other methods in NemaMainWindow
        self.sounddevice = sounddevice
        
        super(NemaMainWindow, self).__init__()
        self.shared_image_array = shared_image_array
        self.display_epg_channel = cfg.display_epg_channel         
        
        if not 1 <= self.display_epg_channel <= 8:
            self.display_epg_channel = 1
            cfg.display_epg_channel = self.display_epg_channel
            cfg.save()
        
        #Read from cfg only once ! Any edits would require a restart of the application to take effect
        self.recorded_epg_channels = cfg.recorded_epg_channels
        self.video_fourcc = cfg.video_fourcc
        self.video_format = cfg.video_format
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.img_queue = img_queue
        self.img_cmd_queue = img_cmd_queue
        self.img_status_queue = img_status_queue
        
        self.prev_point = 0
        # for now we only support EKG style overwriting chart
        self.leading_samples = 500
        # default min and max must be powers of two
        self.samples_to_display = 4000 
        self.minimum_samples_to_display = 500   
        self.maximum_samples_to_display = 64000 # gives approx two minute's worth of data at 500 Hz
        assert self.samples_to_display % self.minimum_samples_to_display == 0
        assert self.maximum_samples_to_display % self.samples_to_display == 0
        self.max_metadata_length = 4999
        self.log_cache = LogCache()
        self.buf = AcquiredDataOverwriteMode(cfg,
                                             self.log_cache,
                                             self.max_metadata_length,
                                             self.samples_to_display,
                                             display_channel = self.display_epg_channel,
                                             recorded_channels = self.recorded_epg_channels)
        self.demo_mode = False
        self.vid_source_control = 4
        self.camera_connected = False
        self.requested_force_triggered_mode = False
        self.dropped_video_frames_while_recording = False
        self.camera_info_dict = {CamPrm.display_freq : 0,
                                 CamPrm.record_freq : 0,
                                 CamPrm.connection_info : ["Not Connected",0,0]} 


        self.dropped_frame_error_text =\
"Some frames were dropped by the Camera. Please take the following steps:"+\
"<br><ol>"+\
"<li>Check Amplifier to Camera, and Camera to Computer Connections</li><br>"+\
"<li>Use 'Zoom in' button to select a smaller recording area or "+\
"reduce framerate in <b>Camera > Settings</b></li><br>"+\
"<li>Ensure Camera has a dedicated USB 3.0 port</li><br>"+\
"<li>Use a PC with higher performance</li></ol><br>"+\
"""<style>
a:link {
    color: rgb(33, 150, 243); 
}
</style>"""+\
"<br>Feel free to contact technical support at 1.844.663.8749 or <br>"+\
'<a href="mailto:support@nemametrix.com">support@nemametrix.com</a>'+\
" if you have any questions."


        self.y_width = 1088
        self.x_width = 2048
        self.x_left = 0
        self.y_top = 0
        

        
        self.center_y_arr = [self.y_top]

        #Has to be the same as in video.py
        self.base_freq = 250

        # takes the path where the executable resides
        self.base = os.path.dirname(sys.argv[0])
        # normal case for installed application
        stylesheet_path = os.path.join(self.base, "ui", "dark_stylesheet.css")
        if not os.path.isfile(stylesheet_path):
            stylesheet_path = os.path.join(self.base, "..", "common", "ui", "dark_stylesheet.css")
        with open(stylesheet_path, "r") as ss:
            self.style_sheet = ss.read()
        self.setStyleSheet(self.style_sheet)
        self.setupUi(self)
        self.graphicsLayoutWidget.setBackground(None)
        #Minimize space between image view and EPG view
        self.graphicsLayoutWidget.ci.setSpacing(0)

        """8-channel UI setup"""
        """
        self.channel_label.setText("Channel (Display): ") 
        for i in range(1,9):
            self.channel_comboBox.addItem(str(i))


        self.channel_comboBox.setCurrentIndex(display_channel - 1) 
        self.channel_comboBox.currentIndexChanged.connect(self.update_display_channel)
        #Immutable set of recording channels initially loaded from config
        """
        """End of 8-channel specific setup """
        #Create a 'parent' layout holding image view and image buttons
        
        self.image_layout = self.graphicsLayoutWidget.addLayout(row=0, col=0)
        self.image_layout.setContentsMargins(0,0,0,0)
        #Create image_view_layout, image is meant to be centered w.r.t to this
        self.image_view_layout = self.image_layout.addLayout(row=0,col=0)
        self.image_view_layout.setContentsMargins(0,0,0,0)

        #create image_view_layout
        self.image_button_layout =\
        self.image_layout.addLayout(row=0,col=1)
        self.image_button_layout.setContentsMargins(0,0,0,0)        

        #get gridLayout object for both image_view_layout and image_layout micro modifications
        #only need to be performed once 
        image_gridLayout = self.image_layout.layout
        image_gridLayout.setColumnMaximumWidth(1,160)
        image_gridLayout.setSpacing(0)
        
        image_view_gridLayout = self.image_view_layout.layout
        image_view_gridLayout.setSpacing(0)
        image_view_gridLayout.setColumnStretchFactor(1,200)
        image_view_gridLayout.setColumnMinimumWidth(0,0)
        image_view_gridLayout.setColumnMinimumWidth(2,0)
        #image_view_gridLayout.setRowStretchFactor(1,100)
        image_view_gridLayout.setRowAlignment(1,QtCore.Qt.AlignVCenter)
        #Create image_button_layout
        #Create a proxy widget to allow embedding of normal qwidgets (like
        #buttons) within graphicslayout
        self.q_proxy_widget = QtGui.QGraphicsProxyWidget()
        self.image_button_layout.addItem(self.q_proxy_widget)
        
        #Intermediate widget to serve as the QWidget end of the proxy
        self.intermediate_widget = QtGui.QWidget()
        self.intermediate_widget.setStyleSheet(self.style_sheet)
        self.q_proxy_widget.setWidget(self.intermediate_widget) 
        self.intermediate_widget.setMaximumWidth(150)
        #self.intermediate_widget.setMinimumWidth(150)
        
        #Spacer Items to squeeze all buttons as close as possible
        spacerItemTop = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Minimum,
                QtGui.QSizePolicy.Expanding)
        spacerItemBot = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Minimum,
                QtGui.QSizePolicy.Expanding)
        
        #Add a layout that can now accept QWidgets and then populate them with
        #buttons,labels,sliders that have been defined in ui/ui_mainwindow.py
        self.image_button_widget_layout =\
        QtGui.QVBoxLayout(self.intermediate_widget)
        self.image_button_widget_layout.addItem(spacerItemTop)
        self.image_button_widget_layout.addWidget(self.pushButtonROI)
        self.image_button_widget_layout.addWidget(self.pushButtonImage)
        self.image_button_widget_layout.addWidget(self.exposure_label)
        self.image_button_widget_layout.addWidget(self.exposure_slider)
        self.image_button_widget_layout.addWidget(self.gain_label)
        self.image_button_widget_layout.addWidget(self.gain_slider)
        self.image_button_widget_layout.addWidget(self.auto_exp_gain_checkBox)
        self.image_button_widget_layout.addWidget(self.pushButtonCameraSettings)
        self.image_button_widget_layout.addItem(spacerItemBot)
        self.image_button_widget_layout.setSpacing(15)
        self.image_button_widget_layout.setContentsMargins(0,0,0,0)
    
        #self.intermediate_widget.setMaximumWidth(self.exposure_label.sizeHint().width())
       #Treat these additional columns as spacers to ensure centering of display image
       #image_view_layout in the horizontal direction (only)
        self.layout_left = self.image_view_layout.addLayout(1,0)
        self.layout_left.setMinimumSize(QtCore.QSizeF(0,0))
        self.layout_left.setContentsMargins(0,0,0,0)
        self.layout_right = self.image_view_layout.addLayout(1,2) 
        self.layout_right.setMinimumSize(QtCore.QSizeF(0,0))
        self.layout_right.setContentsMargins(0,0,0,0)
       #Add a viewbox which only displays image
        self.vb = VideoView(cfg,self.image_view_layout,self.video_view_callback,
                            self.animation_finished_signal)

        self.image_view_layout.addItem(
                self.vb,
                row = 1, 
                col = 1)

        self.vb.disableAutoRange('xy')
        self.vb.autoRange(padding=0)
        self.vb.setSizePolicy(QtGui.QSizePolicy.Expanding,QtGui.QSizePolicy.Expanding)

        self.vb.setAspectLocked(True)
        self.vb.setMouseEnabled(x=False,y=False)
        #self.cam =\
        #cv2.VideoCapture('/home/ram/perugino/nema_desktop_sw/nemacquire/NemAcq_Test_Files/9x_video_60fps.avi')
        
        self.test_full_img = cv2.imread('Etaluma.png')
        
        self.layout = self.graphicsLayoutWidget.addLayout(row=1, col=0)
        self.graphicsView = self.layout.addPlot(row=1, col=0, enableMouse=False, enableMenu=False, background=None)
        self.w_left = self.graphicsView.plot()
        self.w_right = self.graphicsView.plot()

        # style for pyqtgraph objects
        self.labelStyle = {'color': '#ffffff', 'font-size': '12pt', 'font-family': 'sans-serif'}
        # color for recording / non-recording waveform
        self.recording_red = (255,76,76)
        self.plot_color = (255,255,255)

        self.filter_label.setText("Filter (Display):")
        self.freq_text_label = QtGui.QLabel("EPG (Hz)", self.graphicsLayoutWidget)
        self.freq_text_value = QtGui.QLabel("000.00", self.graphicsLayoutWidget)
        self.img_label =\
        QtGui.QLabel("Channel not detected")
        #self.image_view_layout.addLabel(self.img_label)
        self.freq_text_value.setStyleSheet('font: bold "Trebuchet MS"; font-size: 38pt; color: rgb(33, 150, 243);')
        self.freq_text_value.setAlignment(QtCore.Qt.AlignRight)
        
        
        
        # Set tooltip for filter labels and filter objects
        filter_tooltip_text = "Filter is for display only\nWhen recording, unfiltered data is saved to disk"
        self.highpass_comboBox.setToolTip(filter_tooltip_text)
        self.notch_comboBox.setToolTip(filter_tooltip_text)
        self.filter_label.setToolTip(filter_tooltip_text)
        
        #Gain slider maximum initialization
        self.gain_multiplier = 100 #QSlider only works with Integer values so we
        # use a multiplier to handle up to 2 decimal points
        gain_max = 6.0
        gain_min = -1.5
        if cfg.gain > gain_max:
            cfg.gain = gain_max
        self.gain_label.setText("Gain: xxx db")
        self.gain_slider.setValue(cfg.gain)
        
        self.update_gain_limits(gain_min,0.01,gain_max)
        self.gain_slider.valueChanged.connect(self.update_gain)
        
        s = self.gain_label.sizeHint()
        self.gain_label.setMinimumWidth(s.width())
        s = self.gain_slider.sizeHint()
        self.gain_slider.setMinimumWidth(s.width())
        
        #Exposure slider maximum initialization
        exposure_max = 1000.0/get_framerate(cfg.triggered,
                                            self.base_freq,
                                            cfg.framerate_div,
                                            cfg.framerate_free)
        exposure_max = int(exposure_max) - 1
        
        if cfg.exposure_time > exposure_max :
            cfg.exposure_time = exposure_max
        self.exposure_label.setText("Exposure: xxx ms")
        self.exposure_slider.setValue(cfg.exposure_time)

        self.update_exposure_maximum(exposure_max)
        self.exposure_slider.valueChanged.connect(self.update_exposure)
        
        self.auto_exp_gain_checkBox.stateChanged.connect(self.update_auto_exp_gain)
        #Initialize camera settings from cfg for elements displayed in main ui


        s = self.exposure_label.sizeHint()
        self.exposure_label.setMinimumWidth(s.width())
        s = self.exposure_slider.sizeHint()
        self.exposure_slider.setMinimumWidth(s.width())
        
        self.power_spectrum = None

        self.increaseY = QtGui.QPushButton(self.graphicsLayoutWidget)
        self.increaseY.setMinimumSize(QtCore.QSize(38, 38))
        self.increaseY.setText("+")
        self.decreaseY = QtGui.QPushButton(self.graphicsLayoutWidget)
        self.decreaseY.setMinimumSize(QtCore.QSize(38, 38))
        self.decreaseY.setText("-")
        self.increaseX = QtGui.QPushButton(self.graphicsLayoutWidget)
        self.increaseX.setMinimumSize(QtCore.QSize(38, 38))
        self.increaseX.setText("+")
        self.decreaseX = QtGui.QPushButton(self.graphicsLayoutWidget)
        self.decreaseX.setMinimumSize(QtCore.QSize(38, 38))
        self.decreaseX.setText("-")
        self.fitY = QtGui.QPushButton(self.graphicsLayoutWidget)
        self.fitY.setMinimumSize(QtCore.QSize(38, 38))
        self.fitY.setMaximumSize(QtCore.QSize(38, 38))
        self.fitY.setText(u'\u2195')
    
        self.offset_text_label = QtGui.QLabel("Offset (V):   ", self.graphicsLayoutWidget)
        self.offset_text_value = QtGui.QLabel("             ", self.graphicsLayoutWidget)
        s = "Mean reading over the last second, before display filtering"
        self.offset_text_label.setToolTip(s)
        self.offset_text_value.setToolTip(s)

        self.vpp_text_label = QtGui.QLabel("Amplitude (V):   ", self.graphicsLayoutWidget)
        self.vpp_text_value = QtGui.QLabel("             ", self.graphicsLayoutWidget)
        s = "Max-Min reading over the last second, after display filtering"
        self.vpp_text_label.setToolTip(s)
        self.vpp_text_value.setToolTip(s)

        self.powerline_text_label = QtGui.QLabel("Powerline Noise (V):   ",self.graphicsLayoutWidget)
        self.powerline_text_value = QtGui.QLabel("                             ",self.graphicsLayoutWidget)
        s = "Amplitude of the dominant bandpass filtered signal around 50Hz or 60Hz, before display filtering"
        self.powerline_text_label.setToolTip(s)
        self.powerline_text_value.setToolTip(s)
 
        self.wait_dialog = QtGui.QMessageBox(parent=self)
        self.wait_dialog.setText("Operation in progress. Please wait . . .")
        self.wait_dialog.setStandardButtons(0)
        customizeDialogFlags(self.wait_dialog, " ")   
        self.wait_dialog.setIconPixmap(QtGui.QPixmap(":/icon/NemaSymbol_scaled.png"))     
        
        self.buttonHeight = self.increaseY.size().height()
        self.buttonWidth = self.increaseY.size().width()
        
        self.update_x_label()
        self.graphicsView.setLabel('left', 'Voltage', units='V', **self.labelStyle)
        self.graphicsView.setXRange(0,self.samples_to_display, padding=0)
        self.graphicsView.getAxis('bottom').setStyle(showValues=False, tickLength=5)
        self.graphicsView.getAxis('left').setStyle(tickLength=5) 
        self.graphicsView.getAxis('bottom').setTickSpacing(500, 500)        # couldn't disable minor ticks in x axis
        self.graphicsView.setMouseEnabled(False,False)
        self.graphicsView.showGrid(True,True,0.4)
        self.graphicsView.setYRange(-0.0002, 0.0002, padding=0)
        
        # text must be set before setWidth is seen as a valid command
        self.graphicsView.getAxis('right').textWidth = 30
        self.graphicsView.getAxis('right').setWidth(30)
        # hide right axis labels
        self.graphicsView.setLabel('right', "")
        self.graphicsView.getAxis('right').enableAutoSIPrefix(False)
        self.graphicsView.getAxis('right').setStyle(showValues=False)

        self.elapsed_time_label =  QtGui.QLabel("Elapsed time: ", self.graphicsLayoutWidget)
        self.elapsed_time_text =  QtGui.QLabel("00:00:00", self.graphicsLayoutWidget)
        vid_rec_text =\
            "Video : Display at %3d fps; Recording at %3d fps" % (0, 0)
        self.video_fps_text = QtGui.QLabel(vid_rec_text,self.graphicsLayoutWidget)
        self.video_fps_text.hide()
        self.rec_text = QtGui.QLabel("Not Recording", self.graphicsLayoutWidget)
                
        self.set_stats_text_position()
        self.comm_stats_dialog = QtGui.QDialog()
        self.comm_stats_dialog.ui = Ui_CommStats()
        self.comm_stats_dialog.ui.setupUi(self.comm_stats_dialog)
        self.comm_stats_dialog.setModal(False)
        self.comm_stats_dialog.setParent(self)
        customizeDialogFlags(self.comm_stats_dialog, "Amplifier Information", close=True)
        self.cfg = cfg
        self.x_axis_origin = 0

        # be careful to set defaults before connecting events
        self.pushButtonCameraSettings.clicked.connect(self.show_camera_settings_dialog)
        self.pushButtonImage.clicked.connect(self.capture_static_image)
        self.pushButtonROI.setText("Zoom in")
        self.pushButtonROI.setToolTip("Crop image to blue Region of"
                +" Interest (ROI).\nCropping to smaller area allows for greater"
                +"\nframerate when recording")
        self.pushButtonROI.clicked.connect(self.toggle_ROI_view)
        exposure_tool_tip = "Duration when camera accepts light"\
                +" for each frame.\nIncrease maximum exposure time by selecting"\
                +" lower\nframerate"
        gain_tool_tip = "<p>Positive gain amplifies signal while "+\
        "negative gain attenuates signal. E.g. +3db doubles the signal</p>"

        self.exposure_label.setToolTip(exposure_tool_tip)
        self.exposure_slider.setToolTip(exposure_tool_tip)
        self.gain_slider.setToolTip(gain_tool_tip)
        self.gain_label.setToolTip(gain_tool_tip)

        self.pushButtonRecord.setEnabled(False)
        self.pushButtonRecord.clicked.connect(self.start_record)
        self.menuItemAbout.triggered.connect(self.about)
        self.menuItemHelp.triggered.connect(self.acquire_user_guide)
        self.decreaseX.clicked.connect(self.increase_x)
        self.increaseX.clicked.connect(self.decrease_x)
        self.decreaseY.clicked.connect(self.increase_y)
        self.increaseY.clicked.connect(self.decrease_y)
        self.fitY.clicked.connect(self.fit_y)
        
        self.menuConnectionInfo.triggered.connect(self.open_comm_window)
        # todo: testmode (demo) variable name is overloaded with squarewave function
        self.menuItemToggleDemoMode.setChecked(False)
        self.menuItemToggleDemoMode.triggered.connect(self.toggle_demo_mode)
        self.menuItemTestSignalOnAmp.triggered.connect(self.set_amp_test_signal)
        self.initialize_filters()
        
        self.menuItemShowFreq.triggered.connect(self.toggle_freq)
        self.menuItemShowVpp.triggered.connect(self.toggle_vpp)
        self.menuItemShowOffset.triggered.connect(self.toggle_offset)
        self.menuItemShowPowerline.triggered.connect(self.toggle_powerline)
        self.menuItemPower.triggered.connect(self.toggle_power_spectrum)
        self.menuItemGrid.triggered.connect(self.toggle_grid)
        self.menuItemSetPowerlineThreshold.triggered.connect(self.select_powerline_thres)
        self.menuItemShowFreq.setChecked(cfg.freq)
        self.menuItemShowVpp.setChecked(cfg.vpp)
        self.menuItemShowOffset.setChecked(cfg.offset)
        self.menuItemShowPowerline.setChecked(cfg.powerline)
        self.powerline_threshold = cfg.powerline_threshold
        self.menuItemGrid.setChecked(cfg.grid)
        self.menuItemPower.setChecked(cfg.power_spectrum)
        self.menuItemShowFreq.triggered.connect(self.save_file_preferences)
        self.menuItemShowVpp.triggered.connect(self.save_file_preferences)
        self.menuItemShowPowerline.triggered.connect(self.save_file_preferences)
        self.menuItemShowOffset.triggered.connect(self.save_file_preferences)
        self.menuItemPower.triggered.connect(self.save_file_preferences)
        self.menuItemGrid.triggered.connect(self.save_file_preferences)
        self.menuItemSetPowerlineThreshold.triggered.connect(self.save_file_preferences)
        self.actionSelect_Recording_Directory.triggered.connect(self.select_recording_folder)
        self.actionShow_Recording_Folder.triggered.connect(self.show_recording_folder)
        self.actionShow_Camera_dialog.triggered.connect(self.show_camera_settings_dialog)
        self.actionShow_Camera_info.triggered.connect(self.show_camera_info_dialog)
        # microscope related menu items
        # hide for now... until we have some options to put in here
        # maybe connection status / frame rate?, Enable will likely go away
        self.menuMicroscope.menuAction().setVisible(False)
        self.actionShow_Camera_panel.setCheckable(True) # shoule be moved to ui file
        self.actionShow_Camera_panel.triggered.connect(self.toggle_scope_window)
        self.actionShow_Camera_panel.triggered.connect(self.save_file_preferences)
        self.actionShow_Camera_panel.setChecked(cfg.show_scope)

        # for now, no reason to hide EPG panel
        #self.actionShow_EPG_pannel.setVisible(False)

        self.actionShow_EPG_panel.setCheckable(True)
        self.actionShow_EPG_panel.triggered.connect(self.toggle_EPG_window)
        self.actionShow_EPG_panel.triggered.connect(self.save_file_preferences)
        self.actionShow_EPG_panel.setChecked(cfg.show_epg)

        # set state of options from config
        self.pushButtonExpNotes.clicked.connect(self.show_notes)

        # don't have the menu dissappear after changing an option
        self.menuExperiement_Notes_Fields.installEventFilter(self)
        self.menuView.installEventFilter(self)
        self.menuConnection.installEventFilter(self)
        self.statusbar.installEventFilter(self)


        # todo: would be nice to install event filter to consume the delete log text event

        # create labnotes menu options
        self.labnotes_menu_items = [None,] * len(self.cfg.labnotes_items.keys())
        self.labnotes_widgets = [None,] * len(self.cfg.labnotes_items.keys())
        for i, k in enumerate(self.cfg.labnotes_items.keys()):
            self.add_labnotes_menu_item(k, i)

        #create camera settings widget


        self.amp_connected = False # maintain own state so GUI knows when it has changed
        self.powerline_high = False
        self.update_status_label()
        self.lost_data_warning_shown = False
        self.initialize_notes_dialog()
        self.initialize_about_dialog()
        self.initialize_set_powerline_thres_dialog()
        self.update_powerline_thres()
        self.toggle_grid()
        self.toggle_power_spectrum()
        self.toggle_powerline()
        self.toggle_offset()
        self.toggle_vpp()
        self.toggle_freq()
        self.toggle_highpass_filter()
        self.toggle_notch_filter()
        # self.toggle_out_of_band_filter() # by default, don't enable
        self.toggle_scope_window()
        #self.init_roi()
        self.out_of_band_signal = False

        self.fonts = ('Lucida Console','Courier New','MS Sans Serif','Georgia','Arial','Times New Roman','Trebuchet MS','Verdana','Helvetica')
        
        i = 0
        y_axis = 0
        for font in self.fonts:
            g = globals()
            l = locals()
            exec("self.testfont%d = QtGui.QFont('%s', 12)" % (i, font), g, l)
            exec("self.text_test%d = pg.TextItem(text='%s 12pt', anchor=(0,0))" % (i, font), g, l)
            exec("self.text_test%d.setFont(self.testfont%d)" % (i, i), g, l)
            exec("self.graphicsView.addItem(self.text_test%d)" % i, g, l)
            exec("self.text_test%d.setPos(0,%f)" % (i, y_axis), g, l)
            exec("self.text_test%d.hide()" % i, g, l)
            i += 1
            y_axis -= 0.00002
            
        y_axis = 0
        for font in self.fonts:
            g = globals()
            l = locals()   
            exec("self.testfont%d = QtGui.QFont('%s', 12, weight=75)" % (i, font), g, l)
            exec("self.text_test%d = pg.TextItem(text='%s 12pt Bold', anchor=(0,0))" % (i, font), g, l)
            exec("self.text_test%d.setFont(self.testfont%d)" % (i, i), g, l)
            exec("self.graphicsView.addItem(self.text_test%d)" % i, g, l)
            exec("self.text_test%d.setPos(1000,%f)" % (i, y_axis), g, l)
            exec("self.text_test%d.hide()" % i, g, l)
            i += 1
            y_axis -= 0.00002


        self.show_fonts()
 	
        self.recording = False

        if self.cfg.show_fps:
            self.lastTime = time()
            self.fps = None

        self.test_signal_generator = TestWaveGenerator()
        self.samples_queue = SimpleQueue()  # protocol -> GUI
        self.status_queue = SimpleQueue()   # protocol -> GUI
        self.command_queue = SimpleQueue()  # GUI -> protocol
        self.amp_protocol_worker = ReceiveDataWorker(self.display_epg_channel,
	                                                     self.samples_queue,
	                                                     self.status_queue,
	                                                     self.command_queue)
        self.amp_protocol_worker.start() # start looking for amp
        self.samples_rxd = 0
        self.samples_lost = 0
	        
        self.camera_settings_dialog = CameraSettings(self,
                                            self.command_queue,
                                            self.img_cmd_queue,
                                            self.cfg,
                                            self.base_freq)

        self.camera_info_dialog = CameraInfo(self)
        customizeDialogFlags(self.camera_settings_dialog,"Camera Settings")
        #self.camera_settings_dialog.setIconPixmap(QtGui.QPixmap(":/icon/NemaSymbol_scaled.png")) 
        customizeDialogFlags(self.camera_info_dialog,"Camera Information",
                close = True)
        #self.camera_info_dialog.setIconPixmap(QtGui.QPixmap(":/icon/NemaSymbol_scaled.png")) 
        
        #load cfg camera settings data to initialize ui elements
        cfg_camera_settings_dict = {}
        cfg_camera_settings_dict[CamPrm.auto_exp_gain] = cfg.auto_exp_gain
        cfg_camera_settings_dict[CamPrm.exposure] = cfg.exposure_time
        cfg_camera_settings_dict[CamPrm.gain] = cfg.gain
        self.update_camera_settings_ui(cfg_camera_settings_dict)
        
        self.update_dialog = ArdUpdateDialog(self) 

        self.noise_test_dialog = NoiseTestDialog(self)
        customizeDialogFlags(self.noise_test_dialog,u"Noise Test")
        #self.noise_test_dialog.setIconPixmap(QtGui.QPixmap(":/icon/NemaSymbol_scaled.png")) 
        self.menuItemRunNoiseTest.triggered.connect(self.noise_test_dialog.show)

        t = """The numpy and pyqtgraph modules have been imported as 'np' and 'pg'.
 	The nema_main_window is 'n'.\nExample to set amp ch1 input to electrodes:\nn.command_queue.put("wreg 05 50") """
        self.console = console.ConsoleWidget(namespace={'np' : np,
	                                                'pg' : pg,
	                                                'n'  : self},
	                                    text=t)
        if getattr(sys, 'frozen', False):
            data_dir = os.path.dirname(sys.executable)
        else:
            data_dir = ""
            
        shutter_fn = os.path.join(data_dir,"resources/shutter.wav")
        self.shutter_fs, self.shutter_sound = scipy.io.wavfile.read(shutter_fn)
        self.started_amp_recording = False
        self.started_cam_recording = False

    def set_y_width(self,new_width):
        self.y_width = new_width
    def show_fonts(self):
	if self.cfg.fonts == True:
	    i = 0
	    for x in range (0,len(self.fonts)*3):
 	        g = globals()
	        l = locals()
	        exec("self.text_test%d.show()" % i, g, l)
	        i += 1
	                
    def resizeEvent(self, resizeEvent):
        QtGui.QMainWindow.resizeEvent(self, resizeEvent)
        self.position_scale_buttons()  
        self.set_stats_text_position()
        
    def update_exposure(self):
        value = self.exposure_slider.value()
        self.exposure_label.setText("Exposure: " + str(value) + " ms")
        self.img_cmd_queue.put((Command.exposure_setting, value))        
   
    def force_triggered_mode(self):

        #Forcing of triggered mode happens when Nemacquire sees that both camera
        #and amp are connected. New settings command forces a camera reset and
        #and so we need to take care to not have an 'infinite' camera reset
        #behaviour
        if not self.requested_force_triggered_mode:
            if self.camera_settings_dialog.settings_dict[CamPrm.triggered]:
                #If camera has been set to be synchronized at some point,
                #disable forcing of triggered mode as the user should know
                #what they are doing
                self.requested_force_triggered_mode = True
            else:

                self.img_cmd_queue.put((Command.new_settings,{CamPrm.triggered : True }))
                self.requested_force_triggered_mode = True
    
    def update_camera_settings_ui(self, settings_dict):
        #Update ui elements in main window that display or allow modification of camera parameters
        
        if CamPrm.auto_exp_gain in settings_dict:
            auto_exp_gain = settings_dict[CamPrm.auto_exp_gain]
            self.auto_exp_gain_checkBox.stateChanged.disconnect(self.update_auto_exp_gain)
            self.auto_exp_gain_checkBox.setChecked(auto_exp_gain)
            self.auto_exp_gain_checkBox.stateChanged.connect(self.update_auto_exp_gain) 
        
        if CamPrm.exposure in settings_dict:
            #self.exposure_slider.setEnabled(True)
            #self.gain_slider.setEnabled(True)
            exposure = settings_dict[CamPrm.exposure]
            gain = settings_dict[CamPrm.gain]
            self.exposure_slider.valueChanged.disconnect(self.update_exposure)
            self.exposure_slider.setValue(exposure)
            self.exposure_slider.valueChanged.connect(self.update_exposure)
            self.exposure_label.setText("Exposure: " + str(int(round(exposure,0))) + " ms")    
        if CamPrm.gain in settings_dict: 
            self.gain_slider.valueChanged.disconnect(self.update_gain)
            self.gain_slider.setValue(int(gain*self.gain_multiplier))
            self.gain_slider.valueChanged.connect(self.update_gain)
            self.gain_label.setText("Gain: %0.2f db"%gain)

        self.update_camera_controls_enabled()

    def update_auto_exp_gain(self):
        state = self.auto_exp_gain_checkBox.isChecked()
        self.img_cmd_queue.put((Command.auto_exp_gain_setting,state))
        self.update_camera_controls_enabled()

    def update_exposure_maximum(self,max_exp):
        self.exposure_slider.setMaximum(max_exp)
        
    def update_gain(self):
        value = self.gain_slider.value()
        value_actual = value*1.0/self.gain_multiplier
        self.gain_label.setText("Gain: %0.2f db"%value_actual)
        self.img_cmd_queue.put((Command.gain_setting,value_actual))
    

    def update_gain_limits(self,min_gain,increment_gain,max_gain):
        self.gain_slider.setMaximum(max_gain*self.gain_multiplier)
        self.gain_slider.setMinimum(min_gain*self.gain_multiplier)

    def update_status_label(self, amp_firmware_version_string = None):
        if self.camera_connected:
            u_text = "Connected"
        else:
            u_text = "Not detected"

        # handles cases:
        # - where demo on and connect event
        # - connected and demo_mode off event
        if amp_firmware_version_string:
            self.comm_stats_dialog.ui.status_value.setText(amp_firmware_version_string)
        

        if self.demo_mode == True:
            a_text = "Demo mode"
        else:
            if self.amp_connected:
                a_text = "Connected"
            else:
                a_text = "Not detected"
                self.comm_stats_dialog.ui.status_value.setText(a_text)
        s = "Camera status: \nAmplifier status:"
        self.connection_label.setText(s)
        #s = "\t%s\n\t%s" % (u_text, a_text)
        s = " %s\n %s" % (u_text, a_text)
        self.connection_status_label.setText(s)

        if self.demo_mode or self.amp_connected or self.camera_connected:
            self.pushButtonRecord.setEnabled(True)
        else:
            self.pushButtonRecord.setEnabled(False)
             
    def save_labnotes_preferences(self,check_valid_values = False):
        for i, k in enumerate(self.cfg.labnotes_items):
            labnotes_value = self.cfg.labnotes_items[k]
            widget, field = self.labnotes_widgets[i]
            labnotes_value[1] = self.labnotes_menu_items[i].isChecked()
            if k in self.cfg.mandatory_labnotes_items_fields:
                if k in self.cfg.restricted_choices_labnotes_items_fields:
                    if field.currentIndex() > 0:
                        labnotes_value[2] = unicode(field.currentText())
                    else:
                    #Not selected yet
                        if check_valid_values:
                            raise ValueError
                        else:
                            labnotes_value[2] = unicode("")
                else:
                    if not field.text() == "":
                        labnotes_value[2] = unicode(field.text())
                    else:
                        if check_valid_values:
                            raise ValueError
                        else:
                            labnotes_value[2] = unicode("")
            else:
                if k in self.cfg.restricted_choices_labnotes_items_fields:
                    labnotes_value[2] = field.currentText()
                else:
                    labnotes_value[2] = field.text()
            if labnotes_value[1]:
                widget.show()
            else:
                widget.hide()
        self.cfg.save()
        
    def click_close_labnotes(self):
        #print "click_close_labnotes()"
        self.save_labnotes_preferences() # saves any updated values
        # what the save/close button does depends on how it is opened
        self.buttonBoxSave.button(QtGui.QDialogButtonBox.Save).clicked.disconnect()
        self.notes_dialog.close()
        
    def add_labnotes_menu_item(self, field, index):
        menu_item = QtGui.QAction(self)
        menu_item.setCheckable(True)
        menu_item.setChecked(self.cfg.labnotes_items[field][1])
       
        #Some fields are always shown and so we don't allow user to hide them
        if not field in self.cfg.always_shown_labnotes_items_fields:
            self.menuExperiement_Notes_Fields.addAction(menu_item)

        menu_item.setText(self.cfg.labnotes_items[field][0])
        menu_item.triggered.connect(self.save_file_preferences)
        self.labnotes_menu_items[index] = menu_item


    def initialize_set_powerline_thres_dialog(self):
        self.thres_dialog = QtGui.QDialog(parent=self)
        self.thres_dialog.setStyleSheet(self.style_sheet)
        self.thres_dialog.setModal(False)
        customizeDialogFlags(self.thres_dialog,"Set Powerline Noise Threshold")
        self.thres_dialog.setMinimumSize(350,0)
        vLayout = QtGui.QVBoxLayout(self.thres_dialog) 
        hLayout = QtGui.QHBoxLayout()
        vLayout.addLayout(hLayout)
        hLayout.setSpacing(10)
        vLayout.setSpacing(20)   
        
        thres_label_text = u"Powerline Threshold (µV)"
        thres_label = QtGui.QLabel(thres_label_text)
        hLayout.addWidget(thres_label)

        self.thres_set_value = QtGui.QLineEdit(str(self.powerline_threshold))
        self.thres_set_value.setFixedWidth(40)
        validator = QtGui.QIntValidator()
        self.thres_set_value.setValidator(validator)
        hLayout.addWidget(self.thres_set_value)
        
        explTextLabel = QtGui.QLabel("Adjust threshold value above which\npowerline noise warning is always shown")
        explTextLabel.setObjectName('explTextLabel')
        explTextLabel.setStyleSheet(self.style_sheet)
        vLayout.addWidget(explTextLabel)
        
        buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        buttonBox.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self.close_thres_dialog)
        buttonBox.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self.update_powerline_thres)
        buttonBox.button(QtGui.QDialogButtonBox.Cancel).clicked.connect(self.close_thres_dialog)
        vLayout.addWidget(buttonBox)
        
    def update_powerline_thres(self):
        self.powerline_threshold = int(self.thres_set_value.text())
        self.menuItemSetPowerlineThreshold.setText(u"Set Powerline Noise Threshold (µV):  " + str(self.powerline_threshold))
        self.save_file_preferences()
        
    def close_thres_dialog(self): 
        self.thres_dialog.close()

    def initialize_about_dialog(self):
        ''' The About dialog displays copyright and information about the current build.'''
        self.about_dialog = QtGui.QDialog(parent=self)
        self.about_dialog.setStyleSheet(self.style_sheet)
        self.about_dialog.setModal(False)
        customizeDialogFlags(self.about_dialog, "About NemAcquire", close=True)
        
        
        vLayout = QtGui.QVBoxLayout(self.about_dialog)
        vLayout.setSpacing(50)

        graphicLabel = QtGui.QLabel(self.about_dialog)
        graphicLabel.setPixmap(QtGui.QPixmap(":/icon/White_logo_scaled.png"))
        vLayout.addWidget(graphicLabel)

        textLabel = QtGui.QLabel(self.about_dialog)
        s = "NemAcquire 2.1 Alpha\n" + \
                          "Copyright © 2017 NemaMetrix\n" + \
                           "\nBuild date:  \t" + version.build_date + "\n" + \
                           "Build number:  \t" + version.svnversion + "\n" + \
                           "Build machine: \t" + version.build_computer[0] + " " + version.build_computer[2]
        textLabel.setText(QtGui.QApplication.translate("", s, None, QtGui.QApplication.UnicodeUTF8))
        #textLabel.setFont(self.statsfont)
        vLayout.addWidget(textLabel)

    def initialize_notes_dialog(self):
        ''' The Lab Notes Dialog allows a user to append metadata to the recorded file.'''
        self.notes_dialog = QtGui.QDialog(parent=self)
        #self.notes_dialog.setIconPixmap(QtGui.QPixmap(":/icon/NemaSymbol_scaled.png")) 
        self.verticalLayout = QtGui.QVBoxLayout(self.notes_dialog)
        self.notes_dialog.setLayout(self.verticalLayout)
        self.label = QtGui.QLabel(self.notes_dialog)
        customizeDialogFlags(self.notes_dialog, "Enter Experiment Notes")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setText("These notes will be added as metadata to the saved file.")
        additional_notes_label = QtGui.QLabel(self.notes_dialog)
        additional_notes_label.setAlignment(QtCore.Qt.AlignCenter)
        additional_notes_label.setText("Additional fields can be added from File >"
                +" Experiment Notes Fields.")
        self.verticalLayout.addWidget(self.label)
        self.notes_dialog.installEventFilter(self)
        self.warning_widget = QtGui.QWidget()
        self.horizontalLayout_0 = QtGui.QHBoxLayout()
        self.warning_label = QtGui.QLabel(self.notes_dialog)
        self.warning_label.setAlignment(QtCore.Qt.AlignHCenter)
        self.warning_label.setStyleSheet("QLabel { color: red}")
        self.warning_label.setText('WARNING: Data has been lost. The saved file will include discontinuities in data.')
        self.warning_label.hide()
        self.horizontalLayout_0.addWidget(self.warning_label)
        self.warning_widget.setLayout(self.horizontalLayout_0)
        self.verticalLayout.addWidget(self.warning_widget)

        # create widget for all labnotes fields
        for i, k in enumerate(self.cfg.labnotes_items):
            self.create_labnotes_widget(self.cfg.labnotes_items[k], k, i)


        self.labnotes_widgets[self.cfg.labnotes_items.keys().index('notes')][1].setMaxLength(300)
        spacerItem1 = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        spacerItem2 = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        self.verticalLayout.addItem(spacerItem1)
        self.verticalLayout.addWidget(additional_notes_label)
        self.verticalLayout.addItem(spacerItem2)
        self.horizontalLayout_buttonBox = QtGui.QHBoxLayout()
        spacerItem = QtGui.QSpacerItem(300, 20, QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Minimum)
        
        self.buttonBox = QtGui.QDialogButtonBox(self.notes_dialog)
        self.horizontalLayout_buttonBox.addWidget(self.buttonBox)
        self.horizontalLayout_buttonBox.addItem(spacerItem)
        self.buttonBoxSave = QtGui.QDialogButtonBox(self.notes_dialog)
        self.horizontalLayout_buttonBox.addWidget(self.buttonBoxSave)
        
        self.buttonBox.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.addButton(QtGui.QDialogButtonBox.RestoreDefaults)    # Discard Recording
        self.buttonBox.addButton(QtGui.QDialogButtonBox.Reset)              # Clear Values
        self.buttonBox.addButton(QtGui.QDialogButtonBox.Help)               # Revert Values
        self.buttonBoxSave.addButton(QtGui.QDialogButtonBox.Save)
        self.buttonBox.setCenterButtons(False)
        self.verticalLayout.addLayout(self.horizontalLayout_buttonBox)

        self.buttonBox.button(QtGui.QDialogButtonBox.Reset).setText("Clear All")
        self.buttonBox.button(QtGui.QDialogButtonBox.Reset).setMinimumSize(QtCore.QSize(120, 30))
        self.buttonBox.button(QtGui.QDialogButtonBox.Reset).clicked.connect(self.confirm_clear)
        self.buttonBox.button(QtGui.QDialogButtonBox.Help).setText("Revert")
        self.buttonBox.button(QtGui.QDialogButtonBox.Help).setMinimumSize(QtCore.QSize(80, 30))
        self.buttonBox.button(QtGui.QDialogButtonBox.Help).clicked.connect(self.confirm_revert)
        self.buttonBoxSave.button(QtGui.QDialogButtonBox.Save).setDefault(True)
        self.buttonBoxSave.button(QtGui.QDialogButtonBox.Save).setMinimumSize(QtCore.QSize(80, 30))
        self.buttonBox.button(QtGui.QDialogButtonBox.RestoreDefaults).hide()
        self.buttonBox.button(QtGui.QDialogButtonBox.RestoreDefaults).setMinimumSize(QtCore.QSize(160, 30))
        self.buttonBox.button(QtGui.QDialogButtonBox.RestoreDefaults).clicked.connect(self.confirm_discard)
        self.buttonBox.button(QtGui.QDialogButtonBox.RestoreDefaults).setText("Discard Recording")
        
    def create_labnotes_widget(self, values, name, index):
        widget = QtGui.QWidget()
        horizontalLayout = QtGui.QHBoxLayout()
        label = QtGui.QLabel(self.notes_dialog)
        label.setFixedWidth(240)
        horizontalLayout.setContentsMargins(0,0,0,0)
        if name in self.cfg.restricted_choices_labnotes_items_fields:
            #Since there are restricted choices, use a QComboBox

            field = QtGui.QComboBox()
            field.setStyleSheet(self.style_sheet)
            field.addItem("Select")
            for choice in self.cfg.restricted_choices_labnotes_items_fields[name]:
                field.addItem(choice)
            field.setFixedWidth(400)
            field.setCurrentIndex(0)
        
        else:
            field = QtGui.QLineEdit(self.notes_dialog)
            field.setMaxLength(100)
            field.setFixedWidth(400)
            field.setAlignment(QtCore.Qt.AlignLeft)
            field.setText(unicode(values[2])) # values can be ascii strings or integers or floats
        horizontalLayout.addWidget(field)
        horizontalLayout.addWidget(label)
        horizontalLayout.setDirection(QtGui.QBoxLayout.RightToLeft)
        widget.setLayout(horizontalLayout)
        self.verticalLayout.addWidget(widget)
        label.setText(values[0] + ":")
        if name in self.cfg.labnotes_items_tool_tips:
            label.setToolTip(self.cfg.labnotes_items_tool_tips[name])
            field.setToolTip(self.cfg.labnotes_items_tool_tips[name])
        r = (widget, field)
        self.labnotes_widgets[index] = r

            
    def click_save_labnotes(self):
        try:
            if self.started_amp_recording:
                self.save_labnotes_preferences(check_valid_values = True) # save any changes
            else:
                self.save_labnotes_preferences(check_valid_values = False)
        except ValueError:
            # can't have newlines or /n in the text otherwise html tags are
            # not auto-detected properly by the message box
            formatted_message_text = """Select Worm Orientation and Pumping
 Stimulus in Experimental Notes for accurate analysis with
 NemAnalysis.<br><br>Choose Worm Orientation as Follows:<br><ul><li><b>'Head First'</b> if the head of the worm
is closest to the outlet. The fake worm on the screenchip is
 positioned this way.</li><br><li><b>'Tail First'</b> if the tail of
the worm is closest to the outlet.</li></ul>"""
            formatted_message_text = formatted_message_text.replace('\n','')            
            QtGui.QMessageBox.information(self,
                                          self.tr("Set Worm Orientation and Pumping Stimulus"),
                                          self.tr(formatted_message_text),
                                          QtGui.QMessageBox.Ok)
                                          
            return
        try:
            # Write metadata header before closing the file
            metadata = cfg.labnotes_items.copy()  # json requires unicode
            d = self.buf.get_amplifier_settings()
            metadata.update(d)
            l = localtime()
            metadata['date'] = strftime("%Y-%m-%d", l)
            metadata['time'] = strftime("%H:%M:%S", l)
            metadata['svn_version'] = version.svnversion
            metadata['client_computer'] = platform.uname()
            metadata['build_computer'] = version.build_computer
            metadata['with_video'] = self.started_cam_recording
            metadata['with_epg'] = self.started_amp_recording
            if self.started_cam_recording:
                metadata['video_format'] = str(self.video_format)
                metadata['video_fourcc'] = str(self.video_fourcc)
                camera_settings_to_write =\
                self.camera_settings_dialog.settings_dict.copy()
                
                framerate_div = camera_settings_to_write[CamPrm.framerate_div]
                framerate_free = camera_settings_to_write[CamPrm.framerate_free]
                
                #Framerate_div and framerate_free are confusing so we remove it
                #from metadata. The actual framerate of recording is determined
                #and added to the settings to be written
                del camera_settings_to_write[CamPrm.framerate_free]
                del camera_settings_to_write[CamPrm.framerate_div]
                
                #Note that "Unsynchronized Framerate" is the dict key for
                #CamPrm.framerate_free, shouldn't be a problem here since old key was deleted
                camera_settings_to_write["Framerate"] = get_framerate(
                                        camera_settings_to_write[CamPrm.triggered],
                                        self.base_freq,
                                        framerate_div,
                                        framerate_free)

                for k in camera_settings_to_write :
                    metadata[k] = camera_settings_to_write[k]
            if self.started_cam_recording and self.started_amp_recording:
                metadata['time_offset'] = float(self.buf.get_video_time_offset())
                metadata['sample_offset'] =\
                int(self.buf.get_video_sample_offset_raw())
                print 'Time offset between EPG and Video is: ' +\
                str(self.buf.get_video_time_offset())
                if metadata['sample_offset'] == -1 and self.camera_settings_dialog.settings_dict[CamPrm.triggered]:
                    QtGui.QMessageBox.warning(self, "Synchronization not Found",\
                        "Video, EPG synchronization information is invalid. Check amplifier to camera connection.", QtGui.QMessageBox.Ok)
            metadata_json = json.dumps(metadata, encoding="utf-8") # default is UTF-8
            if len(metadata_json) > self.max_metadata_length:
                metadata_json[:self.max_metadata_length]
                QtGui.QMessageBox.warning(self, "Error", \
                                "Metadata length exceeded, will truncate.", QtGui.QMessageBox.Ok)

            recorded_full_fn = self.buf.get_current_full_filename()

            if self.started_amp_recording or self.started_cam_recording:
                self.buf.close_file(metadata_json)

            end_full_fn = get_new_full_filename("nema", "txt", self.cfg)
            if recorded_full_fn != end_full_fn:
                # meta data must have been changed affecting the filename - rename
                os.rename(recorded_full_fn, end_full_fn)
                video_fn = recorded_full_fn[:-4]+'.' + self.video_format
                if os.path.exists(video_fn):
                    os.rename(video_fn, end_full_fn[:-4]+'.'+self.video_format)
                        
            if self.started_amp_recording and self.started_cam_recording:
                log("Closed EPG and video recording with basename: %s" % 
                    end_full_fn[:-4],cache=self.log_cache)
            elif self.started_amp_recording :
                log("Closed EPG recording: %s" % 
                    end_full_fn, cache=self.log_cache)
            elif self.started_cam_recording :
                log("Closed video recording: %s" % 
                    end_full_fn[:-4]+'.' + self.video_format, cache=self.log_cache)

            self.started_amp_recording = False
            self.started_cam_recording = False

            # reset the worm orientation to force user to select on next recording

        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            t = traceback.format_exception(exc_type, exc_value, exc_traceback)
            s = ""
            for l in t:
                s += l
            title = "Exception"
            QtGui.QMessageBox.warning(self,
                                      title,
                                      "There was a problem saving:\n %s" % s,
                                      QtGui.QMessageBox.Ok)
            
        # auto-increment worm number
        worm_number = str(self.cfg.labnotes_items['worm_number'][2])
        if worm_number.isdigit():
            worm_value = int(worm_number) + 1
            self.labnotes_widgets[self.cfg.labnotes_items.keys().index('worm_number')][1].setText(str(worm_value))

        self.revert_mandatory_labnotes_fields()
        self.disable_mandatory_field_check() 
        self.click_close_labnotes()

    def highlight_mandatory_field_if_unselected(self):
        #if self.labnotes_orientation_combobox.currentIndex() == 0:
        #    self.labnotes_orientation_label.setStyleSheet('color: rgb(255,100,100)')     
        #else:
        #    self.labnotes_orientation_label.setStyleSheet(self.style_sheet)

        for k in self.cfg.mandatory_labnotes_items_fields:
            i = self.cfg.labnotes_items.keys().index(k)
            field_widget = self.labnotes_widgets[i][1]
            label_widget = self.labnotes_widgets[i][0]
            if k in self.cfg.restricted_choices_labnotes_items_fields:
                if field_widget.currentIndex() == 0 and self.started_amp_recording:
                    label_widget.setStyleSheet(
                        'color: rgb(255,100,100)')
                else:
                    label_widget.setStyleSheet(self.style_sheet)
            else: 
                if field_widget.text() == "" and self.started_amp_recording:
                    label_widget.setStyleSheet(
                        'color: rgb(255,100,100)')
                else:
                    label_widget.setStyleSheet(self.style_sheet)

    def disable_mandatory_field_check(self):
        for k in self.cfg.mandatory_labnotes_items_fields:
            i = self.cfg.labnotes_items.keys().index(k)
            if k in self.cfg.restricted_choices_labnotes_items_fields:
                self.labnotes_widgets[i][1].currentIndexChanged.disconnect(self.highlight_mandatory_field_if_unselected)
            else:
                self.labnotes_widgets[i][1].textChanged.disconnect(self.highlight_mandatory_field_if_unselected)

    def enable_mandatory_field_check(self):
        for k in self.cfg.mandatory_labnotes_items_fields:
            i = self.cfg.labnotes_items.keys().index(k)
            if k in self.cfg.restricted_choices_labnotes_items_fields:
                self.labnotes_widgets[i][1].currentIndexChanged.connect(self.highlight_mandatory_field_if_unselected)
            else:
                self.labnotes_widgets[i][1].textChanged.connect(self.highlight_mandatory_field_if_unselected)



    def update_camera_connection_view(self):
 
        if self.camera_connected:

            self.actionShow_Camera_panel.setChecked(True)
            self.toggle_scope_window()
            if self.actionShow_EPG_panel.isChecked() and\
                not self.amp_connected:
                self.actionShow_EPG_panel.setChecked(False)
                self.toggle_EPG_window()
        else : 
            pass

    def show_camera_settings_dialog(self):
        self.camera_settings_dialog.setModal(True)
        self.camera_settings_dialog.show()

    def show_camera_info_dialog(self):
        self.camera_info_dialog.show()


    # only called when "Experiment Notes" is clicked - not when stop recording is clicked
    def show_notes(self):
        self.notes_dialog.setModal(False)
        self.save_labnotes_preferences() # updates what is shown from the menu selection
        #self.buttonBoxSave.button(QtGui.QDialogButtonBox.Save).clicked.disconnect(self.click_save_labnotes)
        self.buttonBoxSave.button(QtGui.QDialogButtonBox.Save).clicked.connect(self.click_close_labnotes)
        self.buttonBoxSave.button(QtGui.QDialogButtonBox.Save).setText("Close")
        self.buttonBox.button(QtGui.QDialogButtonBox.RestoreDefaults).hide()
        for k in self.cfg.mandatory_labnotes_items_fields:
            i = self.cfg.labnotes_items.keys().index(k)
            self.labnotes_widgets[i][0].setStyleSheet(self.style_sheet)
        self.notes_dialog.show()
        self.notes_dialog.raise_()

    def update_camera_controls_enabled(self):
        #Any exposure or gain change when recording results in incorrect
        #triggers
        
        if self.recording:
            self.exposure_slider.setEnabled(False)
            self.exposure_label.setEnabled(False)
            self.gain_slider.setEnabled(False)
            self.gain_label.setEnabled(False)
            self.auto_exp_gain_checkBox.setEnabled(False)
        else:
            self.auto_exp_gain_checkBox.setEnabled(True)
            if self.auto_exp_gain_checkBox.isChecked():
                self.exposure_slider.setEnabled(False)
                self.exposure_label.setEnabled(False)
                self.gain_slider.setEnabled(False)
                self.gain_label.setEnabled(False)
            else:
                self.exposure_slider.setEnabled(True)
                self.exposure_label.setEnabled(True)
                self.gain_slider.setEnabled(True)
                self.gain_label.setEnabled(True)

    def capture_static_image(self):
        #print self.bounds
        if self.vb.img_item.qimage is None:
            self.vb.img_item.render()
        
        if self.cfg.roi_enabled and not self.recording:

            q_image = self.vb.img_item.qimage.copy(self.vb.roi_bounds.x,
                                                    self.vb.roi_bounds.y,
                                                    self.vb.roi_bounds.width,
                                                    self.vb.roi_bounds.height)  

            #q_image_mirrored = q_image_cropped.mirrored(False,True)
        else:
            q_image = self.vb.img_item.qimage.copy(self.vb.img_bounds.x,
                                                    self.vb.img_bounds.y,
                                                    self.vb.img_bounds.width,
                                                    self.vb.img_bounds.height)

        full_fn = get_new_full_filename("nema_snapshot", "png", self.cfg)
        full_metadata_fn = get_new_full_filename("nema_snapshot", "txt",
                self.cfg)
        try:

            #Make a new thread to prevent blocking
            save_img_thread = Thread(target = q_image.save, args = (full_fn,))
            save_img_thread.start()
            save_metadata_thread = Thread(target = self.write_image_metadata,
                    args = (full_metadata_fn,))
            save_metadata_thread.start()
            self.vb.startImageCaptureAnimation()
            self.sounddevice.play(self.shutter_sound, self.shutter_fs)
            
        except: 
            exc_type, exc_value, exc_traceback = sys.exc_info()
            t = traceback.format_exception(exc_type, exc_value, exc_traceback)
            s = ""
            for l in t:
                s += l
                title = "Exception"
            QtGui.QMessageBox.warning(self,
                                      title,
                                      "There was a problem saving:\n %s" % s,
                                      QtGui.QMessageBox.Ok)
        else :    
            log('Saved snapshot: %s' % full_fn, cache=self.log_cache)

    def write_image_metadata(self,fn):

        with open(fn, 'w') as image_metadata_file:
            
            metadata = cfg.labnotes_items.copy()  # json requires unicode
            d = self.buf.get_amplifier_settings()
            metadata.update(d)
            l = localtime()
            metadata['date'] = strftime("%Y-%m-%d", l)
            metadata['time'] = strftime("%H:%M:%S", l)
            metadata['svn_version'] = version.svnversion
            metadata['client_computer'] = platform.uname()
            metadata['build_computer'] = version.build_computer
            metadata['is_image'] = True
            #metadata['with_video'] = self.started_cam_recording
            #metadata['with_epg'] = self.started_amp_recording
            #if self.started_cam_recording:
            metadata['video_format'] = str(self.video_format)
            metadata['video_fourcc'] = str(self.video_fourcc)
            camera_settings_to_write =\
            self.camera_settings_dialog.settings_dict.copy()
            
            framerate_div = camera_settings_to_write[CamPrm.framerate_div]
            framerate_free = camera_settings_to_write[CamPrm.framerate_free]
            
            #Framerate_div and framerate_free are confusing so we remove it
            #from metadata. The actual framerate of recording is determined
            #and added to the settings to be written
            del camera_settings_to_write[CamPrm.framerate_free]
            del camera_settings_to_write[CamPrm.framerate_div]
            
            #Note that "Unsynchronized Framerate" is the dict key for
            #CamPrm.framerate_free, shouldn't be a problem here since old key was deleted
            camera_settings_to_write["Framerate"] = get_framerate(
                                    camera_settings_to_write[CamPrm.triggered],
                                    self.base_freq,
                                    framerate_div,
                                    framerate_free)

            for k in camera_settings_to_write :
                metadata[k] = camera_settings_to_write[k]
            metadata_json = json.dumps(metadata, encoding="utf-8") # default is UTF-8
            image_metadata_file.write(metadata_json)

    
    def enable_capture_button(self):

        self.pushButtonImage.setEnabled(True)
        self.animation_finished_signal.disconnect(self.enable_capture_button)

    def play_camera_shutter_sound(self):
        pass
        #self.shutter_sound.play()

    def clear_labnotes(self):
        for i, k in enumerate(self.cfg.labnotes_items):
            if k in self.cfg.restricted_choices_labnotes_items_fields:
                self.labnotes_widgets[i][1].setCurrentIndex(0)
            else:
                self.labnotes_widgets[i][1].setText('')
    
    def revert_mandatory_labnotes_fields(self):
        for k in self.cfg.mandatory_labnotes_items_fields:
            if k == "pumping_stimulus":
                #Don't revert pumping stimulus
                continue
            labnotes_str = str(self.cfg.labnotes_items[k][2])
            i = self.cfg.labnotes_items.keys().index(k)
            if k in self.cfg.restricted_choices_labnotes_items_fields:
                self.labnotes_widgets[i][1].setCurrentIndex(0)
            else:
                self.labnotes_widgets[i][1].setText("")

    def revert_labnotes(self):
        for i, k in enumerate(self.cfg.labnotes_items):
            labnotes_str = str(self.cfg.labnotes_items[k][2])
            if k in self.cfg.restricted_choices_labnotes_items_fields:
                choices = self.cfg.restricted_choices_labnotes_items_fields[k]
                try:
                    index = choices.index(labnotes_str)
                    self.labnotes_widgets[i][1].setCurrentIndex(index+1)
                except:
                    self.labnotes_widgets[i][1].setCurrentIndex(0)
            else:
                self.labnotes_widgets[i][1].setText(labnotes_str)
                """
                if labnotes_str == "H":
                    self.labnotes_widgets[i][1].setCurrentIndex(1)
                elif labnotes_str == "T":
                    self.labnotes_widgets[i][1].setCurrentIndex(2)
                else:
                    self.labnotes_widgets[i][1].setCurrentIndex(0)
            else:
                self.labnotes_widgets[i][1].setText(labnotes_str)
                """
        
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonRelease:
            if isinstance(obj, QtGui.QMenu): #if obj is self.menuExperiement_Notes_Fields
                if obj.activeAction():
                    obj.activeAction().trigger()
                    return True
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key == QtCore.Qt.Key_Escape:
                if self.notes_dialog.isModal():
                    #print "caught ESC"
                    self.confirm_discard()
                    return True
                else:
                    #print "caught ESC"
                    self.clicked_close_labnotes()
                    return True
        return False

    def keyPressEvent(self, ev):
        key = ev.key()
        if key == QtCore.Qt.Key_Slash:
            if self.console.isVisible():
                self.console.hide()
            else:
                self.console.show()
        if key == QtCore.Qt.Key_O:
            self.toggle_out_of_band_filter()
        if key == QtCore.Qt.Key_I:
            if self.out_of_band_signal:
                self.command_queue.put("wreg 0f 00")
                self.command_queue.put("wreg 10 00")
                self.out_of_band_signal = False
            else:
                self.command_queue.put("wreg 04 03")
                self.command_queue.put("wreg 0f 10")
                self.command_queue.put("wreg 10 10")
                self.out_of_band_signal = True
        #Only for key automation !
        #if key == QtCore.Qt.Key_S:
        #    if self.recording :
        #        self.stop_record()
        #        sleep(0.5) 
        #        self.click_save_labnotes()
        #    else :
        #        self.start_record()
        
    def confirm_clear(self):
        choice = QtGui.QMessageBox.warning(self, "Clear Experiment Notes", "Are you sure you want to clear the experiment note fields?", QtGui.QMessageBox.Ok, QtGui.QMessageBox.Cancel)
        if choice == QtGui.QMessageBox.Ok:
            self.clear_labnotes()
            
    def confirm_revert(self):
        choice = QtGui.QMessageBox.warning(self, "Revert to Previous Value", "Are you sure you want to revert the fields to their saved values?", QtGui.QMessageBox.Ok, QtGui.QMessageBox.Cancel)
        if choice == QtGui.QMessageBox.Ok:
            self.revert_labnotes()
     
    def confirm_discard(self):
        discard = QtGui.QMessageBox.warning(self, "Discard Recording", "If you continue, the last recording will not be saved. Continue?", QtGui.QMessageBox.Ok, QtGui.QMessageBox.Cancel)
        if discard == QtGui.QMessageBox.Ok:
            if self.started_amp_recording : 
                self.started_amp_recording = False

            if self.started_cam_recording:
                self.started_cam_recording = False

            self.buttonBoxSave.button(QtGui.QDialogButtonBox.Save).clicked.disconnect()

            self.disable_mandatory_field_check()
            self.notes_dialog.close()
            self.buf.discard_recording()
            log("Discarded recording",cache=self.log_cache)   
            self.img_cmd_queue.put((Command.discard_recording,None))
            self.revert_mandatory_labnotes_fields()
            
            
    def verify_rec_folder(self):
        if not os.path.isdir(self.cfg.recording_folder):
            QtGui.QMessageBox.warning(self, "Directory Reset", 
                "The current recording directory is not a valid location. The location of saved files has been reset to the desktop. Use File > Select Recording Folder to change this location.", 
                QtGui.QMessageBox.Ok)
            self.cfg.recording_folder = os.path.expanduser(os.path.join('~', 'Desktop'))
            self.cfg.save()
            
    def select_recording_folder(self):
        self.verify_rec_folder()     
        recording_folder = QtGui.QFileDialog.getExistingDirectory(dir=self.cfg.recording_folder,
                                                                  options= QtGui.QFileDialog.ShowDirsOnly)
                                                                
        # handles 'cancel case' by not changing existing folder
        if recording_folder: 
            self.cfg.recording_folder = recording_folder
            self.cfg.save()

    def show_recording_folder(self):
        self.verify_rec_folder()
        d = self.cfg.recording_folder
        if sys.platform=='win32':
            subprocess.Popen(['explorer', d], shell=True)
        elif sys.platform=='darwin':
            subprocess.Popen(['open', d])
        else:
            subprocess.Popen(['xdg-open', d])
            
    def toggle_ROI_view(self):
        self.vb.stateUpdate(State.toggle_view_state)

    def video_view_callback(self, state):
        if state == State.roi_view :
            self.pushButtonROI.setEnabled(True)
            self.pushButtonImage.setEnabled(True)
            self.pushButtonROI.setText("Zoom out")

        elif state == State.full_view : 
            self.pushButtonROI.setEnabled(True)
            self.pushButtonImage.setEnabled(True)
            self.pushButtonROI.setText("Zoom in")
        elif state == State.recording_full_view:
            self.pushButtonImage.setEnabled(True)
            self.pushButtonROI.setEnabled(False)
        else:
            self.pushButtonImage.setEnabled(False)
            self.pushButtonROI.setEnabled(False)

    def toggle_scope_window(self):
        if self.actionShow_Camera_panel.isChecked():
            self.graphicsLayoutWidget.addItem(self.image_layout, row=0, col=0)
            self.graphicsView.setFixedHeight(300)
        else:
            qt_revert_fixed_size(self.graphicsView)
            self.graphicsLayoutWidget.removeItem(self.image_layout)
        self.set_stats_text_position()

    def toggle_EPG_window(self):
        if self.actionShow_EPG_panel.isChecked():
            self.graphicsLayoutWidget.addItem(self.layout,row = 1, col=0)
            self.decreaseX.setVisible(True)
            self.increaseX.setVisible(True)
            self.decreaseY.setVisible(True)
            self.increaseY.setVisible(True)
            self.fitY.setVisible(True)
            self.filter_label.setVisible(True)
            self.notch_comboBox.setVisible(True)
            self.highpass_comboBox.setVisible(True)

        else:
            self.graphicsLayoutWidget.removeItem(self.layout)
            self.decreaseX.setVisible(False)
            self.increaseX.setVisible(False)
            self.decreaseY.setVisible(False)
            self.increaseY.setVisible(False)
            self.fitY.setVisible(False)
            self.filter_label.setVisible(False)
            self.notch_comboBox.setVisible(False)
            self.highpass_comboBox.setVisible(False)
        self.set_stats_text_position()
        
    def position_scale_buttons(self):
        graph_size = self.graphicsView.geometry()
        y_bottom_postion = self.graphicsLayoutWidget.height()-(self.buttonHeight)
        if self.power_spectrum:
            y_bottom_postion = y_bottom_postion-self.power_spectrum.height()
        self.decreaseY.move(graph_size.width()-(self.buttonHeight*0.1), y_bottom_postion-(self.buttonHeight)-(self.buttonHeight*0.2)) 
        self.increaseY.move(graph_size.width()-(self.buttonHeight*0.1), y_bottom_postion-(self.buttonHeight)*2-(self.buttonHeight*0.2)*2) 
        self.fitY.move(graph_size.width()-(self.buttonHeight*0.1), y_bottom_postion-(self.buttonHeight)*3-(self.buttonHeight*0.2)*3)
        self.increaseX.move(graph_size.width()-(self.buttonHeight*1.1), y_bottom_postion)
        self.decreaseX.move(graph_size.width()-(self.buttonHeight*2.3), y_bottom_postion)
            
    def open_comm_window(self):
        self.comm_stats_dialog.show()
        self.comm_stats_dialog.raise_()

    def toggle_power_spectrum(self):
        gradient = QtGui.QLinearGradient(0, 0, 150, 0)
        gradient.setColorAt(0, QtGui.QColor.fromRgbF(0, 1, 0, 1))
        gradient.setColorAt(0.03, QtGui.QColor.fromRgbF(1, 1, 0, 1))
        gradient.setColorAt(0.3, QtGui.QColor.fromRgbF(1, 0, 0, 1))
        gradient.setColorAt(0.7, QtGui.QColor.fromRgbF(0, 0, 1, 1))
        gradient.setColorAt(1, QtGui.QColor.fromRgbF(0, 0, 0, 0))

        self.brush = QtGui.QBrush(gradient)
        if self.menuItemPower.isChecked():
            self.power_spectrum = self.layout.addPlot(row=2, col=0, enableMouse=False, enableMenu=False, background=None)
            self.power_spectrum.setMouseEnabled(False,False)
            self.power_spectrum_plot = self.power_spectrum.plot()
            self.power_spectrum.setMaximumHeight(100)
            self.power_spectrum.setLabel('bottom', "Frequency", units='Hz', **self.labelStyle)
            self.power_spectrum.setLabel('left', "Power", units=None, unitPrefix=None, **self.labelStyle)
            self.power_spectrum.getAxis('left').enableAutoSIPrefix(False)
            self.power_spectrum.setXRange(0, 125, padding=0)
        else: 
            if self.power_spectrum:
                self.layout.removeItem(self.layout.getItem(row=2, col=0))
            self.power_spectrum = None
            self.power_spectrum_plot = None
        app.processEvents()
        self.position_scale_buttons()
        self.set_stats_text_position()
        
    def toggle_grid(self):
        if self.menuItemGrid.isChecked():
            self.graphicsView.showGrid(True,True,0.6) 
        else:
            self.graphicsView.showGrid(False,False,0.6)

    #def update_display_channel(self):
    #    channel = self.channel_comboBox.currentIndex() + 1
    #    print ("updated display channel to %d" % channel)
    #    self.cfg.display_epg_channel = channel
    #    self.cfg.save()

    def initialize_filters(self):

        if self.cfg.highpass:
            self.highpass_comboBox.setCurrentIndex(1)
        if self.cfg.notch_60Hz:
            self.notch_comboBox.setCurrentIndex(1)
        if self.cfg.notch_50Hz:
            self.notch_comboBox.setCurrentIndex(2)
        
        self.highpass_comboBox.currentIndexChanged.connect(self.toggle_highpass_filter)
        self.highpass_comboBox.currentIndexChanged.connect(self.save_file_preferences)
        self.notch_comboBox.currentIndexChanged.connect(self.toggle_notch_filter)
        self.notch_comboBox.currentIndexChanged.connect(self.save_file_preferences)
    
    def toggle_highpass_filter(self):
        if self.highpass_comboBox.currentIndex() == 1:
            self.buf.enable_highpass_filter(True)
        else:
            self.buf.enable_highpass_filter(False)
        
    def toggle_notch_filter(self):
        if self.notch_comboBox.currentIndex() == 1:     
            self.buf.enable_notch_filter(True, 60)
        elif self.notch_comboBox.currentIndex() == 2:
            self.buf.enable_notch_filter(True, 50)
        else:
            self.buf.enable_notch_filter(False)
            
    def toggle_out_of_band_filter(self):
        if self.buf.out_of_band_filter == None:
            self.buf.enable_out_of_band_filter(True, 125)
        else:
            self.buf.enable_out_of_band_filter(False)

    def toggle_freq(self):
        if self.menuItemShowFreq.isChecked():
            self.freq_text_label.show()
            self.freq_text_value.show()
        else:
            self.freq_text_label.hide()
            self.freq_text_value.hide()
        self.set_stats_text_position()
            
    def toggle_offset(self):
        if self.menuItemShowOffset.isChecked(): 
            self.offset_text_label.show()
            self.offset_text_value.show()
        else:
            self.offset_text_label.hide()
            self.offset_text_value.hide()
                
    def toggle_powerline(self):
        if self.powerline_high : #Override checked setting if powerline is too high
            self.powerline_text_label.setStyleSheet('color: rgb(255,76,76)')
            self.powerline_text_value.setStyleSheet('color: rgb(255,76,76)')
            self.powerline_text_label.show()
            self.powerline_text_value.show() 
        elif self.menuItemShowPowerline.isChecked(): 
            self.powerline_text_label.setStyleSheet('color: rgb(255,255,255)') 
            #set color to white, refer to a config stylesheet value?
            self.powerline_text_value.setStyleSheet('color: rgb(255,255,255)')
            self.powerline_text_label.show()
            self.powerline_text_value.show()
        else:
            self.powerline_text_label.hide()
            self.powerline_text_value.hide()
        

    def toggle_vpp(self):
        if self.menuItemShowVpp.isChecked():
            self.vpp_text_label.show()
            self.vpp_text_value.show()
        else:
            self.vpp_text_label.hide()
            self.vpp_text_value.hide()

    def set_amp_test_signal(self):
        if self.menuItemTestSignalOnAmp.isChecked():
            cmd_str = get_input_square_wave_command_string(self.display_epg_channel)
            self.command_queue.put(cmd_str)
        else:
            cmd_str = get_input_normal_command_string(self.display_epg_channel)
            self.command_queue.put(cmd_str)

    def save_file_preferences(self):
        self.cfg.vpp = self.menuItemShowVpp.isChecked()
        self.cfg.freq = self.menuItemShowFreq.isChecked()
        self.cfg.offset = self.menuItemShowOffset.isChecked()
        self.cfg.powerline = self.menuItemShowPowerline.isChecked()
        self.cfg.powerline_threshold = self.powerline_threshold
        self.cfg.grid = self.menuItemGrid.isChecked()
        self.cfg.power_spectrum = self.menuItemPower.isChecked()
        self.cfg.show_scope = self.actionShow_Camera_panel.isChecked()
        if self.highpass_comboBox.currentIndex() == 1:
            self.cfg.highpass = True
        else:
            self.cfg.highpass = False
        if self.notch_comboBox.currentIndex() == 1:     
            self.cfg.notch_50Hz = False
            self.cfg.notch_60Hz = True
        elif self.notch_comboBox.currentIndex() == 2:
            self.cfg.notch_50Hz = True
            self.cfg.notch_60Hz = False
        else:
            self.cfg.notch_50Hz = False
            self.cfg.notch_60Hz = False
        self.save_labnotes_preferences()
        self.cfg.save()
        
    def save_recording_preferences(self):    
        self.cfg.unixTime = self.actionUnixTime.isChecked()
        self.cfg.channel_2 = self.actionChannel2.isChecked()
        self.cfg.channel_3 = self.actionChannel3.isChecked()
        self.cfg.channel_4 = self.actionChannel4.isChecked()
        self.cfg.channel_5 = self.actionChannel5.isChecked()
        self.cfg.channel_6 = self.actionChannel6.isChecked()
        self.cfg.channel_7 = self.actionChannel7.isChecked()
        self.cfg.channel_8 = self.actionChannel8.isChecked()
        self.cfg.save()
        
    def toggle_demo_mode(self):
        if self.menuItemToggleDemoMode.isChecked():
            assert self.demo_mode == False
            if self.amp_connected == True:
                choice = QtGui.QMessageBox.warning(self,
                                                   "Enable demo mode",
                                                   "Amp is connected. Are you sure you want to start off-line demo mode?",
                                                   QtGui.QMessageBox.Ok,
                                                   QtGui.QMessageBox.Cancel)
                if choice == QtGui.QMessageBox.Cancel:
                    self.menuItemToggleDemoMode.setChecked(False)
                    return
            self.demo_mode = True
            self.test_signal_generator.start()
        else:            
            assert self.demo_mode == True
            self.demo_mode = False
            self.test_signal_generator.stop()
        self.update_status_label()

    def show_amp_connected_dialog(self):
        
        s1 = u"""<b>Welcome!</b><br><br>
Before you start, remember:
<ul>
<li><b>Run a noise test</b> before loading a worm. This will ensure the ScreenChip system is correctly setup and ready for recording.<br></li>
<li>If you are not using a pump stimulus, such as food or serotonin (5-HT), wild type (N2) worms will pump <b>sporadically at less than once per second on average.<br></li>
</ul>
Noise tests can be run at any time from the menu:<br>
Amplifier>Run Noise Test<br><br>
Would you like to run a noise test now?
"""
        msgbox = QtGui.QMessageBox(QtGui.QMessageBox.Information,
                                   u"Amp Connected",
                                   s1,
                                   parent=self)
        
        msgbox.setText(s1)
        run_noise_test_msgbox_button = msgbox.addButton(QtGui.QMessageBox.Yes)
        run_noise_test_msgbox_button.clicked.connect(self.noise_test_dialog.show)
        msgbox.addButton(QtGui.QMessageBox.No)
        # workaround to prevent model dialog (it's nice to see the data and not drop data)
        msgbox.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        customizeDialogFlags(msgbox,u"Amp Connected")
        msgbox.show()
    
   

    # self.amp_connected is only changed here
    def _change_in_connection_status(self, connected_b, version_string = None,
            updating = False,failed_connection_attempt = False):
        
        #updating does not result in a change to amp_connected
        #first AmpStatus from update has updating = true and connection False
        #second AmpStatus has updating = False and the connection state wouldn't
        #have changed
        #TODO make this into a separate signal
        if failed_connection_attempt:
            QtGui.QMessageBox.warning(self,
                        "Amplifier firmware update failed", 
                        "Nemacquire is reattempting Amplifier firmware update.\nIf problem persists, try connecting to a different USB port",
                        QtGui.QMessageBox.Ok)
            log("Amplifier detection/upload failed",cache=self.log_cache)
            if self.update_dialog.isVisible():
                self.update_dialog.close()
                self.update_dialog.loading_qmovie.stop()
            return
            
        if updating: 
            self.update_dialog.show()
            self.update_dialog.loading_qmovie.start()
        else: 
            if self.amp_connected == connected_b:
                self.update_dialog.hide()

        if connected_b:
            #Send the framerate command as soon as possible 
            #to prevent dropped data errors on windows
            div = self.cfg.framerate_div
            send_framerate_cmd(self.command_queue,div)
            # quit demo if enabled
            if self.demo_mode:
                # do these things rather than calling toggle_demo_mode to avoid
                # update_status_label being called more than once
                self.demo_mode = False
                self.test_signal_generator.stop()
                self.menuItemToggleDemoMode.triggered.disconnect(self.toggle_demo_mode)
                self.menuItemToggleDemoMode.setChecked(False)
                self.menuItemToggleDemoMode.triggered.connect(self.toggle_demo_mode)
            self.amp_connected = True
            self.update_status_label(version_string)
            self.samples_lost = 0 
            self.samples_rxd = 0
            if not self.actionShow_EPG_panel.isChecked():
                self.actionShow_EPG_panel.setChecked(True)
                self.toggle_EPG_window()
            # amp initializes to electrodes, so change if needed
            if self.menuItemTestSignalOnAmp.isChecked():
                cmd_str = get_input_square_wave_command_string(self.display_epg_channel)
                self.command_queue.put(cmd_str)
            else:
                self.show_amp_connected_dialog()
           

            if self.camera_connected:
                self.force_triggered_mode()
        
        else:
            # change connect button to show 'connect'
            self.amp_connected = False
            if not self.camera_connected:
                self.pushButtonRecord.setEnabled(False)
            self.update_status_label()
            if self.recording:
                self.stop_record()
            self.lost_data_warning_shown = False
            self.w_left.clear()
            self.w_right.clear()
            if self.power_spectrum_plot:
                self.power_spectrum_plot.setData((0,),(0,),stepMode=False)


    def update(self):
        if self.vid_source_control == 4:
            img = None
            ret = False
            with self.shared_image_array.get_lock():
                img_shape =\
                np.array(self.shared_image_array.get_obj()[:3])
                flat_img =\
                np.frombuffer(self.shared_image_array.get_obj(),dtype="uint16")
            if img_shape[0] != 0:

                #Not RGB 
                if img_shape[2] != 3:
                    size_img = img_shape[0]*img_shape[1]
                    img = np.reshape(flat_img[3:size_img+3],img_shape[:2])
                else:
                    
                    size_img = img_shape[0]*img_shape[1]*img_shape[2]
                    img = np.reshape(flat_img[3:size_img+3],img_shape[:3])
                    img = cv2.cvtColor(img,cv2.COLOR_RGB2BGR)
                ret = True

            #img = self.test_full_img
            #ret = True    
        elif self.vid_source_control == 2: 
            img = self.test_full_img
            ret = True
            
        elif self.vid_source_control == 3:
            self.cam.get_image(self.img)
            img = self.img.get_image_data_numpy()
            ret = True
        else:
            ret,img = self.cam.read()

        if ret:
            #If recieving full image from camera then crop it. Otherwise, camera only captures in desired ROI.
            #Additional shape check required to prevent race condition when camera started recording but nemacquire hasn't
            #recieved notification yet
            if self.cfg.roi_enabled and img.shape[1] == 2048 and img.shape[0] == 1088 :
                pass                    

            self.vb.setImage(img) 

        self.vb.processAnimation()    

        while not self.status_queue.empty():
            
            amp_status = self.status_queue.get()
            self._change_in_connection_status(amp_status.connected,
                    amp_status.firmware_version, amp_status.updating,amp_status.failed_connection_attempt)


        while not self.img_status_queue.empty():
            
            status,data = self.img_status_queue.get()

            if status is Command.camera_connected:
                self.camera_settings_dialog.button_save.clicked.connect(self.vb.setResetCameraMessage)
                self.camera_connected = True
                self.update_status_label()
                self.update_camera_connection_view()
                self.pushButtonRecord.setEnabled(True)
                #print "camera connected !"
                log("Camera connected",cache=self.log_cache)
                self.vb.stateUpdate(State.last_view_state)
                if self.amp_connected:
                    self.force_triggered_mode()
            elif status is Command.camera_disconnected:
                self.camera_info_dialog.reset()
                self.camera_settings_dialog.button_save.clicked.disconnect(self.vb.setResetCameraMessage)
                self.camera_connected = False
                self.update_status_label()
                self.update_camera_connection_view()
                log("Camera disconnected", cache=self.log_cache)
                if not self.amp_connected :
                    self.pushButtonRecord.setEnabled(False)
                if self.recording:
                    self.stop_record()
                    QtGui.QMessageBox.warning(self,
                        "Disconnected while recording", 
                        "Check camera connection, data has been saved up till disconnection",
                        QtGui.QMessageBox.Ok)
                    log("Camera disconnected while recording!",cache=self.log_cache)
                self.vb.stateUpdate(State.no_camera_connected)
            elif status is Command.first_frame_timestamp:
                self.buf.timestamp_dict[-1] = data
            elif status is Command.dropped_frames:
                print "dropped frames !"
                if not self.dropped_video_frames_while_recording:
                    QtGui.QMessageBox.warning(self,
                            "Dropped Video Frames", 
                            self.dropped_frame_error_text, 
                            QtGui.QMessageBox.Ok)
                log("Frames dropped, reduce framerate",cache=self.log_cache)
                self.dropped_video_frames_while_recording = True
            elif status is Command.info_update:
                self.camera_info_dict = data
                self.camera_info_dialog.updateValues(*data[CamPrm.connection_info])
            elif status is Command.limit_update:
                self.camera_settings_dialog.updateLimits(data)
                self.update_exposure_maximum(data[CamPrm.exposure][2])
                self.update_gain_limits(*data[CamPrm.gain])
            elif status is Command.settings_update:
                #print data
                self.camera_settings_dialog.update_camera_settings_ui(data)
                self.update_camera_settings_ui(data)

                #During recording we don't want this to be logged
                if not self.recording:
                    log("Camera Settings Updated",cache=self.log_cache)

            elif status is Command.trig_error: 
                if not self.dropped_video_frames_while_recording:
                    QtGui.QMessageBox.warning(self,
                            "Dropped Video Frames", 
                            self.dropped_frame_error_text,
                            QtGui.QMessageBox.Ok)
                log("Frames dropped, reduce framerate",cache=self.log_cache)
                self.dropped_video_frames_while_recording = True
            elif status is Command.timeout_error_triggered:
                if self.camera_settings_dialog.isVisible():
                    self.timeout_warning_dialog = TimeoutWarningDialog(self.camera_settings_dialog)
                    self.timeout_warning_dialog.setWindowModality(QtCore.Qt.WindowModal)
                else:
                    self.timeout_warning_dialog = TimeoutWarningDialog(self)
                customizeDialogFlags(self.timeout_warning_dialog,"Camera not grabbing frames")
                #self.timeout_warning_dialog.setWindowModality(QtCore.Qt.WindowModal)
                self.timeout_warning_dialog.show()
                log("Camera not being triggered",cache=self.log_cache)
            elif status is Command.opened_video:
                if self.started_amp_recording:
                    log("Started camera and EPG recording with basename: %s" %
                    self.buf.get_current_full_filename()[:-4],cache=self.log_cache)
                else:
                    log("Started camera recording with basename: %s"%
                    self.buf.get_current_full_filename()[:-4],cache=self.log_cache)
            elif status is Command.cannot_open_video:
                self.dropped_video_frames_while_recording = True
                QtGui.QMessageBox.warning(self,
                        "Cannot open video file",
                        "Cannot open video file, " +
                        "EPG will continue to record",
                        QtGui.QMessageBox.Ok)
                log("Cannot open video file",cache=self.log_cache)
            elif status is Command.clear_timeout_error:
                log("",cache=self.log_cache)
            elif status is Command.auto_exp_gain_settings_update:
                #print "updated settings"
                self.update_camera_settings_ui(data)
                self.camera_settings_dialog.update_camera_settings_ui(data)
            elif status is Command.video_frames_missing:
                QtGui.QMessageBox.warning(self,
                        "Some frames absent in video",
                        "Video file lacks some frames",
                        QtGui.QMessageBox.Ok)
                self.warning_label.show()
        # retrieve new data from amp, if available
        while not self.samples_queue.empty():
            sample_data = self.samples_queue.get()
            #print exposure_starts
            if isinstance( sample_data, ( int, long )):
                # this is actually a samples lost notification
                self.samples_lost += sample_data
            else:
                values, timestamp, exposure_starts = sample_data
                if not self.demo_mode:
                    # only use the data if not in demo_mode
                    self.buf.add_samples(values,timestamp,exposure_starts)
                self.samples_rxd += len(values)

        if self.demo_mode:
            values = self.test_signal_generator.get_values()
            if len(values) > 0:
                self.buf.add_samples(values,time(),[])
            
        if self.log_cache.last_displayed_message != self.log_cache.last_log_message:
            self.statusbar.showMessage(self.log_cache.last_log_message, 0)
            self.log_cache.last_displayed_message = self.log_cache.last_log_message

        next_point, y = self.buf.get_data()
        if next_point != self.prev_point:
            if next_point < self.prev_point:
                # the buffer has wrapped
                if self.buf.highpass_filter:
                    self.offset_correction(0)
                else:
                    self.offset_correction(self.buf.pre_filter_offset)
            x1 = np.arange(next_point)
            x2 = np.arange(next_point + self.leading_samples, self.samples_to_display)
            self.w_left.setData(x1, y[:next_point], pen=self.plot_color)
            self.w_right.setData(x2, y[next_point + self.leading_samples:], pen=self.plot_color)

            # fft graph
            if self.power_spectrum:
                if len(self.buf.fft_data) > 0:
                    self.power_spectrum_plot.setData(self.buf.fft_x, self.buf.fft_data,
                                                     stepMode = True, fillLevel=0,
                                                     brush=self.brush)
            # reduces efficiency but neccessary on OS X to avoid stale data displayed
            self.graphicsLayoutWidget.resetCachedContent()
        self.prev_point = next_point                
                
        if self.samples_lost > 0 and not self.lost_data_warning_shown:
            QtGui.QMessageBox.warning(self, "Lost Data", "Some data has been lost. Please check the amplifier connection before continuing.", QtGui.QMessageBox.Ok)
            self.lost_data_warning_shown = True

        if self.comm_stats_dialog.isVisible():
            self.comm_stats_dialog.ui.samples_rxd.setText(str(self.samples_rxd))
            self.comm_stats_dialog.ui.samples_lost.setText(str(self.samples_lost))

        y_min, y_max = self.graphicsView.viewRange()[1]
        if self.menuItemShowFreq.isChecked():
            if self.buf.dominant_freq == 0:
                freq_value_s = "        "
            else:
                freq_value_s = "%3.2f" % self.buf.dominant_freq
            # left justify label and have minimum two spaces after : on longest string
            self.freq_text_value.setText(freq_value_s)

        if self.noise_test_dialog.isVisible():
            self.noise_test_dialog.updateVpp(self.buf.vpp)
            
        if self.menuItemShowVpp.isChecked():
            # handle microvolts
            if abs(self.buf.vpp) < 0.001:
                vpp_label_s = u"Amplitude (µV):"
                vpp_value_s = "%3d" % (self.buf.vpp*1000000)
            # handle millivolts
            else:
                vpp_label_s = u"Amplitude (mV):"
                vpp_value_s = "%3.2f" % (self.buf.vpp*1000)
            self.vpp_text_label.setText(vpp_label_s)
            self.vpp_text_value.setText(vpp_value_s)
            self.vpp_text_value.adjustSize()

        if self.powerline_high != (abs(self.buf.powerline_noise_V) >
                self.powerline_threshold*0.000001) :
            self.powerline_high = not self.powerline_high
            self.toggle_powerline()
        if self.menuItemShowPowerline.isChecked() or self.powerline_high:
            if abs(self.buf.powerline_noise_V) < 0.001:
                 powerline_label_s = u"Powerline Noise (µV):"     
                 powerline_value_s = "%3d" % (self.buf.powerline_noise_V*1000000)
            # handle millivolts
            else:
                powerline_label_s = u"Powerline Noise (mV):"
                powerline_value_s = "%3.2f" % (self.buf.powerline_noise_V*1000)
            self.powerline_text_label.setText(powerline_label_s)
            self.powerline_text_value.setText(powerline_value_s)
            self.powerline_text_value.adjustSize()

        if self.menuItemShowOffset.isChecked():
            # handle microvolts
            if abs(self.buf.pre_filter_offset) < 0.001:
                offset_label_s = u"Offset (µV):"
                offset_value_s = "%3d" % (self.buf.pre_filter_offset*1000000)
            # handle millivolts
            else:
                offset_label_s = u"Offset (mV):"
                offset_value_s = "%3.2f" % (self.buf.pre_filter_offset*1000)
            self.offset_text_label.setText(offset_label_s)
            self.offset_text_value.setText(offset_value_s)
            self.offset_text_value.adjustSize()

        if self.recording:
            self.elapsed_time_label.setText("Elapsed time:")
            self.elapsed_time_label.setStyleSheet('color: rgb(255,76,76)')
            elapsed_seconds = time() - self.start_record_time
            m, s = divmod(elapsed_seconds, 60)
            h, m = divmod(m, 60)
            
            self.elapsed_time_text.setText("%02d:%02d:%02d" % (h, m, s))
            self.elapsed_time_text.setStyleSheet('color: rgb(255,76,76)')
        else:
            self.elapsed_time_label.setText("")
            self.elapsed_time_text.setText("")

        if self.cfg.show_fps:
            now = time()
            dt = now - self.lastTime
            self.lastTime = now
            if self.fps is None:
                self.fps = 1.0/dt
            else:
                s = np.clip(dt*3., 0, 1)
                self.fps = self.fps * (1-s) + (1.0/dt) * s
                self.graphicsView.setTitle('%0.2f fps' % self.fps, **self.labelStyle)
    
    def start_record(self):
        
        assert(self.started_amp_recording == False)
        assert(self.started_cam_recording == False)
        try:
            self.verify_rec_folder()
            self.buf.start_recording()
            self.dropped_video_frames_while_recording = False
            if self.amp_connected or self.demo_mode:
                self.started_amp_recording = True
            if self.camera_connected :
                self.vb.stateUpdate(State.started_recording)
                if self.cfg.roi_enabled:
                    self.recording_bounds = [self.vb.roi_bounds.x, 
                                             self.vb.roi_bounds.x +
                                             self.vb.roi_bounds.width,
                                             self.vb.roi_bounds.y,
                                             self.vb.roi_bounds.y + 
                                             self.vb.roi_bounds.height]
                    #print self.recording_bounds
                else :
                    self.recording_bounds = [0, 2048, 0, 1088]
                     
                self.img_cmd_queue.put((
                    Command.record,(
                    self.buf.get_current_full_filename()[:-4]+'.' + self.video_format,
                    self.video_fourcc,
                    self.recording_bounds)))
                self.started_cam_recording = True

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            t = traceback.format_exception(exc_type, exc_value, exc_traceback)
            s = ""
            for l in t:
                s += l
            title = "Exception"
            QtGui.QMessageBox.warning(self,
                                      title,
                                      "There was a problem starting recording:\n %s" % s,
                                      QtGui.QMessageBox.Ok)
            log("Problem starting recording",cache=self.log_cache)
            
        else:

            self.camera_settings_dialog.recording_event(True)
            self.pushButtonRecord.setText("Stop Recording") 
            self.pushButtonRecord.clicked.disconnect(self.start_record)
            self.pushButtonRecord.clicked.connect(self.stop_record)
            self.rec_text.setText("Recording")
            self.rec_text.setStyleSheet('color: rgb(255,76,76)')
            self.plot_color = self.recording_red
            self.plot_shadow = (255,255,255)
            self.start_record_time = time()
            self.samples_lost_count_at_start_record = self.samples_lost
            self.recording = True
            if self.started_cam_recording:
                if self.camera_settings_dialog.settings_dict[CamPrm.triggered]:
                    sync_state = "Synchronized "
                else:
                    sync_state = "Unsynchronized "
                vid_rec_text = sync_state +\
                        "Video : Display at %3d fps; Recording at %0.6f fps" %\
                (self.camera_info_dict[CamPrm.display_freq], 
                self.camera_info_dict[CamPrm.record_freq])
                self.video_fps_text.setText(vid_rec_text)
                self.video_fps_text.setStyleSheet('color: rgb(255,76,76)')
                self.video_fps_text.show()
                self.video_fps_text.adjustSize()
            self.set_stats_text_position()
            self.update_camera_controls_enabled()
            if not self.started_cam_recording:
                log("Opened EPG recording: %s" %
                    self.buf.get_current_full_filename(),cache=self.log_cache)

            
    def stop_record(self):
        self.camera_settings_dialog.recording_event(False)
        self.save_labnotes_preferences() 
        if self.camera_connected:            
            self.img_cmd_queue.put((Command.stop_record, None))
        self.buf.stop_recording()
        self.video_fps_text.hide()
        self.rec_text.setText("Not Recording")
        self.rec_text.setStyleSheet('color: rgb(200,200,200)')
        self.plot_color = (255,255,255)
        self.recording = False
        if self.started_cam_recording:
            self.vb.stateUpdate(State.stopped_recording)
        # modal lab notes dialog
        self.buttonBoxSave.button(QtGui.QDialogButtonBox.Save).setText("Save")
        self.buttonBoxSave.button(QtGui.QDialogButtonBox.Save).clicked.connect(self.click_save_labnotes)
        self.highlight_mandatory_field_if_unselected()
        self.enable_mandatory_field_check()
        # todo: need to disconnect .currentIndexChanged!!!!! 
        self.buttonBox.button(QtGui.QDialogButtonBox.RestoreDefaults).show()
        self.notes_dialog.setModal(True)
        self.setEnabled(False) # grey out main window
        # must hide then show to get change in modality to occur if was previously open
        self.notes_dialog.setEnabled(True)
        self.notes_dialog.hide()
        
        if self.samples_lost > self.samples_lost_count_at_start_record or\
                self.dropped_video_frames_while_recording:
            self.warning_label.show()
        else:
            self.warning_label.hide()
        
        self.dropped_video_frames_while_recording = False
        self.notes_dialog.show()
         
        # revert UI
        self.update_camera_controls_enabled()
        self.pushButtonRecord.setText("Record")
        self.pushButtonRecord.clicked.disconnect(self.stop_record)
        self.pushButtonRecord.clicked.connect(self.start_record)
        self.setEnabled(True) # restore main window
        

    
    def closeEvent(self,event):
        if self.recording == True:
            result = QtGui.QMessageBox.question(self, 
                "Recording in Progress - Confirm Exit",
                "A recording is in progress. Data will be lost if you exit. Are you sure you want to exit?",
                 QtGui.QMessageBox.Yes| QtGui.QMessageBox.No)
            if result == QtGui.QMessageBox.Yes:
                if self.started_amp_recording:
                    self.buf.stop_recording()
                    self.buf.discard_recording()
                    self.started_amp_recording = False
            else:
                event.ignore()
                return
        # close comms window
        self.comm_stats_dialog.close()
        
        self.img_cmd_queue.put((Command.terminate, None))
        event.accept()


    def about(self):
        self.about_dialog.show()
        self.about_dialog.raise_()
    
    def select_powerline_thres(self):
        self.thres_set_value.setText(str(self.powerline_threshold))
        self.thres_dialog.show()
        self.thres_dialog.raise_()
            
    def acquire_user_guide(self):
        acquire_pdf = os.path.join(self.base, "NemAcquireUserGuide.pdf")
        if sys.platform == 'win32':
            os.startfile(acquire_pdf)
        elif sys.platform == 'darwin':
            os.system("open " + acquire_pdf)
        else:
            subprocess.call(["xdg-open", acquire_pdf])
        
    def decrease_x(self):
        y_min, y_max = self.graphicsView.viewRange()[1]
        if self.samples_to_display > self.minimum_samples_to_display: 
            self.decreaseX.setEnabled(True)
            self.samples_to_display /= 2
            self.buf.set_buffer_size(self.samples_to_display)
            self.graphicsView.setXRange(0,self.samples_to_display, padding=0)
            x_min, x_max = self.graphicsView.viewRange()[0]
            self.update_x_label()
        if self.samples_to_display == self.minimum_samples_to_display:
            self.increaseX.setEnabled(False)
        self.set_stats_text_position()
                    
    def increase_x(self):
        y_min, y_max = self.graphicsView.viewRange()[1]
        if self.samples_to_display < self.maximum_samples_to_display:  
            self.increaseX.setEnabled(True)
            self.samples_to_display *= 2
            self.buf.set_buffer_size(self.samples_to_display)
            self.graphicsView.setXRange(0,self.samples_to_display, padding=0)
            x_min, x_max = self.graphicsView.viewRange()[0]
            self.update_x_label()
        if self.samples_to_display == self.maximum_samples_to_display:
            self.decreaseX.setEnabled(False)
        self.set_stats_text_position()
            
    def update_x_label(self):
        s = 'Time: %dsec Total (1sec / division)' % (self.samples_to_display/self.buf.sample_rate)
        self.graphicsView.setLabel('bottom', s, **self.labelStyle)

    # adjust text position
    def set_stats_text_position(self):
        # four lines for stats:
        # 1: white space
        # 2: Amplitude, Recording, EPG Hz
        # 3: white space
        # 4: Offset, Elapsed time, EPG Value*
        # * EPG Value is its own style
        
        # update() schedules a paint event to process correct image_view_layout size
        # processEvents() executes the scheduled paint event
        #print "in set_stats"
        self.graphicsLayoutWidget.update()
        app.processEvents()
        
        if self.actionShow_Camera_panel.isChecked():
            graph_top_position = self.image_layout.height()
        else:
            graph_top_position = 0

        vertical_buffer = self.rec_text.height()/4
        horizontal_buffer = self.fitY.size().width()+self.graphicsView.getAxis('left').width()
        
        line_one_pos = graph_top_position+self.pushButtonRecord.height()
        line_two_pos = vertical_buffer+self.rec_text.height()+line_one_pos
        line_three_pos = vertical_buffer + self.rec_text.height() + line_two_pos
        
        EPG_graph_width = self.graphicsView.width()-self.graphicsView.getAxis('right').width()
        self.freq_text_label.move(EPG_graph_width-self.freq_text_label.width(), self.freq_text_value.height()+line_one_pos)
        self.freq_text_value.move(EPG_graph_width-self.freq_text_value.width(), line_one_pos)  
                 
        self.vpp_text_label.move(horizontal_buffer, line_one_pos)
        self.vpp_text_value.move(horizontal_buffer+self.powerline_text_label.sizeHint().width(), line_one_pos)
        self.offset_text_label.move(horizontal_buffer, line_two_pos)
        self.offset_text_value.move(horizontal_buffer+self.powerline_text_label.sizeHint().width(), line_two_pos)
        self.powerline_text_label.move(horizontal_buffer,line_three_pos)
        self.powerline_text_value.move(horizontal_buffer+self.powerline_text_label.sizeHint().width(), line_three_pos)

        self.elapsed_time_label.move(self.graphicsView.width()/2-self.elapsed_time_label.width()/2, 0)
        self.elapsed_time_text.move(self.graphicsView.width()/2+self.elapsed_time_label.width()/2, 0)
        self.video_fps_text.move(self.graphicsView.width()/2-self.video_fps_text.width()/2+self.elapsed_time_text.width()/2,self.elapsed_time_label.height())
        self.rec_text.move(self.graphicsView.width()/2, line_one_pos)

    def offset_correction(self, offset):
        y_min, y_max = self.graphicsView.viewRange()[1]
        # ajust for offset, offset value should be midpoint  
        y_range = y_max - y_min
        y_max = offset + y_range/2
        y_min = offset - y_range/2
        self.graphicsView.setYRange(y_min, y_max, padding=0)

    # halve the y range about the center
    def decrease_y(self):
        y_min, y_max = self.graphicsView.viewRange()[1]
        y_range = y_max - y_min
        center = y_range / 2 + y_min
        y_min = center - y_range/4
        y_max = center + y_range/4
        # limit y-axis zoom-in to 20 uV
        if y_max-y_min > 0.00002:
            self.graphicsView.setYRange(y_min, y_max, padding=0)

    # double the y range about the center
    def increase_y(self):
        y_min, y_max = self.graphicsView.viewRange()[1]
        y_range = y_max - y_min
        center = y_range / 2 + y_min
        y_min = center - y_range
        y_max = center + y_range
        # limit y-axis zoom-out to 1V
        if y_max-y_min < 1:
            self.graphicsView.setYRange(y_min, y_max, padding=0)

    def fit_y(self):

        y_min_left, y_max_left = self.w_left.dataBounds(1)
        y_min_right,y_max_right = self.w_right.dataBounds(1)

        if y_min_left is None or y_max_left is None:
            y_min = y_min_right
            y_max = y_max_right
        elif y_min_right is None or y_max_right is None:
            y_min = y_min_left
            y_max = y_max_left
        else:
            y_max = max(y_max_left,y_max_right)
            y_min = min(y_min_left,y_min_right)
        #y_max = self.buf.post_filter_offset+(self.buf.vpp/2)
        #y_min = self.buf.post_filter_offset-(self.buf.vpp/2)
        
        if y_min is None or y_max is None:
            return
        if y_max-y_min > 0.00002 :
            # padding is fractional, e.g. .50 = 50%
            self.graphicsView.setYRange(y_min, y_max, padding=.50)
        else:
            center = self.buf.post_filter_offset
            self.graphicsView.setYRange(center-0.00001, center+0.00001)


# crude simple unit test, fail is if exception is generated
def run_cfg_unit_test():
    cfg = NemaConfig()
    # since the cfg values are class static attributes we need to save
    temp = cfg.labnotes_items['species'][2]
    cfg.labnotes_items['species'][2] = u""" a b c ':";°C1234567890~`!@#$%^&*()-_=+ /.,<>';:][{} | \\"""
    nema_main_window = NemaMainWindow(cfg)
    # put back the default value, in case no config and need the default value
    cfg.labnotes_items['species'][2] = temp
            
if __name__ == "__main__":
    #logger = log_to_stderr()
    #logger.setLevel(logging.INFO)
    freeze_support() # otherwise app continuouslys open in Windows
    img_queue = SimpleQueue()        # video R/W -> GUI for display of live image
    shared_image_array = Array('h',3+2048*1088*3)
    img_cmd_queue = SimpleQueue()    # GUI -> video R/W
    img_status_queue = SimpleQueue() # video R/W -> GUI
    
    vid_process = VideoProcess(img_queue,
                               img_cmd_queue,
                               img_status_queue,
                               shared_image_array)
    vid_process.start()

    # must create now because cfg exceptions will raise dialog boxes
    app = QtGui.QApplication(sys.argv)

    # run_cfg_unit_test() running on Mac causing native window to not display properly
    cfg = NemaConfig()
    try:
        cfg.load()
    except (ConfigParser.ParsingError, ConfigParser.NoOptionError, ConfigParser.NoSectionError, ValueError) as e:
        if type(e)  == ConfigParser.NoOptionError:
            title = "No Option"
        elif type(e) == ConfigParser.ParsingError:
            title = "Parsing"
        elif type(e) == ConfigParser.NoSectionError:
            title = "No Section"
        elif type(e) == ValueError:
            title = "Value"
        else:
            title = "Unknown"
        bad_config_msg = QtGui.QMessageBox.information(None,
                                                       title,
                                                       "Could not load the nema_config.txt configuration file - likely due to a NemAcquire update. It will be renamed to 'nema_config_backup.txt' and a new configuration file will be created. Previous settings may revert to their default values. Press OK to continue.\n\nDetails: %s" % e,
                                                       QtGui.QMessageBox.Cancel,
                                                       QtGui.QMessageBox.Ok)     
        if bad_config_msg == QtGui.QMessageBox.Cancel:
            QtGui.QMessageBox.information(None,
                                          title,
                                          "No changes made. Exiting.",
                                          QtGui.QMessageBox.Ok)
            exit()
        else:
            # backup and rename current config
            if os.path.isfile(os.path.join(cfg.cfg_path, "nema_config_backup.txt")):
                os.remove(os.path.join(cfg.cfg_path, "nema_config_backup.txt"))  # if a prior backup exists
            os.rename(os.path.join(cfg.cfg_path, "nema_config.txt"), os.path.join(cfg.cfg_path, "nema_config_backup.txt"))
            cfg.load()  # calling load again to create default config file 

    nema_main_window = NemaMainWindow(img_queue, img_cmd_queue,
            img_status_queue, shared_image_array, cfg)
    nema_main_window.show()
    nema_main_window.position_scale_buttons()
    nema_main_window.set_stats_text_position()
    nema_main_window.set_stats_text_position()
    timer = QtCore.QTimer()
    timer.timeout.connect(nema_main_window.update)
    timer.start(40) # 25 fps
    app.exec_()
    nema_main_window.amp_protocol_worker.terminate()
    vid_process.terminate()

