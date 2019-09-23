from cv2 import VideoCapture as vc
import cv2
import sys 
from time import sleep
import time
from PySide import QtCore, QtGui
import pyqtgraph as pg
from collections import deque
import os
#from matplotlib import pyplot as plt
import numpy as np
from itertools import tee,izip
import frameutils as fu
from functools import partial
import scipy.signal as signal
import scipy.interpolate as sp
#from skimage.morphology import skeletonize
#from skimage import img_as_ubyte
from modelutil import ModelUtil

class WormDetector():
    
    def pairwise(self,iterable):
        a, b = tee(iterable)
        next(b, None)
        return izip(a, b)
    

    def __init__ (self, selection = 0) : 
        self.y_min_a = []
        self.y_max_a = []

        self.x_min_a = []
        self.x_max_a = []

        self.avg_param = 5
        self.canny_param = [20,50]
        self.hline_param = [1, np.pi/180, 300]

        self.del_ker_param = [6]
        #todo define kernel parameters and add them to trackbars

        #raw image
        self.img = np.ndarray([])
        #output cnt
        self.cnt = np.ndarray([])
        #output cnt as part of image
        self.cnt_img = np.ndarray([])
        
        self.cnt_cor_param = [10]
        #1 corresponds to fixed bounds, 2 corresponds to moving average
        self.channelBoundsMode = 2
 
    def updateParams(self,param,pos,levels):
        param[pos] = levels
        

    def contourCorrect(self,cnt):

        cnt_len = cnt.shape[0]
        #print cnt_len
        hull = cv2.convexHull(cnt)
        for pa,pb in self.pairwise(list(cnt)):
            pass
        count = 0
        special_points = []
        special_idx = []
        for edge in hull:
            edge = edge[0]
            #assume edge hull points are in edge
            cur_index_1 = np.where(cnt==edge[0])[0]
            cur_index_2 = np.where(cnt==edge[1])[0]
            #print cur_index_2
            cur_index = np.intersect1d(cur_index_1,cur_index_2)
            #look into the future
            
            
            next_index = ( cur_index + 3) % cnt_len
            prev_index = ( cur_index -3 ) % cnt_len
           
            #print next_index
            #print prev_index

            norm_var = cv2.norm(cnt[next_index],cnt[prev_index]) 
            #print str(norm_var) + ', ',
            if( norm_var  < self.cnt_cor_param[0]):
                #print edge
                special_idx.append(cur_index[0])
                special_points.append(edge)
                count += 1

        cnt_c = cnt.copy()
        idx_to_remove = []
        for idx,line_tip in enumerate(special_points) :
            
            #peaking into future
            future_norm = self.cnt_cor_param[0] + 1
            f_index = 1
            idx_to_remove.append(special_idx[idx])
            while cv2.norm(cnt_c[(special_idx[idx]+f_index)%cnt_len] \
                    ,cnt_c[(special_idx[idx]-f_index) % cnt_len]) < self.cnt_cor_param[0]:
                
                idx_to_remove.append((special_idx[idx]+f_index)%cnt_len)

                idx_to_remove.append((special_idx[idx]-f_index)%cnt_len)

                f_index += 1

        idx_to_remove.sort()

        idx_to_remove = list(set(idx_to_remove))
        idx_to_remove.sort()
        #print cnt_c
        cnt_c = np.delete(cnt_c,idx_to_remove,0)
        



        
        return cnt_c

    def startTrackbars(self,name_window):
        cv2.namedWindow("Img Process Control")
        cv2.createTrackbar("Canny 1st threshold",\
        "Img Process Control"\
        ,self.canny_param[0],100,partial(self.updateParams,self.canny_param,0))
        
        cv2.createTrackbar("Canny 2nd threshold",\
        "Img Process Control"\
        ,self.canny_param[1],255,partial(self.updateParams,self.canny_param,1))

        cv2.createTrackbar("HoughLines rho",\
        "Img Process Control"\
        ,self.hline_param[0],1000,partial(self.updateParams,self.hline_param,0)) 

        cv2.createTrackbar("HoughLines line length",\
        "Img Process Control"\
        ,self.hline_param[2],1500,partial(self.updateParams,self.hline_param,2))

        cv2.createTrackbar("Contour correction",\
        "Img Process Control"\
        ,self.cnt_cor_param[0],50,partial(self.updateParams,self.cnt_cor_param,0))

        cv2.createTrackbar("Deletion kernel horizontal",\
        "Img Process Control"\
        ,self.del_ker_param[0],10,partial(self.updateParams,self.del_ker_param,0))

    def getChannelBoundImg(self,img_canny):
        #Expects Canny Input
        img_canny_t = img_canny.copy()


        lines = cv2.HoughLines(img_canny_t,*self.hline_param)
            
        if lines is None or len(lines[0,:,0]) < 2:
            return False

        #insertion sort by y_intercept while calculating average angle
        selected_lines = []
        theta_avg = 0

        try : 
            for rho,theta in lines[:,0,:] :

                y_intercept = rho/np.sin(theta)
                insr_pos = 0
                theta_avg += theta

                for pos,line_t in enumerate(selected_lines) :                       

                    if y_intercept > line_t[2] :

                        insr_pos = pos + 1
                        continue

                    insr_pos = pos    
                    break
                
                selected_lines.insert(insr_pos,(rho,theta,y_intercept))
            

            theta_avg /= len(selected_lines)        
            prev_rho=0
         
            #code segment for comparison between every consecutive pair of lines

            #for la,lb in self.pairwise(list(selected_lines)):
            #    if abs(la[1] - theta_avg)>np.pi/180:
            #        pass

            

            

            #remove angles that deviate too much from average angle
            for la in list(selected_lines):
                if abs(la[1]-theta_avg)>np.pi/180:
                    selected_lines.remove(la)
                    
            for rho,theta,y_intercept in selected_lines :
                #print('another one')
                a = np.cos(theta)
                b = np.sin(theta)
                x0 = a*rho
                y0 = b*rho
                #Assume line length of 600
                lenl = 2000
                x1 = int(x0 - lenl*b)
                y1 = int(y0 + lenl*a)
                x2 = int(x0 + lenl*b)
                y2 = int( y0 - lenl*a)
                #print('x1 ' + str(x1) + ',y1 ' + str(y1)) 
                cv2.line(img_canny_t,(x1,y1),(x2,y2),1,2)
           # cv2.imshow('lines on canny',np.multiply(img_canny_t,255))
            

            #Get bounding rect containing 2 lines that are assumed to correspond to
            #channel walls (optimal if they are nearly horizontal

            x_min = 0
            x_max = img_canny_t.shape[1]

            if len(selected_lines) == 0 :
                return False
            #First line y axis bounds
            rho, theta,y_intercept = selected_lines[0]

            y_min_1 = int((rho - x_max*np.cos(theta))/(np.sin(theta)))
            y_max_1 = int(selected_lines[-1][2])

            #Last line bounds
            rho, theta,y_intercept = selected_lines[-1]
            
            y_max_2 = int((rho - x_max*np.cos(theta))/(np.sin(theta)))
            y_min_2 = int(selected_lines[0][2])


            if self.channelBoundsMode == 1: 
               
                if (len(self.y_min_a) < 2):
                
                    self.y_min_a.append(min(y_min_1,y_min_2)- 20)
                    self.y_max_a.append(max(y_max_1,y_max_2)+ 20)

            
                y_min = self.y_min_a[0]
                y_max = self.y_max_a[0]


            elif self.channelBoundsMode == 2:


                self.y_min_a.append(min(y_min_1,y_min_2)- 20)
                self.y_max_a.append(max(y_max_1,y_max_2)+ 20)

                if (len(self.y_min_a) > self.avg_param) :
                    self.y_min_a.pop(0)
                    self.y_max_a.pop(0)


                y_min = sum(self.y_min_a)/len(self.y_min_a)
                y_max = sum(self.y_max_a)/len(self.y_max_a)

        except :
            return False
        else :
            return y_min, y_max, x_min, x_max
        
        

    def breakLines(self,img_canny):

        #Expects Canny Input
        img_canny_t = img_canny.copy()
        #kernel = np.ones((1,self.del_ker_param[0]),np.uint8)
        #img_canny_t -= cv2.erode(img_canny_t,kernel,iterations= 2  )
        kernel = np.ones((2,self.del_ker_param[0]),np.uint8)
        img_canny_t = cv2.dilate(img_canny_t,kernel,iterations=1)

        return img_canny_t

    def checkBinaryInput():
        pass

    def getCanny(self,img):

        
        img_canny = img

        img_canny = cv2.GaussianBlur(img_canny,(5,5),0)
       
        img_canny = cv2.Canny(img_canny,*self.canny_param)
        
        #todo: check if threshold is really necessary
        _,img_canny = cv2.threshold(img_canny,0,1,cv2.THRESH_BINARY)
        
        return img_canny


    def getSpline(self,cnt):
        #expects [ [x,y] [x,y]...]

        x = cnt[:,0]
        y = cnt[:,1]

        knots = np.arange(np.min(x),np.max(x),(np.min(x)-np.max(x))/100)
        tck = sp.splrep(x,y,k=3,s= 50)

        u = np.arange(np.min(x),np.max(x))
        
        new_points = sp.splev(u,tck)

        return u, new_points


    def skeletonise(self,img_contour):
        #expects filled contour
        
        element = cv2.getStructuringElement(cv2.MORPH_CROSS,(3,3))
        size = np.size(img_contour)
        skel = np.zeros(img_contour.shape,np.uint8)
        done = False
        while not done:

            eroded = cv2.erode(img_contour,element)
            temp = cv2.dilate(eroded,element)
            temp = cv2.subtract(img_contour,temp)
            skel = cv2.bitwise_or(skel,temp)
            img_contour = eroded.copy()

            zeros = size - cv2.countNonZero(img_contour[:,:,1])
            if zeros==size:
                done = True
        
        cv2.imshow("skel",skel)
        return skel


    def findEndPoints(self,img_canny_t):
        
        y_max = img_canny_t.shape[0]
        x_max = img_canny_t.shape[1]

        int_y = []

        for x in range(x_max):

            int_y.append(np.sum(img_canny_t[:,x]))

        
        b, a = signal.butter(3,0.02)
        int_y = signal.lfilter(b, a,int_y)
