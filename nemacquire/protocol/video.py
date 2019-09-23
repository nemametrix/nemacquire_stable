from multiprocessing import Process, Array,log_to_stderr
from multiprocessing.queues import SimpleQueue, Queue
import cv2
import sys
import time
import logging
import frameutils as fu
import numpy as np
import os
import cProfile
import traceback

def get_framerate(triggered, base_freq, framerate_div, framerate_free):
    if triggered:
        return (base_freq*1.0) / 2**framerate_div
    else:
        return framerate_free #TODO link to cfg number

"""
 Recording Workflow : 

Image Display Workflow : 
  
    Always going on, sends images to display queue after a
    period that can be different depending on whether nemacquire is recording or
    not. No checks on whether all frames are displayed. TODO may need to flush
    queue

Camera disconnects/connects : Process relays information to main thread and
stop recording if it is happening

Camera settings: 1. Initialized with cfg data 2. When new settings are
recieved, camera is closed and opened again
3. A verification dictionary is sent. 

Synchronization: Only first video frame and first EPG sample is timestamped.

Video Frame is timestamped with the timer on the camera, which is ensured to be
synced whenever a recording is started

Every frame has a timestamp and a frame counter, we use both to ensure that
there are no skipped frames or frames with an incorrect time between frames

Note: we assume that the encoder can ALWAYS write frames
"""

#Copy values from all keys in dict_2
def dict_copy(dict_1,dict_2):
    for k in dict_2:
        try:
            dict_1[k] = dict_2[k]
        except:
            raise ValueError

class Command():
    """ Enumeration of commands exchanged between GUI and videowriter process"""

    #Handled by VideoProcess  
    terminate = 0
    record = 1
    stop_record = 2
    discard_recording = 3
    filename = 4
    new_settings = 5
    exposure_setting = 6
    gain_setting = 7
    auto_exp_gain_setting = 8

    #Sent by VideoProcess
    camera_disconnected = 10
    camera_connected = 11
    first_frame_timestamp = 12
    dropped_frames = 13
    info_update = 14
    limit_update = 15
    settings_update = 16
    trig_error = 17
    exposure_error = 18
    opened_video = 19
    cannot_open_video = 20
    timeout_error_generic = 21
    timeout_error_triggered = 22
    clear_timeout_error = 23
    auto_exp_gain_settings_update = 24
    video_frames_missing = 25

class CamPrm():
    """Enumeration of camera parameters"""
    framerate_free = 'Unsynchronized Framerate'
    exposure = 'Exposure (ms)'
    framerate_div = 'Synchronized Framerate'
    buf_size = 'Buffer Size'
    offset_y = 'Offset Y'
    height = 'Recording Height'
    triggered = 'Synchronized'
    white_balance = 'White Balance'
    gain = 'Gain (db)'
    auto_exp_gain = "Auto Exposure/Gain"
    connection_info = "Connection Info."
    display_freq = "Display fps"
    record_freq = "Record fps"
