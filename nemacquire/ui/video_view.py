from collections import namedtuple, deque


from PySide import QtGui,QtCore
import pyqtgraph as pg
from pyqtgraph import GraphicsLayoutWidget
import pyqtgraph.console as console
import cv2
import sys
from custom_pyqtgraph_classes import ViewBoxCustom, RectROICustom
from time import sleep

#Graphics Layout/Plot item  containing viewbox with image item and roi
#with methods to toggle roi selection

#State 1 : No Camera Connected 
#State 2 : Full View during recording (no ROI)
#State 3 : Full View with ROI selection tool
#State 4 : Zoomed in (ROI) view with panning

def qt_revert_fixed_size(obj):
    
    max_value = 1677215
    
    obj.setMaximumHeight(1677215)
    obj.setMaximumWidth(1677215)
    obj.setMinimumWidth(0)
    obj.setMinimumHeight(0)

class State:

    no_camera_connected = 0
    recording_full_view = 1
    full_view = 2
    roi_view = 3

    #Let VideoView decide whether to choose a full or roi view
    last_view_state = 4
    toggle_view_state = 5
    started_recording = 6
    stopped_recording = 7

class Bounds:
    
    Point = namedtuple('Point',['x','y'])

    def __init__ (self, x = 0, y = 0, width = 1, height = 1):
        
        self.x = x
        self.y = y
        self.width = width
        self.height = height
 
    @classmethod
    def from_bounds(cls,bounds,invertY = False):
        #print "from bounds"
        if not invertY:
            return  cls(x = bounds.x(),
                        y = bounds.y(),
                        width = bounds.width(),
                        height = bounds.height())
        else:
            return  cls(x = bounds.x(),
                        y = 1088 - bounds.y(),
                        width = bounds.width(),
                        height = bounds.height())

    @classmethod
    def from_range(cls,x_range, y_range,invertY = False):

        if not invertY:
            return cls( x = x_range[0],
                        y = y_range[0],
                        width = x_range[1] - x_range[0],
                        height = y_range[1] - y_range[0])
        else:
            return cls( x = x_range[0],
                        y = 1088-y_range[1],
                        width = x_range[1] - x_range[0],
                        height = y_range[1] - y_range[0])
            
    def fit_within(self,parentBounds):
        self.x = max(parentBounds.x,self.x)
        self.y = max(parentBounds.y,self.y)


        self.width = min(parentBounds.width,
                self.x - parentBounds.x + self.width)

        self.height = min(parentBounds.height,
                self.y - parentBounds.y + self.height)


    def topLeft(self):
        return Point(self.x,self.y)

    def bottomRight(self):
        return Point(self.x + self.width,self.y + self.height)

    def xRange(self):
        return (self.x, self.x + self.width)

    def yRange(self):
        return (self.y, self.y + self.height)