#        plt_h = plt.subplot()
 #       plt_h.plot(int_y)
  #      plt.show()
        mid_int_y = np.max(int_y)/2.0
        worm = False
        x_min = 0
        for i, int_y_i in enumerate(int_y):
            if not worm :

                if int_y_i > mid_int_y:
        
                    x_min = i - 50
                    worm = True

            else :

                if int_y_i < mid_int_y:

                    x_max = i + 100 
                    break

        

        if self.channelBoundsMode == 1: 
           
            if (len(self.x_min_a) < 2):
            
                self.x_min_a.append(x_min)
                self.x_max_a.append(x_max)

        
            x_min = self.x_min_a[0]
            x_max = self.x_max_a[0]


        elif self.channelBoundsMode == 2:


            self.x_min_a.append(x_min)
            self.x_max_a.append(x_max)

            if (len(self.x_min_a) > self.avg_param) :
                self.x_min_a.pop(0)
                self.x_max_a.pop(0)


            x_min = sum(self.x_min_a)/len(self.x_min_a)
            x_max = sum(self.x_max_a)/len(self.x_max_a)

            if x_min < 0 :
                x_min =0
        return x_min,x_max


    def findCenterLine(self,img_canny_t):

        y_max = img_canny_t.shape[0]
        x_max = img_canny_t.shape[1]


        #print img_canny_t.shape
        centerline = np.zeros(x_max) #linear array
        
        y_arr = np.arange(1,y_max+1)
        #print y_arr
        for x in range(x_max):
            
            centerline[x] = sum(np.multiply(y_arr,img_canny_t[:,x]))/y_max
            #check for rounding error

        
        #plt_h = plt.subplot()
        #plt_h.plot(centerline)
        #plt.show()
        return centerline
            

    def findCenterLine1(self,cnt):
        #2012,1,2

        x_max = np.max(cnt[:,0,0])
        last_x = 0
        centerline = []
        topline = []
        botline = []
        duplicate_arr = []
        for i  in range(cnt.shape[0]):

            x = cnt[i,0,0]
            y = cnt[i,0,1]
            
            if last_x == x :
               pass 
            else :
                last_x = x
                #print len(duplicate_arr)
                if len(duplicate_arr) < 2:
                    #duplicate_arr = []
                    print("hmm")
                elif len(duplicate_arr) == 2:
                    #print("why")
                    centerline.append([x,sum(duplicate_arr)/len(duplicate_arr)])
                    topline.append([x,max(duplicate_arr)])
                    botline.append([x,min(duplicate_arr)])
                    duplicate_arr = []
                else:
                    pass
                    #print("wtf")
            
            duplicate_arr.append(y)


        return np.array(centerline),np.array(topline),np.array(botline)
        

    def ensureUniqueY(self,cnt,centerline):

        #expects [ [x,y],
                #  [x,y] ]
        
        arg_sort = cnt[:,0,0].argsort() #sort according to first column 

        cnt_sorted = cnt[arg_sort]


    #print cnt_sorted
        x = cnt_sorted[:,0,0]
        y = cnt_sorted[:,0,1]

        y_min = np.min(y)
        y_max = np.max(y)
       # print y_min
       # print y_max
        mid_y = (y_min + y_max)/2.0
        #print mid_y
        last_x_i = -1
        duplicate_arr = []
        
        idx_to_remove = []

        #remove duplicates that are not part of the worm
        in_worm = False
        for i,x_i in enumerate(x):
            #print i 
            #print x_i
            #print "EOS"
            if (not x_i == last_x_i) and (len(duplicate_arr) > 1) :

                np_dup = np.array(duplicate_arr)
                
                np_dup_pos = np_dup[np_dup[:,1]>=0]
                np_dup_neg = np_dup[np_dup[:,1]<0]
                
                #print np_dup_neg 
                np_dup_pos = np_dup_pos[np_dup_pos[:,1].argsort()]
                np_dup_neg = np_dup_neg[np_dup_neg[:,1].argsort()]

                #print np_dup_neg
                if np_dup_pos.size == 0:

                    if np.abs(np_dup_neg[-1,1] - np_dup_neg[-2,1]) > 0:        
                        for j in np_dup_neg[:-2]:
                            idx_to_remove.append(j[0])
                    else:
                        for j in np_dup_neg[:]:
                            idx_to_remove.append(j[0])
                elif np_dup_neg.size == 0:

                    if np.abs(np_dup_pos[0,1] - np_dup_pos[1,1]) > 0:        
                        for j in np_dup_pos[2:]:
                            idx_to_remove.append(j[0])
                    else:
                        for j in np_dup_pos[:]:
                            idx_to_remove.append(j[0])
                else:
                #print np_dup
                    assert np_dup_pos[0,1] >= 0 
                    assert np_dup_neg[-1,1] < 0
                    if np.abs(np_dup_pos[0,1] - np_dup_neg[-1,1]) > 0:        
                
                        for j in np_dup_pos[1:]:
                            
                            idx_to_remove.append(j[0])
                        for j in np_dup_neg[:-1]:
                            idx_to_remove.append(j[0])
                    else:
                        for j in np_dup_pos[:]:
                            idx_to_remove.append(j[0])
                        for j in np_dup_neg[:]:
                            idx_to_remove.append(j[0])
                duplicate_arr = []
                    
            
            duplicate_arr.append([i,(y[i]-mid_y)])
            #print duplicate_arr
            last_x_i = x_i

        #print cnt_sorted.shape
        print cnt_sorted.shape
        print len(idx_to_remove)
        cnt_sorted = np.delete(cnt_sorted,idx_to_remove,0)
        print cnt_sorted.shape
        #print cnt_sorted.shape

       # plt_h = plt.subplot()
        #plt_h.scatter(cnt_sorted[idx_to_remove,0,0],cnt_sorted[idx_to_remove,0,1],s=2,
                #color='r' )
        #plt_h.scatter(cnt_sorted[:,0,0],cnt_sorted[:,0,1],s=1)
        #plt.show()
        #print cnt_sorted
        return cnt_sorted
    


   
        
    def getContour(self,img_canny):

        _, contours, hierarchy =\
        cv2.findContours(img_canny.copy(),cv2.RETR_TREE,cv2.CHAIN_APPROX_NONE)
        
        #find biggest contour
        max_area = 0
        max_idx = 0
        for idx, contour in enumerate(contours) :
            area = cv2.contourArea(contour)
            if area > max_area : 
                max_idx = idx
                max_area = area
                
        #hull = cv2.convexHull(selected_contours[0])
        #approxPoly = cv2.approxPolyDP(selected_contours[0],8,True)
        return contours[max_idx]
        
    def getProcessedCnt(self,img): 
        img = fu.ensureGray(img)
        
        img_canny = self.getCanny(img)
        y_min,y_max,x_min,x_max = self.getChannelBoundImg(img_canny)
        img_bound = img_canny[y_min:y_max,x_min:x_max]
        img_brokenlines = self.breakLines(img_bound)
        cnt = self.getContour(img_brokenlines)
 
        return cnt


    def eraseLinesConv(self,img_canny,worm_x_min,worm_x_max):
        #assumes already cropped in y
        y_max = img_canny.shape[0]
        x_max = img_canny.shape[1]
        print y_max
        offset = 30
        width = 10
        #print worm_x_min
        #print worm_x_max
        window = np.ones([15,10])
        #window = img_canny[int(y_max/1.5):y_max,worm_x_min - offset: worm_x_min - offset + width]
        benchmark = np.sum(window)
        window = cv2.dilate(window,np.ones([5,5]),iterations=5)
        output1 =\
        cv2.filter2D(img_canny.copy(),-1,window,anchor =\
                (2,2),borderType=cv2.BORDER_CONSTANT)
        #output = cv2.morphologyEx(img_canny.copy(),cv2.MORPH_TOPHAT,window)
        #kernel = np.ones([1,4])
        #output1 = cv2.erode(output1,kernel,iterations=1)
        #output1 = cv2.dilate(output1,kernel,iterations=10)
        output2 =\
        cv2.filter2D(img_canny.copy(),-1,window,anchor =\
                (window.shape[1]-1,window.shape[0]-1),borderType=cv2.BORDER_CONSTANT)

        output1 = cv2.inRange(output1,0,np.max(output1)/3)
        output1 =  cv2.dilate(output1,np.ones([3,3]),iterations = 1)
        #output1 = cv2.erode(output1,np.ones([2,2]),iterations=20)
        print np.max(output1)
        #ret, output1 =  cv2.threshold(output1,np.max(output1)/1.8,1,cv2.THRESH_BINARY)
        #ret, output2 =  cv2.threshold(output2,45,255,cv2.THRESH_BINARY)

         