class VideoProcess(Process):

    def __init__(self, img_queue, cmd_queue, status_queue,shared_image_array):
        
        Process.__init__(self)
        self.shared_image_array = shared_image_array
        self.video_fourcc = 'H264' #Default
        self.zero_offset = 0
        self.base_freq = 250
        self.cmd_queue = cmd_queue
        self.img_queue = img_queue
        self.status_queue = status_queue
        self.limit_dict = {}
        self.connected = False
        self.record = False
        self.filename = ''
        self.bounds = []
        self.first_frame = False
        self.img_write_queue = None
        self.settings = {}
        self.settings[CamPrm.white_balance] = False
        self.vid_writer = None

    def send_exp_and_gain_update(self):
        cur_settings_dict = {}
        cur_settings_dict[CamPrm.auto_exp_gain] =\
                self.cam.get_param(self.xiapi.XI_PRM_AEAG)
        cur_settings_dict[CamPrm.gain]=\
                self.cam.get_param(self.xiapi.XI_PRM_GAIN)
        cur_settings_dict[CamPrm.exposure]=\
                self.cam.get_param(self.xiapi.XI_PRM_EXPOSURE)/1000.0
        
        self.status_queue.put((Command.auto_exp_gain_settings_update,cur_settings_dict))
        dict_copy(self.settings,cur_settings_dict)

    def verify_settings(self):

        cur_settings_dict = {}


        cur_settings_dict[CamPrm.buf_size] =\
        int(self.cam.get_buffers_queue_size())

        cur_settings_dict[CamPrm.framerate_div] = self.settings[CamPrm.framerate_div]
        trg_src = self.cam.get_trigger_source()
        if trg_src is 'XI_TRG_OFF':
            cur_settings_dict[CamPrm.triggered] = False
        elif trg_src is 'XI_TRG_EDGE_RISING':
            cur_settings_dict[CamPrm.triggered] = True
        else:
            raise ValueError
        cur_settings_dict[CamPrm.white_balance] =\
        self.cam.get_param(self.xiapi.XI_PRM_AUTO_WB) 

        cur_settings_dict[CamPrm.framerate_free] =\
        self.cam.get_param(self.xiapi.XI_PRM_FRAMERATE) 

        cur_settings_dict[CamPrm.auto_exp_gain] =\
                self.cam.get_param(self.xiapi.XI_PRM_AEAG)
        cur_settings_dict[CamPrm.gain] =\
                self.cam.get_param(self.xiapi.XI_PRM_GAIN)
        cur_settings_dict[CamPrm.exposure] =\
                self.cam.get_exposure()/1000.0
        cur_settings_dict[CamPrm.offset_y] = self.cam.get_offsetY() 
        dict_copy(self.settings,cur_settings_dict)
        self.info_dict[CamPrm.record_freq] = self._get_framerate()
        self.status_queue.put((Command.settings_update, cur_settings_dict))

 
    def update_limits(self):
        
        self.limit_dict = {}

        self.limit_dict[CamPrm.framerate_free] = (
                        self.cam.get_framerate_minimum(),
                        self.cam.get_framerate_increment(),
                        self.cam.get_framerate_maximum())

        exposure_max = 1000.0/self._get_framerate()
        exposure_max = int(exposure_max) - 1
        self.limit_dict[CamPrm.exposure] = ( 
                        self.cam.get_exposure_minimum()/1000,
                        self.cam.get_exposure_increment()/1000,
                        exposure_max)

        self.limit_dict[CamPrm.buf_size] = (   
                            self.cam.get_buffers_queue_size_minimum(),
                            self.cam.get_buffers_queue_size_increment(),
                            self.cam.get_buffers_queue_size_maximum())


        self.limit_dict[CamPrm.offset_y] = (
                            self.cam.get_offsetY_minimum(),
                            self.cam.get_offsetY_increment(),
                            self.cam.get_offsetY_maximum())

        self.limit_dict[CamPrm.height] = (
                            self.cam.get_height_minimum(),
                            self.cam.get_height_increment(),
                            self.cam.get_height_maximum())

        self.limit_dict[CamPrm.gain] = (
                            self.cam.get_gain_minimum(),
                            self.cam.get_gain_increment(),
                            self.cam.get_gain_maximum())
        self.status_queue.put((Command.limit_update, self.limit_dict))
                
                
    def updateEstimatedLimits(self):
        self.limit_dict = {}
        self.limit_dict[CamPrm.exposure] = (1, 0 , int(1000.0/self._get_framerate()))
        
        self.limit_dict[CamPrm.framerate_free] = (
                        1,
                        1,
                        100)


        self.limit_dict[CamPrm.buf_size] = (   
                            1,
                            1,
                            20)


        self.limit_dict[CamPrm.offset_y] = (
                            0,
                            1,
                            1088)

        self.limit_dict[CamPrm.height] = (
                            0,
                            1,
                            1088)

        self.limit_dict[CamPrm.gain] = (
                            -1.5,
                            0.1
                            ,3)

        self.status_queue.put((Command.limit_update, self.limit_dict))
                
    def init_camera(self,cam):
        self.timeout_error_counter = 0
        self.timeout_error_sent = False
        self.info_dict[CamPrm.connection_info][1] = 0
        self.info_dict[CamPrm.connection_info][2] = 0
        
        if self.record: 
            self.stop_record()
        
        try: #Attempt to set parameters.  
            cam.set_param(self.xiapi.XI_PRM_GPO_MODE,'XI_GPO_OFF')
            cam.set_param(self.xiapi.XI_PRM_RECENT_FRAME,0)
            self.isColor = cam.get_param(self.xiapi.XI_PRM_IMAGE_IS_COLOR)
             
            if self.isColor: 
                cam.set_param(self.xiapi.XI_PRM_IMAGE_DATA_FORMAT,'XI_RGB24')

                #Ignore white balance if it is not a color camera
                if self.settings[CamPrm.white_balance]:
                    cam.set_param(self.xiapi.XI_PRM_AUTO_WB,1)
                else :
                    cam.set_param(self.xiapi.XI_PRM_AUTO_WB,0)
            else : 
                cam.set_param(self.xiapi.XI_PRM_IMAGE_DATA_FORMAT,'XI_MONO8')
            
            cam.set_param(self.xiapi.XI_PRM_EXPOSURE, 500)
            cam.set_param(
                    self.xiapi.XI_PRM_ACQ_TIMING_MODE,
                    'XI_ACQ_TIMING_MODE_FRAME_RATE')
            #print self.settings[CamPrm.framerate_free]
            try:
                cam.set_param(self.xiapi.XI_PRM_FRAMERATE,float(self.settings[CamPrm.framerate_free]))
            except:
                self.logger.info(traceback.format_exc())
                self.logger.info("Reconnect Camera")

            
            #Handle amp triggered or software triggered setting
            if self.settings[CamPrm.triggered]:
                
                cam.set_param(self.xiapi.XI_PRM_TRG_SOURCE,'XI_TRG_EDGE_RISING')
                cam.set_param(self.xiapi.XI_PRM_GPI_MODE,'XI_GPI_TRIGGER')
                

            #Handle auto exposure/gain and manual exposure/gain settings 
            if self.settings[CamPrm.auto_exp_gain]:

                max_exp_ms = int(1000.0/self._get_framerate())
            
                if max_exp_ms > 1:
                    max_exp_ms -= 1
                cam.set_param(self.xiapi.XI_PRM_AE_MAX_LIMIT, max_exp_ms*1000)
                cam.set_param(self.xiapi.XI_PRM_AEAG,1)

            else:
                if cam.get_param(self.xiapi.XI_PRM_AEAG) == 0:
                    
                    cam.set_param(self.xiapi.XI_PRM_AEAG,0)
                    #Set exposure. If settings contains an exposure value that exceeds the framerate, we 
                    #set a smaller exposure period
                    exposure_to_set = min(int(self.settings[CamPrm.exposure]*1000),
                                                int((1.0/self._get_framerate())*1000*1000)) #maximum exposure in micros
                    cam.set_param(self.xiapi.XI_PRM_EXPOSURE,exposure_to_set)
                    cam.set_param(self.xiapi.XI_PRM_GAIN,self.settings[CamPrm.gain])
                    
            cam.set_param(self.xiapi.XI_PRM_COUNTER_SELECTOR,'XI_CNT_SEL_API_SKIPPED_FRAMES')
             
            #This is the most fickle setting and is done last so that an exception here doesn't affect anything else
            cam.set_param(self.xiapi.XI_PRM_BUFFERS_QUEUE_SIZE,30) 

        except self.xiapi.Xi_error as e:
               
            #Invalid parameter supplied (error codes defined in xidefs.py in XIMEA library)
            if e.status == 11:
                self.logger.info("Wrong parameter values. Setting to reasonable values")
            
            self.logger.info(traceback.format_exc())
        except :
            self.logger.info(traceback.format_exc())
             
        finally:
            tpf = cam.get_param(self.xiapi.XI_PRM_TRANSPORT_PIXEL_FORMAT)
            self.bpp = self.xiapi.XI_GenTL_Image_Format_e[tpf].value
            self.bwl = int(cam.get_param(self.xiapi.XI_PRM_LIMIT_BANDWIDTH))
            cam.set_param(self.xiapi.XI_PRM_GPO_MODE,'XI_GPO_OFF')

            self.update_limits()
            self.update_disp_period()
        
    def set_exposure_time(self,exposure_time):
        if self.connected:
            try:
                #self.cam.set_param(self.xiapi.XI_PRM_AEAG,0)
                self.cam.set_param(self.xiapi.XI_PRM_EXPOSURE,
                #self.cam.set_exposure(
                        int(exposure_time*1000))

            except self.xiapi.Xi_error as err:

                if err.status == 40:
                    self.logger.error("Error setting exposure time !")
            finally:
                self.update_limits()
                self.verify_settings()
        else: 
            settings_dict = {}
            settings_dict[CamPrm.gain] = self.settings[CamPrm.gain]
            settings_dict[CamPrm.auto_exp_gain] = self.settings[CamPrm.auto_exp_gain]
            settings_dict[CamPrm.exposure] = exposure_time
            self.settings[CamPrm.exposure] = exposure_time
            self.updateEstimatedLimits()
            self.status_queue.put((Command.settings_update, settings_dict))

    def set_gain(self,gain):
        if self.connected:
            try: 
                self.cam.set_param(self.xiapi.XI_PRM_GAIN
                        ,gain)
                #self.cam.set_param(self.xiapi.XI_PRM_AEAG,0)

            except self.xiapi.Xi_error as err:

                if err.status == 40:
                    self.logger.error("Error setting gain !")
            finally:
                self.update_limits()
                self.verify_settings()
        else:
            settings_dict={}
            settings_dict[CamPrm.gain] = gain
            self.settings[CamPrm.gain] = gain
            settings_dict[CamPrm.exposure] = self.settings[CamPrm.exposure]
            settings_dict[CamPrm.auto_exp_gain] = self.settings[CamPrm.auto_exp_gain]
            self.updateEstimatedLimits()
            self.status_queue.put((Command.settings_update, settings_dict))

    def set_auto_exp_gain(self,value):
        if self.connected:
            try:
                if value:
                    max_exp_ms = int(1000.0/self._get_framerate())     
                    if max_exp_ms > 1:
                        max_exp_ms -= 1
                    self.cam.set_param(self.xiapi.XI_PRM_AE_MAX_LIMIT, max_exp_ms*1000)
                    self.cam.set_param(self.xiapi.XI_PRM_AEAG,1)
                else:
                    self.cam.set_param(self.xiapi.XI_PRM_AEAG,0)
                    self.cam.set_param(self.xiapi.XI_PRM_GAIN, self.settings[CamPrm.gain])
                    self.cam.set_param(self.xiapi.XI_PRM_EXPOSURE,
                           int(self.settings[CamPrm.exposure]*1000))

            except self.xiapi.Xi_error as err:

                if err.status == 40:
                    self.logger.error("Error setting auto_exposure_gain !")
            finally:
                self.update_limits()
                self.verify_settings()
        else:
            settings_dict={}
            settings_dict[CamPrm.gain] = self.settings[CamPrm.gain]
            settings_dict[CamPrm.exposure] = self.settings[CamPrm.exposure]
            settings_dict[CamPrm.auto_exp_gain] = value
            self.settings[CamPrm.auto_exp_gain] = value
            self.updateEstimatedLimits()
            self.status_queue.put((Command.settings_update, settings_dict))

    # convienence method
    def _get_framerate(self):
        return get_framerate(self.settings[CamPrm.triggered],
                             self.base_freq,
                             self.settings[CamPrm.framerate_div],
                             self.settings[CamPrm.framerate_free])

    def update_disp_period(self):
        #Display frames are sampled with a width of disp_period
        #disp_period is set to be as close as possible to the
        #desired frequency.

        if self.record :
            desired_freq = self.disp_fps_record
        else :
            desired_freq = self.disp_fps_free

        disp_period = int(round(self._get_framerate()/desired_freq,0))

        if disp_period <= 0 :
            disp_period = 1


        self.logger.debug("disp_period is %d",disp_period)
        
        #This is the only function allowed to modify display settings and 
        #info is only updated here
        
        self.info_dict[CamPrm.display_freq] =\
                int(self._get_framerate()/disp_period)

        self.disp_period = disp_period
        self.disp_counter = 0
            
    @staticmethod
    def constraint_dim(cur_dim,min_dim,max_dim,inc_dim):

        cur_dim = cur_dim - cur_dim % inc_dim
        
        if cur_dim < min_dim:
            cur_dim = min_dim

        elif cur_dim > max_dim:
            cur_dim = max_dim

        return cur_dim

        
    def set_camera_bounds(self):
        
        assert self.bounds[1] <= 2048
        assert self.bounds[3]  <= 1088
       
        assert self.bounds[2] < self.bounds[3]
        assert self.bounds[0] < self.bounds[1]

        self.bounds = list(self.bounds)
        #self.logger.info(self.bounds)
        width_max = self.cam.get_width_maximum()
        width_min = self.cam.get_width_minimum()
        width_increment = self.cam.get_width_increment()
        width_to_set = int(self.bounds[1] - self.bounds[0])
        width_to_set = VideoProcess.constraint_dim(width_to_set,
                                            0,
                                            2048,
                                            width_increment)
    
        height_max = self.cam.get_height_maximum()
        height_min = self.cam.get_height_minimum()
        height_increment = self.cam.get_height_increment()
        height_to_set = int(self.bounds[3] - self.bounds[2]) 
        height_to_set = VideoProcess.constraint_dim(height_to_set,
                                            0,
                                            1088,
                                            height_increment)

        offsetX_max = self.cam.get_offsetX_maximum()
        offsetX_min = self.cam.get_offsetX_minimum()
        offsetX_increment = self.cam.get_offsetX_increment()
        #self.logger.info([offsetX_min,offsetX_max,offsetX_increment])
        offsetX_to_set = VideoProcess.constraint_dim(int(self.bounds[0]),
                                            0,
                                            2048,
                                            offsetX_increment)

        offsetY_max = self.cam.get_offsetY_maximum()
        offsetY_min = self.cam.get_offsetY_minimum()
        offsetY_increment = self.cam.get_offsetY_increment()
        offsetY_to_set = VideoProcess.constraint_dim(int(self.bounds[2]),
                                            0,
                                            1088,
                                            offsetY_increment)
        
        cur_height = self.cam.get_height()
        cur_width = self.cam.get_width()
        cur_offset_x = self.cam.get_offsetX()
        cur_offset_y = self.cam.get_offsetY()

        #Order of bounds setting is important

        if cur_offset_y < offsetY_to_set:
            self.cam.set_param(self.xiapi.XI_PRM_HEIGHT,height_to_set)
            self.cam.set_param(self.xiapi.XI_PRM_OFFSET_Y, offsetY_to_set)
        else :
            self.cam.set_param(self.xiapi.XI_PRM_OFFSET_Y, offsetY_to_set)
            self.cam.set_param(self.xiapi.XI_PRM_HEIGHT, height_to_set)

        if cur_offset_x < offsetX_to_set:
            self.cam.set_param(self.xiapi.XI_PRM_WIDTH, width_to_set)
            self.cam.set_param(self.xiapi.XI_PRM_OFFSET_X, offsetX_to_set)
        else :
            self.cam.set_param(self.xiapi.XI_PRM_OFFSET_X, offsetX_to_set)
            self.cam.set_param(self.xiapi.XI_PRM_WIDTH, width_to_set)

        self.bounds[0] = offsetX_to_set 
        self.bounds[1] = offsetX_to_set + width_to_set 
        self.bounds[2] = offsetY_to_set 
        self.bounds[3] = offsetY_to_set + height_to_set 
        #self.logger.info(self.bounds)

    def start_record(self,data):
        self.timeout_error_counter = 0
        self.timeout_error_sent = False 
        self.cam.stop_acquisition()
        self.info_dict[CamPrm.connection_info][1] = 0
        self.info_dict[CamPrm.connection_info][2] = 0
        self.dropped_frame_warning_sent = False
        self.logger.info('Initializing video recording')
        self.record = True
        self.first_frame = True
        self.update_disp_period()
        self.filename, self.video_fourcc, self.bounds = data

        self.set_camera_bounds()
        
        self.logger.info("Video Codec : " + str(self.video_fourcc))
        try :
            self.vid_writer = cv2.VideoWriter(
            self.filename,
            # using H264 because of performance and filesize
            # for example a 2048 x 1088, 30.00 fps, video in:
            # H.264: 259K
            # MJPG:  76M
            # a 300x difference !!!
            # it's unfortuante that H264 is not supported by default on
            # windows or OSX but there are free downloads including VLC
            # VLC will allow a user to convert to other formats
            cv2.VideoWriter_fourcc(*str(self.video_fourcc)),
            self._get_framerate(),
            (self.bounds[1]-self.bounds[0],self.bounds[3]-self.bounds[2]))
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            t = traceback.format_exception(exc_type, exc_value, exc_traceback)
            s = ""
            for l in t:
                s += l
            self.logger.info(s)
            self.status_queue.put((Command.cannot_open_video,None))
        else:
            if self.vid_writer.isOpened():
                self.status_queue.put((Command.opened_video,None))
            else:
                self.status_queue.put((Command.cannot_open_video,None))
            self.update_camera_time_offset()
            LC = int(self.bounds[3]-self.bounds[2])
            bwf = (48.0)/(((129*self.bwl*10**6)/(1024.0*self.bpp))*((12.0+LC)/(LC*1.0)))
            self.time_dr = (37.625+5.375*LC)*bwf*0.0000001
            #self.logger.info("Time dr is " + str(self.time_dr))
            self.setup_incorrect_trigger_detection() 
        self.cam.set_param(self.xiapi.XI_PRM_GPO_MODE,'XI_GPO_EXPOSURE_ACTIVE')
        
        #we disable aeag as exposure/gain changes results in incorrect triggering !
        self.cam.set_param(self.xiapi.XI_PRM_EXPOSURE,int(self.settings[CamPrm.exposure]*1000))
        self.cam.set_param(self.xiapi.XI_PRM_GAIN,self.settings[CamPrm.gain])
        self.cam.set_param(self.xiapi.XI_PRM_AEAG,0)
        self.verify_settings()
        self.cam.start_acquisition() 
    
    def stop_record(self):
        self.timeout_error_counter = 0    
        self.cam.set_param(self.xiapi.XI_PRM_GPO_MODE,'XI_GPO_OFF')
        recieved_frames = self.info_dict[CamPrm.connection_info][2]
        self.info_dict[CamPrm.connection_info][1] = 0
        self.info_dict[CamPrm.connection_info][2] = 0
        self.logger.debug('stop recording')
        self.record = False
        self.first_frame = False
        self.disp_period = self.update_disp_period()
        if self.vid_writer:
            self.vid_writer.release()
            video_to_check = cv2.VideoCapture(self.filename)
            if video_to_check.isOpened():
                self.logger.debug( "Number of recieved frames is %d" % (recieved_frames,))
                self.logger.debug("Number of frames written to video is %d" %\
                    (video_to_check.get(cv2.CAP_PROP_FRAME_COUNT),))
                if recieved_frames != video_to_check.get(cv2.CAP_PROP_FRAME_COUNT):
                    
                    self.status_queue.put((Command.video_frames_missing, None))
            video_to_check.release()
        self.vid_writer = None
        self.cam.stop_acquisition()
        self.last_counter_value = 0
        self.bounds[0] = 0
        self.bounds[1] = 2048
        self.bounds[2] = 0
        self.bounds[3] = 1088
        self.set_camera_bounds()
        self.cam.start_acquisition()
        
        #self.img_write_queue = None
        
    def _attempt_open_camera(self):
       
        try:
            if self.cam.get_number_devices() > 0 : 
                try:
                    self.cam.open_device()
                    self.init_camera(self.cam)
                    self.update_camera_time_offset()
                    self.cam.start_acquisition()
                    self.info_dict[CamPrm.connection_info][0] =\
                    self.cam.get_device_info_string(self.xiapi.XI_PRM_DEVICE_NAME)
                except:
            #let calling function handle an exception
                    self.logger.error(traceback.format_exc())
                else:
                    self.status_queue.put((Command.camera_connected, None))
                    self.verify_settings()
                    found_offset = False
                    self.connected = True
                    self.new_counter_value = 0
                    self.last_counter_value = 0
        except:
            self.logger.error(traceback.format_exc())

    def update_camera_time_offset(self):
        #Reset camera timestamp and store CPU time corresponding to reset event
        self.cam.set_param(self.xiapi.XI_PRM_TS_RST_SOURCE,'XI_TS_RST_SRC_SW')
        self.zero_offset = time.time()

    def get_cam_timestamp(self):
        if self.img.width == 0:
            raise

        timestamp = (self.img.tsSec
                    + self.img.tsUSec*0.000001)
        return timestamp

    def setup_incorrect_trigger_detection(self):
        self.first_trig_found = False
        self.warning_sent = False
        self.last_trig_time = 0
   
    def detect_incorrect_triggers(self):
        self.base_trig_period = 1.0/self._get_framerate()
        if not self.first_trig_found :
            self.first_trig_found = True
            self.last_trig_time = self.get_cam_timestamp()
        else :
            #trigger period is found by comparing timestamps from past 
            #and current frames
            trig_period = self.get_cam_timestamp() - self.last_trig_time
            if abs(self.base_trig_period - trig_period) >\
                    0.002 : #Any kind of error is not tolerable in synchronized mode
                self.logger.error( "Current trig_period %f"% (trig_period,))
                if not self.warning_sent :
                    self.status_queue.put((Command.trig_error, None))
                    self.warning_sent = True
            #self.logger.info("Trigger timing :" +
            #            str(self.base_trig_period) + ', ' + str(trig_period) )

        self.last_trig_time = self.get_cam_timestamp()

    def close_camera(self):
        try:
            self.cam.stop_acquisition()
            self.cam.close_device()
        except:
            self.logger.info(traceback.format_exc())
        finally:
            self.info_dict[CamPrm.connection_info][0] = "Not Connected" 
            self.info_dict[CamPrm.connection_info][1] = 0
            self.info_dict[CamPrm.connection_info][2] = 0

            self.connected = False
            self.status_queue.put((Command.camera_disconnected, None))
    
            if self.record :
                self.update_disp_period()
                self.record = False
                if self.vid_writer:
                    self.vid_writer.release()
            #self.img_write_queue = None

    def _update_params(self,settings_dict):
        if self.connected:
            self.close_camera()
        dict_copy(self.settings,settings_dict) 
        if self.connected:
            self.logger.debug('updated settings and reintializing camera')
        else:
            self.logger.debug('updated camera settings')
        self._attempt_open_camera()

    #def run(self):
    #    cProfile.runctx('self.run_method()',globals(),locals(),'profile_proc1.txt')

    def run(self):
        # must not be imported until after fork otherwise will get the error:
        # __THE_PROCESS_HAS_FORKED_AND_YOU_CANNOT_USE_THIS_COREFOUNDATION_FUNCTIONALITY___YOU_MUST_EXEC__
        from ximea import xiapi
        self.xiapi = xiapi
        self.info_dict = {}
        self.info_dict[CamPrm.connection_info] = ["Not Connected", 0, 0]
        
        self.isColor = False #safe default
        self.last_counter_value = 0
        
        self.shared_image_buffer = np.frombuffer(self.shared_image_array.get_obj(),dtype="uint16")
        
        self.logger = log_to_stderr()
        self.logger.setLevel(logging.INFO)
         
        self.cam = self.xiapi.Camera()
        self.img = self.xiapi.Image()
        
        keep_running = True
        self.dropped_frame_warning_sent = False
        self.timeout_error_cleared = False
    
        self.disp_fps_record = 20
        self.disp_fps_free = 20

        # wait for initialization message with cfg setting
        cmd, data = self.cmd_queue.get() # blocks by default
        self.logger.debug( "cmd:" + str(cmd))
        self.logger.debug("data:" + str(data))
        assert cmd is Command.new_settings, cmd
        self._update_params(data)

        self.update_disp_period() 
         
        while keep_running:
            
            if self.connected:             
                if not self.cam.is_isexist:
                    self.close_camera()
            elif not self.connected:
                self._attempt_open_camera()

            while not self.cmd_queue.empty():
                
                cmd, data = self.cmd_queue.get()
                if cmd is Command.terminate:
                    keep_running = False
                    self.logger.debug('Recieved terminate command')
                    break
                elif cmd is Command.record and self.connected:
                    self.logger.debug('Recieved record command')
                    self.start_record(data)
                elif cmd is Command.stop_record and self.connected:
                    self.logger.debug('Recieved stop record command')
                    self.stop_record()
                elif cmd is Command.discard_recording:
                    self.logger.debug('Recieved discard recording command')         
                    if os.path.exists(self.filename):   
                        os.remove(self.filename)
                elif cmd is Command.new_settings:
                    if not self.record and self.connected:
                        self._update_params(data)
                    if not self.connected:
                        self._update_params(data)
                        self.status_queue.put((Command.settings_update, data))
                        self.updateEstimatedLimits()
                elif cmd is Command.exposure_setting:
                    self.set_exposure_time(data)
                elif cmd is Command.gain_setting:
                    self.set_gain(data)
                elif cmd is Command.auto_exp_gain_setting:
                    self.set_auto_exp_gain(data)

            if not keep_running or not self.connected :
                continue

            try :
                if self.settings[CamPrm.auto_exp_gain]:
                    if self.settings[CamPrm.exposure] !=\
                            self.cam.get_param(self.xiapi.XI_PRM_EXPOSURE)/1000.0:
                        self.send_exp_and_gain_update()
                    elif self.settings[CamPrm.gain] !=\
                            float(self.cam.get_param(self.xiapi.XI_PRM_GAIN)):
                        self.send_exp_and_gain_update()
                
                #allow for 2 times the expected frame period before throwing a
                #timeout error
                self.timeout_max = max(1,int(2*1000.0/self._get_framerate()))
                self.timeout = 5
                self.cam.get_image(self.img,self.timeout_max)
                if self.first_frame:
                    self.last_counter_value = 0
                    self.timestamp = (self.zero_offset 
                                     + self.img.tsSec
                                     + self.img.tsUSec*0.000001)
            
            except self.xiapi.Xi_error as err:
                if err.status == 10:
                    #Only throw a timeout error to warn the user to connect the
                    #camera and amplifier since this is not a serious error.
                    #We don't want this worrying the user during a recording
                    #either
                    if (not self.timeout_error_sent and
                    ( not self.record and self.timeout_error_counter > int(self.timeout_max/ self.timeout))):
                        if self.settings[CamPrm.triggered]:

                            self.status_queue.put((Command.timeout_error_triggered, None))
                            self.timeout_error_sent = True
                            self.timeout_error_cleared = False
                        
                    else:
                        self.timeout_error_counter += 1
                    continue
                else :

                    self.logger.info('Camera probably disconnected')
                    self.close_camera() 

            else :
                self.new_counter_value = self.img.acq_nframe
                if self.timeout_error_counter != 0:
                    if self.timeout_error_sent and not self.timeout_error_cleared:
                        self.status_queue.put((Command.clear_timeout_error,None))
                        self.timeout_error_cleared = True
                    self.timeout_error_counter = 0
                self.data = self.img.get_image_data_numpy()
                self.colordata = fu.ensureColor(self.data)
                
                self.info_dict[CamPrm.connection_info][2] = self.info_dict[CamPrm.connection_info][2] + 1
                if self.record:
                    self.detect_incorrect_triggers()
                    
                    #start_test_time = time.time()
                    #self.img_write_queue.put((self.colordata,self.new_counter_value))
                    if self.vid_writer:
                        self.vid_writer.write(self.colordata)
                   
                    if self.first_frame :
                        self.logger.info("first frame logic") 
                        self.status_queue.put((Command.first_frame_timestamp,
                                               self.timestamp))
                
                        self.first_frame = False
 

                if not self.new_counter_value == self.last_counter_value + 1:  
                    self.logger.error( "dropped %d" % (self.new_counter_value -
                            self.last_counter_value))
                    if self.record:
                        if not self.dropped_frame_warning_sent :
                            self.status_queue.put((Command.dropped_frames, None))
                            self.dropped_frame_warning_sent = True

                        self.logger.info('Frame dropped')
                    self.info_dict[CamPrm.connection_info][1] = (self.info_dict[CamPrm.connection_info][1]
                                            + self.new_counter_value 
                                            - self.last_counter_value)

                if self.disp_counter >= self.disp_period:
                
                    start_time = time.time()
                    if self.isColor:
                        img_size =\
                        self.data.shape[0]*self.data.shape[1]*self.data.shape[2]
                    else:
                        img_size = self.data.shape[0]*self.data.shape[1]

                    with self.shared_image_array.get_lock():


                        if self.isColor:
                            self.shared_image_buffer[:3] =\
                                np.array(self.colordata.shape).astype('uint16')
                            self.shared_image_buffer[3:img_size+3] =\
                                self.colordata.flatten()
                        else:
                            self.shared_image_buffer[:2] =\
                                    np.array(self.data.shape).astype('uint16')
                            self.shared_image_buffer[2] = np.uint16(0)
                            self.shared_image_buffer[3:img_size+3] =\
                                self.data.flatten()

                    #self.img_queue.put(self.colordata)
                    self.disp_counter = 0
                    

                    self.status_queue.put((Command.info_update,
                                                    self.info_dict))

                self.disp_counter = self.disp_counter + 1
                self.last_counter_value = self.new_counter_value 

        if self.connected:

            self.cam.set_param( 
                    self.xiapi.XI_PRM_COUNTER_SELECTOR,
                    'XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES') 
            
            self.logger.debug(  
                    '%s skipped in transport',
                    self.cam.get_counter_value())
            
            self.cam.set_param( 
                    self.xiapi.XI_PRM_COUNTER_SELECTOR,
                    'XI_CNT_SEL_API_SKIPPED_FRAMES')
            
            self.logger.debug(  
                    '%s skipped in api',
                    self.cam.get_counter_value())
            
            self.close_camera()




            

        
