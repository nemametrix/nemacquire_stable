from pyqtgraph import ViewBox,RectROI
from PySide import QtGui,QtCore
from pyqtgraph import Point,mkPen
from pyqtgraph import ImageItem
 

#tested with pyqtgraph 0.10.0 


#Sets hover color and width to a nemacquire themed color instead of a pyqtgraph
#default


class RectROICustom(RectROI):

    
    def movePoint(self, handle, pos, modifiers=QtCore.Qt.KeyboardModifier(), finish=True, coords='parent'):
        ## called by Handles when they are moved. 
        ## pos is the new position of the handle in scene coords, as requested by the handle.
        
        newState = self.stateCopy()
        index = self.indexOfHandle(handle)
        h = self.handles[index]
        p0 = self.mapToParent(h['pos'] * self.state['size'])
        p1 = Point(pos)
        
        if coords == 'parent':
            pass
        elif coords == 'scene':
            p1 = self.mapSceneToParent(p1)
        else:
            raise Exception("New point location must be given in either 'parent' or 'scene' coordinates.")

        
        ## transform p0 and p1 into parent's coordinates (same as scene coords if there is no parent). I forget why.
        #p0 = self.mapSceneToParent(p0)
        #p1 = self.mapSceneToParent(p1)

        ## Handles with a 'center' need to know their local position relative to the center point (lp0, lp1)
        if 'center' in h:
            c = h['center']
            cs = c * self.state['size']
            lp0 = self.mapFromParent(p0) - cs
            lp1 = self.mapFromParent(p1) - cs
        
        if h['type'] == 't':
            snap = True if (modifiers & QtCore.Qt.ControlModifier) else None
            #if self.translateSnap or ():
                #snap = Point(self.snapSize, self.snapSize)
            self.translate(p1-p0, snap=snap, update=False)
        
        elif h['type'] == 'f':
            newPos = self.mapFromParent(p1)
            h['item'].setPos(newPos)
            h['pos'] = newPos
            self.freeHandleMoved = True
            #self.sigRegionChanged.emit(self)  ## should be taken care of by call to stateChanged()
            
        elif h['type'] == 's':
            ## If a handle and its center have the same x or y value, we can't scale across that axis.
            if h['center'][0] == h['pos'][0]:
                lp1[0] = 0
            if h['center'][1] == h['pos'][1]:
                lp1[1] = 0
            
            ## snap 
            if self.scaleSnap or (modifiers & QtCore.Qt.ControlModifier):
                lp1[0] = round(lp1[0] / self.snapSize) * self.snapSize
                lp1[1] = round(lp1[1] / self.snapSize) * self.snapSize
                
            ## preserve aspect ratio (this can override snapping)
            if h['lockAspect'] or (modifiers & QtCore.Qt.AltModifier):
                #arv = Point(self.preMoveState['size']) - 
                lp1 = lp1.proj(lp0)
            
            ## determine scale factors and new size of ROI
            hs = h['pos'] - c
            if hs[0] == 0:
                hs[0] = 1
            if hs[1] == 0:
                hs[1] = 1
            newSize = lp1 / hs
            
            ## Perform some corrections and limit checks
            if newSize[0] == 0:
                newSize[0] = newState['size'][0]
            if newSize[1] == 0:
                newSize[1] = newState['size'][1]
            if not self.invertible:
                if newSize[0] < 0:
                    newSize[0] = newState['size'][0]
                if newSize[1] < 0:
                    newSize[1] = newState['size'][1]
            if self.aspectLocked:
                newSize[0] = newSize[1]
            
            ## Move ROI so the center point occupies the same scene location after the scale
            s0 = c * self.state['size']
            s1 = c * newSize
            cc = self.mapToParent(s0 - s1) - self.mapToParent(Point(0, 0))
            
            ## update state, do more boundary checks
            newState['size'] = newSize
            newState['pos'] = newState['pos'] + cc
            
            if self.maxBounds is not None:
                r = self.stateRect(newState)
                if not self.maxBounds.contains(r):
                    
                    #Order of bounds checking is important !
                    #1. Bound x and y first, update width and height
                    #if necessary
                    #2. Then bound height and width
                    target_x = newState['pos'][0]
                    target_y = newState['pos'][1]
                    target_width = newState['size'][0]
                    target_height = newState['size'][1]

                    #target x must be more than min_x but less than min__x
                    # + max_width
                    #update newState position values first
                    newState['pos'][0] = min(max(self.maxBounds.x(),
                                            target_x),self.maxBounds.right())
                    newState['pos'][1] = min(max(self.maxBounds.y(),
                                            target_y),self.maxBounds.bottom())
                    
                   
                    #Adjusts width and height to make sure right and bottom
                    #edges are the same despite new newState position values
                    target_width = (target_width 
                                        + target_x 
                                        - newState['pos'][0])
                    target_height = (target_height 
                                        + target_y 
                                        - newState['pos'][1])

                    #Apply bound checking for updated target widths 
                    newState['size'][0] = min(target_width,
                                self.maxBounds.right()-newState['pos'][0])

                    newState['size'][1] = min(target_height,
                                self.maxBounds.bottom()-newState['pos'][1])
                    
                

            """End of edit"""
            """Start of old code
                    return
            End of old code"""

            self.setPos(newState['pos'], update=False)
            self.setSize(newState['size'], update=False)
        
        elif h['type'] in ['r', 'rf']:
            if h['type'] == 'rf':
                self.freeHandleMoved = True
            
            if not self.rotateAllowed:
                return
            ## If the handle is directly over its center point, we can't compute an angle.
            try:
                if lp1.length() == 0 or lp0.length() == 0:
                    return
            except OverflowError:
                return
            
            ## determine new rotation angle, constrained if necessary
            ang = newState['angle'] - lp0.angle(lp1)
            if ang is None:  ## this should never appen..
                return
            if self.rotateSnap or (modifiers & QtCore.Qt.ControlModifier):
                ang = round(ang / 15.) * 15.  ## 180/12 = 15
            
            ## create rotation transform
            tr = QtGui.QTransform()
            tr.rotate(ang)
            
            ## move ROI so that center point remains stationary after rotate
            cc = self.mapToParent(cs) - (tr.map(cs) + self.state['pos'])
            newState['angle'] = ang
            newState['pos'] = newState['pos'] + cc
            
            ## check boundaries, update
            if self.maxBounds is not None:
                r = self.stateRect(newState)
                if not self.maxBounds.contains(r):
                    return
            #self.setTransform(tr)
            self.setPos(newState['pos'], update=False)
            self.setAngle(ang, update=False)
            #self.state = newState
            
            ## If this is a free-rotate handle, its distance from the center may change.
            
            if h['type'] == 'rf':
                h['item'].setPos(self.mapFromScene(p1))  ## changes ROI coordinates of handle
                
        elif h['type'] == 'sr':
            if h['center'][0] == h['pos'][0]:
                scaleAxis = 1
                nonScaleAxis=0
            else:
                scaleAxis = 0
                nonScaleAxis=1
            
            try:
                if lp1.length() == 0 or lp0.length() == 0:
                    return
            except OverflowError:
                return
            
            ang = newState['angle'] - lp0.angle(lp1)
            if ang is None:
                return
            if self.rotateSnap or (modifiers & QtCore.Qt.ControlModifier):
                #ang = round(ang / (np.pi/12.)) * (np.pi/12.)
                ang = round(ang / 15.) * 15.
            
            hs = abs(h['pos'][scaleAxis] - c[scaleAxis])
            newState['size'][scaleAxis] = lp1.length() / hs
            #if self.scaleSnap or (modifiers & QtCore.Qt.ControlModifier):
            if self.scaleSnap:  ## use CTRL only for angular snap here.
                newState['size'][scaleAxis] = round(newState['size'][scaleAxis] / self.snapSize) * self.snapSize
            if newState['size'][scaleAxis] == 0:
                newState['size'][scaleAxis] = 1
            if self.aspectLocked:
                newState['size'][nonScaleAxis] = newState['size'][scaleAxis]
                
            c1 = c * newState['size']
            tr = QtGui.QTransform()
            tr.rotate(ang)
            
            cc = self.mapToParent(cs) - (tr.map(c1) + self.state['pos'])
            newState['angle'] = ang
            newState['pos'] = newState['pos'] + cc
            if self.maxBounds is not None:
                r = self.stateRect(newState)
                if not self.maxBounds.contains(r):
                    return
            #self.setTransform(tr)
            #self.setPos(newState['pos'], update=False)
            #self.prepareGeometryChange()
            #self.state = newState
            self.setState(newState, update=False)
        
        self.stateChanged(finish=finish)
    #this function isn't brought to API
    def _makePen(self):
        if self.mouseHovering:
            """Edit"""
            return mkPen(color = (33,170,243,255),width = 3)
            """End of Edit"""
        else:
            return self.pen