#
#        wind_idx = np.where(window == 1)
#
#        conv_idx = np.where(output1 == 1)
#
#        for i in range(len(conv_idx[0])):
#            x_i = conv_idx[0][i]
#            y_i = conv_idx[1][i]
#
#            for j in range(len(wind_idx[0])):
#                x_j = wind_idx[0][j]
#                y_j = wind_idx[1][j]
#
#                x_t = x_i + x_j-30
#                y_t = y_i + y_j-10
#
#                if (x_t < y_max) and (y_t < x_max):
#                    img_canny[x_t,y_t] = 0
#

        #img_canny = img_canny*255 + output1 #+ output2
        cv2.imshow('Window Output', img_canny*255-output1)
       # cv2.imshow('Window',window*255)
        cv2.imshow('Window1',output1)

        return (img_canny*255-output1)/255


    def radiusCalc1(self,filled_cnt,skel_curv,img_shape):

        #use filled contour to make life easier,output of np.nonzero
        #sort numpyd
        skel_curv_x = skel_curv[1]
        skel_curv_y = skel_curv[0]
        #print skel_curv_y
        sort_idx = skel_curv_x.argsort()
        skel_curv_x = skel_curv_x[sort_idx]
        skel_curv_y = skel_curv_y[sort_idx]

        cnt_1d_idx = np.ravel_multi_index(filled_cnt,img_shape)

        # follow convention where slope of first point is calculatable
        # and have the last point's slope follow the 2nd last point's
        # slope
        # but just set R = 0 for last point
        
        skel_R = []
        prev_R = 0
        delta_x_arr = []
        cnt_x_re = []
        cnt_y_re = []
        for i in range(len(skel_curv_x)-1):

            delta_x_t = skel_curv_x[i+1]-skel_curv_x[i] 
            delta_y_t = skel_curv_y[i+1]-skel_curv_y[i]
            
            delta_y_n0 = 1 
            if delta_x_t == 0:
                skel_R.append(prev_R)
                print "well"
                print prev_R
                continue
            else:
                pass
            delta_x_n0 = delta_y_n0 * (- delta_y_t)/(delta_x_t)
            delta_x_arr.append(delta_x_n0)    
            in_filled_cnt = True
            
            test_y = skel_curv_y[i]
            test_x = skel_curv_x[i]
            
            #print "test_y"
            #print test_y
            #print img_shape[0:-1]
            test_1d = np.ravel_multi_index(np.array([[test_y],[test_x]]),img_shape[0:-1])

            delta_y_n = 0
            delta_x_n = 0
            
            R = 0

            while in_filled_cnt :
                print len(np.where(cnt_1d_idx == test_1d))
                if len(np.where(cnt_1d_idx == test_1d)) == 0:
                    #out of contour
                    in_filled_cnt = False #unnecessary
                    break
                else :
                    print("yay")
                #update
                R = R + 1
                delta_y_n = delta_y_n + delta_y_n0
                delta_x_n = delta_x_n + delta_y_n*delta_x_n0
                test_y = test_y + delta_y_n
                test_x = test_x + delta_x_n

                try:

                    test_1d =\
                    np.ravel_multi_index(np.array([np.round(test_y),np.round(test_x)]),img_shape[0:-1])
                except:
                    break

            skel_R.append(R)
            cnt_x_re.append(test_x)
            cnt_y_re.append(test_y)

        skel_R.append(0)
        plt_h = plt.subplot()
        plt_h.scatter(cnt_x_re,cnt_y_re)
        #plt_h.scatter(range(len(delta_x_arr)),delta_x_arr)
        plt.show(block=False)

        return skel_R



        
            
        

    def radiusCalculator(self,cnt,skel_curv,skel_angle):
        #print skel_angle[1]
        skel_angle = skel_angle[1]
        skel_curv_x = skel_curv[0]
        skel_curv_y = skel_curv[1]

        for i in range(len(skel_curv_x)):
            
            skel_x_i = skel_curv_x[i]
            skel_y_i = skel_curv_y[i]
            
            if skel_angle[i] > 1.57 and skel_angle[i] < -1.57:
                continue

            y_s_1 = np.tan(skel_angle[i])
            print y_s_1
            #top edge
            #assume angle between -90 and 90 degrees if not pretend
            #like it doesn't exist
            x_s = 0

            #lazy way just look in one direction
            R = 0 
            top_not_found = True

            while top_not_found:

                y_s = np.round(x_s*y_s_1)
                
                x_matchs = np.where(skel_curv_x == x_s)
                y_matchs = np.where(skel_curv_y == y_s)

                if len(np.intersect1d(x_matchs,y_matchs)) > 0 :
                    #contour point
                    R = np.sqrt(x_s*x_s + y_s*y_s)
                    top_not_found = False
                    break
                    

                x_s = x_s + 1

        
            skel_R.append(R)        

            
            #bottom edge
        plt_h = plt.subplot()
        plt_h.plot(R)
        plt.show()

        return skel_R

    def angleCalc(self,cnt_skel):



        return skel_angle

    def prune(self,skeleton):
        #expects True and False

        img = img_as_ubyte(skeleton)
        skel_idx = np.nonzero(img)

        kernel_x = [-1, 0, 1,-1, 0, 1,-1, 0, 1]
        kernel_y = [-1,-1,-1, 0, 0, 0, 1, 1, 1]
        endpoints_x = []
        endpoints_y = []
        for i in range(len(skel_idx[0])):
            x_i = skel_idx[0][i]
            y_i = skel_idx[1][i]
            if len(np.nonzero(img[kernel_x+x_i,kernel_y+y_i])[0])<3:
                endpoints_x.append(x_i)
                endpoints_y.append(y_i)

        
        endpoints_x = np.array(endpoints_x)
        endpoints_y = np.array(endpoints_y)

        ep_idx = endpoints_x.argsort()
        
        endpoints_x = endpoints_x[ep_idx]
        endpoints_y = endpoints_y[ep_idx]

        endpoints_x[[0,-1]] = []
        endpoints_y[[0,-1]] = []


        kernel_x = [-1, 0, 1,-1, 1,-1, 0, 1]
        kernel_y = [-1,-1,-1, 0, 0, 1, 1, 1]
        #eat away endpoints till a branch point is encountered

        idx_to_remove = []
        for i,x_i in enumerate(endpoints_x):
            deleted = False
            y_i = endpoints_y[i]
            walking = True
            direction = [0,0]
            while walking:
                
                #linear array
                nbrs = np.nonzero(img[kernel_x+x_i,kernel_y+y_i])
                #print nbrs
                if len(nbrs[0])>1:
                    #print"in first part"
                    img[x_i,y_i]=0
                    break
                elif len(nbrs[0]) == 1: #endpoint
                    img[x_i,y_i]=0 #delete point
                    #print "in second part"
                    idx = nbrs[0][0]
                    dir_x = kernel_x[idx] 
                    dir_y = kernel_y[idx]
                    x_i = dir_x + x_i
                    y_i = dir_y + y_i
                    direction = [-dir_x, -dir_y]
                elif len(nbrs[0]) == 2:#2 neighbors -> shouldn't go backwards
                    #print "in third part"
                    idx = nbrs[0][0]
                    dir_x = kernel_x[idx] 
                    dir_y = kernel_y[idx]

                    if (dir_x == direction[0] and dir_y ==\
                            direction[0]):

                        idx = nbrs[0][1]
                        dir_x = kernel_x[idx] 
                        dir_y = kernel_y[idx]
                        #other neighbor is the way to go
                        direction = [-dir_x, - dir_y]
                        x_i = dir_x + x_i
                        y_i = dir_x + y_i

                    else:

                        x_i = dir_x + x_i
                        y_i = dir_y + y_i

                        direction = [- dir_x, - dir_y]

                else:
                    print("hmm")
                    break 


            
        
        
        #djistrikas from leftmost to rightmost endpoint