class VideoView(ViewBoxCustom):

    def __init__(self,cfg,parent_layout,ui_callback,
                    animation_finished_signal):
        super(VideoView,self).__init__(lockAspect=True)
        
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.animation_finished_signal = animation_finished_signal
        self.image_view_layout = parent_layout
        self.image_view_layout.geometryChanged.connect(self.update_viewBox_upon_layout_change)
        self.cfg = cfg
        self.theme_font = QtGui.QFont("Trebuchet MS",50)
        self.theme_text_color = pg.mkColor([70,70,70])
        self.roi_bounds = Bounds()
        self.img_bounds = Bounds()
        self.image_item_animating = False 
        self.roi = self._create_roi(self.cfg.roi_state)
        self.img_item = pg.ImageItem()
        self.text_item_cam_not_connected = self._create_text_item(
                                            "Camera Not Connected",
                                            self.theme_font,
                                            self.theme_text_color)

        super(VideoView,self).addItem(self.img_item)
        super(VideoView,self).addItem(self.roi)
        super(VideoView,self).addItem(self.text_item_cam_not_connected)
        
        self.ui_callback = ui_callback
        self.current_state = None
        self.stateUpdate(State.no_camera_connected)

    def _create_text_item(self,display_text = "Camera Not Connected", font = None,
            color = None):
        
        text_item = QtGui.QGraphicsTextItem(display_text)
        if font:
            text_item.setFont(font)
        if color:
            text_item.setDefaultTextColor(color)

        return text_item
    
    def _create_roi(self,roi_state = None):

        roi = RectROICustom([20,20],[20,20],maxBounds =
                QtCore.QRectF(0,0,2048,1088),
                pen = {'color' : (33,150,243,255), 'width' : 5})
        roi.handlePen = pg.mkPen(color=(238,238,238),width = 3)
        roi.addScaleHandle([0.5, 1], [0.5, 0])
        roi.addScaleHandle([0.5, 0], [0.5, 1])
        roi.addScaleHandle([1, 0.5], [0, 0.5])
        roi.addScaleHandle([0, 0.5], [1, 0.5])
        roi.setState(roi_state)

        roi.setZValue(10)

        return roi

    def save(self,filename):
        
        self.img_item.save(filename)


    def processAnimation(self):
        total_frame_count = 2*2
        if self.image_item_animating:
            self.animation_frame += 1
            if self.animation_frame < total_frame_count:

                opacity =\
                abs((total_frame_count/2-self.animation_frame)/(total_frame_count/2))

                self.img_item.setImage(self.base_animation_image,lut = None,levels =
                        (0,255),opacity =
                        opacity)
            else:

                self.stopImageCaptureAnimation()
                self.animation_finished_signal.emit()
    
    def setImage(self,img):
        
        assert img is not None

        if not self.image_item_animating:
            self.img_item.setImage(img,levels=(0,255))

        
        if (  self.img_bounds.width != img.shape[1] 
                or self.img_bounds.height != img.shape[0]):
        #New image dimensions

            self.img_bounds = Bounds(x = 0, 
                                     y = 0,
                                     width = img.shape[1],
                                     height = img.shape[0])
            self._update_ROI_bounds_constraint()
            
            if (self.current_state == State.full_view or
                self.current_state == State.recording_full_view):
                self.autoRange()

        if self.current_state == State.roi_view:
        #set viewbox limits
            self.setLimits(
                    xMin = self.img_bounds.x,
                    xMax = self.img_bounds.x + self.img_bounds.width,
                    yMin = self.img_bounds.y, 
                    yMax = self.img_bounds.y + self.img_bounds.height,
                    maxXRange = self.img_bounds.width,
                    maxYRange = self.img_bounds.height)

    def save_roi_state(self):
        #print "in save roi state"
        self.roi_bounds = Bounds.from_bounds(self.roi.parentBounds())
        self.cfg.roi_state = self.roi.saveState()
        self.cfg.save()


    def save_vb_range_state(self):
        #update (hidden) roi to match view range in viewbox in roi mode

        #print "y in viewbox is" + str(self.viewRange()[1][0])
        view_bounds = Bounds.from_range(*self.viewRange())
        #view_bounds.fit_within(self.img_bounds)
        
        #print "y in roi is set to" + str(1088 - view_bounds.y)
        self.roi.setPos([view_bounds.x,view_bounds.y])
        self.roi.setSize([view_bounds.width,view_bounds.height])

        self.save_roi_state()

    def _update_ROI_bounds_constraint(self):
        #print "In update ROI bounds constraint"
        #Create a new roi object with desired limits
        #Because no pyqtgraph method to call after instantiation
        
        current_roi_bounds = Bounds.from_bounds(self.roi.parentBounds())
        #current_roi_bounds.fit_within(self.img_bounds)        
        self.roi.setPos([current_roi_bounds.x,current_roi_bounds.y])
        self.roi.setSize([current_roi_bounds.width,current_roi_bounds.height])

        self.roi.maxBounds = QtCore.QRectF(
                0,
                0,
                self.img_bounds.width,
                self.img_bounds.height)
        
        
        self.roi.stateChanged()

    
    def update_ROI_bounds(self):
        #update roi bounds when roi changes
        self.roi_bounds = Bounds.from_bounds(self.roi.parentBounds())
    
    def ROI_bounds_from_cfg(self):
        #load roi bounds from cfg
        self.roi.setState(self.cfg.roi_state)
        self.roi_bounds = Bounds.from_bounds(self.roi.parentBounds())

    def viewBox_approx_bound_hack(self):
 
        vb_height = self.image_view_layout.height()
        vb_width = self.image_view_layout.width()
        
        if vb_width != 0 :
            vb_aspect = vb_height*1.0/vb_width
        else:
            raise
        
        target_height = self.roi_bounds.height
        target_width  = self.roi_bounds.width
        target_aspect = target_height*1.0/target_width
        
        if vb_aspect > target_aspect:
            self.setMaximumHeight(vb_width*target_aspect)
            self.setMaximumWidth(vb_width)
        else:
            self.setMaximumWidth(vb_height*1.0/target_aspect)
            self.setMaximumHeight(vb_height) 
        self.setXRange(*self.roi_bounds.xRange(),padding = 0)
        self.setYRange(*self.roi_bounds.yRange(),padding = 0)
        self.setLimits( xMin = 0,
                        xMax = self.img_bounds.width,
                        yMin = 0, 
                        yMax = self.img_bounds.height,
                        maxXRange = self.img_bounds.width,
                        maxYRange = self.img_bounds.height)
        
    def update_viewBox_upon_layout_change(self):
        if self.current_state == State.roi_view:
            vb_height = self.image_view_layout.height()
            vb_width = self.image_view_layout.width()
            #self.vb.hide()
            
            if vb_width != 0 :
                vb_aspect = vb_height*1.0/vb_width
            else:
                raise
            
            target_height = self.roi_bounds.height
            target_width  = self.roi_bounds.width
            target_aspect = target_height*1.0/target_width
            
            if vb_aspect > target_aspect:
                self.setMaximumHeight(vb_width*target_aspect)
                self.setMaximumWidth(vb_width)
            else:
                self.setMaximumWidth(vb_height*1.0/target_aspect)
                self.setMaximumHeight(vb_height) 
            self.setXRange(*self.roi_bounds.xRange(),padding = 0)
            self.setYRange(*self.roi_bounds.yRange(),padding = 0)
            self.setLimits(xMin = 0,xMax = 2048,yMin = 0, yMax =
                        1088,maxXRange=2048, maxYRange = 1088)


    def imageCaptureAnimation(self):
        
        org_image = self.img_item.image
        self.image_item_animating = True
        for x in range(9):
            opacity = abs((4.0-x)/4.0)
            print opacity
            self.img_item.setImage(org_image,levels = (0,255),opacity =
                    opacity)
            sleep(0.05)
       
        self.image_item_animating = False


    def startImageCaptureAnimation(self):

        self.image_item_animating = True
        self.animation_frame = 0
        self.base_animation_image = self.img_item.image

    def stopImageCaptureAnimation(self):

        self.image_item_animating = False


    def setResetCameraMessage(self):
        
        self.text_item_cam_not_connected.setPlainText("Resetting Camera")

    def stateUpdate(self,target_state):
        #State transitions
        #Ensure roi_bounds is within img_bounds or crop to it.
        #print "In State Update"

        if target_state == State.no_camera_connected:

            self.setLimits(xMin = None,xMax = None,yMin = None, yMax =
                    None,maxXRange = None,maxYRange = None)
            self.text_item_cam_not_connected.show()                
            self.roi.hide()
            self.img_item.hide()
            self.invertY(True)
            super(VideoView,self).autoRange()
        
        elif target_state == State.recording_full_view:
            self.setLimits(xMin = None,xMax = None,yMin = None, yMax =
                    None,maxXRange = None,maxYRange = None)
            self.text_item_cam_not_connected.hide()                
            self.roi.hide()
            self.img_item.show()
            self.invertY(True)
            self.setMouseEnabled(False,False)
            #super(VideoView,self).autoRange()
        
        elif target_state == State.full_view:
            
            self.setLimits(xMin = None,xMax = None,yMin = None, yMax =
                    None,maxXRange = None,maxYRange = None)
            if self.current_state == State.roi_view:
                self.save_vb_range_state()
            self.img_item.show()
            self.roi.show()
            self.text_item_cam_not_connected.hide()
            self.invertY(True)
            self.cfg.roi_enabled = False
            self.cfg.save()
            self.setMouseEnabled(False,False)
            super(VideoView,self).autoRange()
        
        elif target_state == State.roi_view: 

            self.img_item.show()
            if self.current_state == State.full_view:
                self.update_ROI_bounds()
            else :
                self.ROI_bounds_from_cfg()

            self.roi.hide()
            self.invertY(True)
            self.text_item_cam_not_connected.hide()
            self.cfg.roi_enabled = True
            self.cfg.save()
            self.setMouseEnabled(True,True)
            self.viewBox_approx_bound_hack()
            self.sigRangeChangedManually.connect(self.save_vb_range_state)

            self.setXRange(*self.roi_bounds.xRange(),padding=0)
            self.setYRange(*self.roi_bounds.yRange(),padding=0)
            self.roi.sigRegionChangeFinished.disconnect(self.save_roi_state)

        #Transitionary states always call stateUpdate and return immediately
        elif target_state == State.last_view_state:
            if self.cfg.roi_enabled:
                self.stateUpdate(State.roi_view)
            else :
                self.stateUpdate(State.full_view)
            return
        
        elif target_state == State.toggle_view_state:
            if self.cfg.roi_enabled:
                self.stateUpdate(State.full_view)
            else :
                self.stateUpdate(State.roi_view)
            return

        elif target_state == State.started_recording:
            if self.current_state == State.full_view\
                    or self.current_state == State.roi_view:
                self.stateUpdate(State.recording_full_view)
            return

        elif target_state == State.stopped_recording:
            print "stopped recording" 
            if self.current_state != State.no_camera_connected:
                self.stateUpdate(State.last_view_state)
            return
        #temporary states don't execute the below portion of code
        if target_state != State.no_camera_connected:

            self.text_item_cam_not_connected.setPlainText("Camera Not Connected")
        if target_state != State.roi_view :

            if self.current_state == State.roi_view:
                qt_revert_fixed_size(self)
                self.sigRangeChangedManually.disconnect(self.save_vb_range_state)
            self.roi.sigRegionChangeFinished.connect(self.save_roi_state)
            
        self.current_state = target_state

        self.ui_callback(self.current_state)


if __name__ == "__main__":

    app = QtGui.QApplication(sys.argv)
    main_window = QtGui.QMainWindow()

    sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
            QtGui.QSizePolicy.Expanding)
    video_view = VideoView()
    test_img = cv2.imread("Etaluma.png")
    video_view.setImage(test_img)
    video_view.stateUpdate(State.full_view) 

    graphicsLayoutWidget = GraphicsLayoutWidget()
    main_window.setCentralWidget(graphicsLayoutWidget)
    graphicsLayoutWidget.addItem(video_view,0,0)
    graphicsLayoutWidget.setSizePolicy(sizePolicy)
    main_window.show()

    
    c = console.ConsoleWidget(namespace={'s': video_view,
                                         'g': graphicsLayoutWidget,
                                         'n' : main_window,
                                         'pg' : pg})
    c.show()
    video_view.show()
    app.exec_()