if __name__ == '__main__' : 
    import time 
    #nemacquire bounds default
    y_width = 1088
    x_width = 2048
    x_left = 0
    y_top = 0 # default
    bounds =  [ x_left, 
                x_left+x_width,
                y_top, 
                y_top+y_width]
    settings_dict = {}
    settings_dict[CamPrm.framerate_div] = 1
    settings_dict[CamPrm.exposure] = 1 
    settings_dict[CamPrm.triggered] = False 
    settings_dict[CamPrm.white_balance] = False
    settings_dict[CamPrm.framerate_free] = 80
    cmd_queue = SimpleQueue()
    img_queue = SimpleQueue()
    status_queue = SimpleQueue()
    
    vid_writer_process =\
    VideoProcess(img_queue,cmd_queue,status_queue)
    cmd_queue.put((Command.new_settings,settings_dict))
    
    #Run on current process
    vid_writer_process.start()
    #while 1:
    #    if not status_queue.empty():
    #        cmd,data = status_queue.get()
    #        print cmd
    #        if cmd == Command.camera_connected:
    #            break
    
    cmd_queue.put((Command.record,('test.avi',bounds)))
    time_start = time.time()
    timeout = 20
    
    while time.time() < time_start + timeout :
        if not img_queue.empty():
            img = img_queue.get()
        if not status_queue.empty():
            status, data = status_queue.get()
    cmd_queue.put((Command.terminate,None))
    time.sleep(3)
    vid_writer_process.terminate()