#        pQueue = Queue.PriorityQueue()
#
#        pQueue.append(0,[endpoints_x[0],endpoints_y[0]])
#
#        for i in range(len(endpoints_x)-1):
#            pass
#            
#    
        
        return [endpoints_x,endpoints_y],img
        #first pair is top left

    def getProcessedFrame(self,img):
        
        
        img = fu.ensureGray(img)
        
        img_canny = self.getCanny(img)
        y_min,y_max,x_min,x_max = self.getChannelBoundImg(img_canny)

        img_bound = img_canny[y_min:y_max,x_min:x_max]
        x_min, x_max = self.findEndPoints(img_bound)
        
        img_bound = self.eraseLinesConv(img_bound,x_min,x_max)
        cv2.imshow("wonderful",img_bound*255)
        img_bound = img_bound[:,x_min:x_max]
        img_brokenlines = self.breakLines(img_bound)
        cnt = self.getContour(img_brokenlines)


    
        cnt_correct = self.contourCorrect(cnt)
        centerline = [] 
        #centerline = self.findCenterLine(cnt_correct)
        cnt_unique= self.ensureUniqueY(cnt_correct,centerline)
        centerline, topline, botline = self.findCenterLine1(cnt_unique)
        #print centerline.shape
        contourbase = img_canny.copy()

        contourbase.fill(0)
        contourbase = fu.ensureColor(contourbase)
        #print cnt_correct
        #print cnt
        #print contourbase.shape
        #contourbase[cnt[:,0,1],cnt[:,0,0],0] = 255 
        #contourbase[centerline[:,1],centerline[:,0],0] = 255
        #center_x, center_y = self.getSpline(centerline)
        #contourbase[topline[:,1],topline[:,0],0] = 255
        #contourbase[botline[:,1],botline[:,0],0] = 255
        #top_x,top_y = self.getSpline(topline)
        #bot_x,bot_y = self.getSpline(botline)
        cv2.drawContours(contourbase,[cnt],-1,(0,255,0),thickness = cv2.FILLED)

        
        self.skeletonise(contourbase)
        skeleton = skeletonize(contourbase[:,:,1]/255)
        skel_img = 2*img_as_ubyte(skeleton)/5
        endpoints,prune_img = self.prune(skeleton)
        skel_img[endpoints] = 255

        #get skeleton index form and angle representation
        skel_idx = np.nonzero(prune_img)
        cnt_filled = np.nonzero(contourbase)
        cv2.imshow('woah',contourbase)
        modelUtil = ModelUtil()
        skel_R = self.radiusCalc1(cnt_filled,skel_idx,contourbase.shape)
        cv2.imshow('scikit skeleton',prune_img)















        #contourbase[centerline[:,1],centerline[:,0],0] = 255
        #contourbase[np.floor(center_y).astype(int),center_x.astype(int),0] = 255
        
       
        
        #contourbase[np.floor(top_y).astype(int),top_x.astype(int),1] = 255
        #contourbase[np.floor(bot_y).astype(int),bot_x.astype(int),2] = 255
       #print len(cnt_correct)
        #print len(cnt)
        #cv2.drawContours(contourbase,cnt_correct,-1,(255,0,0)) 
        #for point in cnt_correct:
        #    cv2.circle(contourbase,tuple(point),4,(0,255,0))
        
        return contourbase

    
if __name__ == "__main__" : 
    worm_detector = WormDetector()
    img_org = cv2.imread("Etaluma_worm.png")
    worm_detector.startTrackbars('trackbars')
    while True:
        img = worm_detector.getProcessedFrame(img_org)
        cv2.imshow('image',img)
        k = cv2.waitKey(30)
        if k == ord('e'):
            break
        