#Changed viewRect instead of targetRect in existing code !!! Bug in pyqtgraph?

#Prevent scaling that would break aspect ratio when in
#locked aspect ration and limits have been set
class ViewBoxCustom(ViewBox):

    def scaleBy(self,s=None,center=None,x=None,y=None):
        
        if s is not None:
            scale = Point(s)
        else:
            scale = [x, y]

        affect = [True,True]
        if scale[0] is None and scale[1] is None:
            return
        elif scale[0] is None:
            affect[0] = False
            scale[0] = 1.0
        elif scale[1] is None:
            affect[1] = False
            scale[1] = 1.0

        scale = Point(scale)

        if self.state['aspectLocked'] is not False:

            scale[0] = scale[1] 
        
        """Edit"""
        vr = self.viewRect()
        """End of Edit"""

        if center is None:
            center = Point(vr.center())
        else:
            center = Point(center)

        tl = center + (vr.topLeft()-center) * scale
        br = center + (vr.bottomRight()-center) * scale

        """Addition"""
        yMax = self.state['limits']['yLimits'][1]
        xMax = self.state['limits']['xLimits'][1]
        xMin = self.state['limits']['xLimits'][0]
        yMin = self.state['limits']['yLimits'][0]
       
        
        scale_limit = []
        if yMax is not None and affect[0]:
            
            if (br.y() > yMax):


                scale_limit.append((yMax -
                        center.y())/(1.0*vr.bottomRight().y()-center.y()))
                print 'yMax scale is :' + str(scale_limit[-1])
        
        if xMax is not None:
            
            if (br.x() > xMax) and affect[1]:
                scale_limit.append((xMax -
                    center.x())/(1.0*vr.bottomRight().x()-center.x()))
                print 'xMax scale is :' + str(scale_limit[-1])

        if xMin is not None:

            if (tl.x() < xMin) and affect[1]:
                scale_limit.append((
                    xMin - center.x())/
                    (1.0*vr.topLeft().x()-center.x()))
                print 'xMin scale is :' + str(scale_limit[-1])
        
        if yMin is not None:

            if (tl.y() < yMin) and affect[0]:
                scale_limit.append((yMin -
                    center.y())/(1.0*vr.topLeft().y()-center.y()))
                print 'yMin scale is :' + str(scale_limit[-1])

        if self.state['aspectLocked'] is not False and len(scale_limit)>0:

            min_scale_limit = min(scale_limit)

            scale[1] = min_scale_limit
            scale[0] = scale[1]

            tl = center + (vr.topLeft()-center) * scale
            br = center + (vr.bottomRight()-center) * scale
        """End of Addition"""

        if not affect[0]:
            self.setYRange(tl.y(),br.y(),padding = 0 )
        elif not affect[1]:
            self.setXRange(tl.x(), br.x(), padding = 0 )
        else:
            self.setRange(QtCore.QRectF(tl,br),padding = 0)
    
