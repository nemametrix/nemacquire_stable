import numpy as np
import scipy as sp
#import matplotlib.pyplot as plt

class ModelUtil():
    def __init__(self):
        pass

    def samplefunc(self):

        x = np.arange(0,6.5,0.1)
        y = np.sin(x)
        cnt = []
        for i,x_i in enumerate(x):
            cnt.append([x_i,y[i]])

        return cnt

    def getSpline(self,cnt):
        #expects [ [x,y] [x,y]...]

        x = cnt[:,0]
        y = cnt[:,1]

        knots = np.arange(np.min(x),np.max(x),(np.min(x)-np.max(x))/100)
        tck = sp.splrep(x,y,k=3,s= 50)

        u = np.arange(np.min(x),np.max(x))
        
        new_points = sp.splev(u,tck)

        return u, new_points

    def curveRepr1(self,cnt):
        
        #Last point has same tangent as previous point

        #cnt_x = [cntsub[0] for cntsub in cnt]
        #cnt_y = [cntsub[1] for cntsub in cnt]

        cnt_x = cnt[0]
        cnt_y = cnt[1]
        u = np.arange(0,len(cnt_x))/float(len(cnt_x))
        
        print len(u)
        print len(cnt_x)
        
        theta_u = []
        
        #iterate up to 2nd last element in theta_u
        for i in range(0,len(cnt_x)-1):

            theta_u.append(np.arctan((cnt_y[i+1]-cnt_y[i])/(cnt_x[i+1]-cnt_x[i])))


        theta_u.append(theta_u[-1])

        return u, theta_u


    def curveRepr(self,cnt):
        
        #Last point has same tangent as previous point

        cnt_x = [cntsub[0] for cntsub in cnt]
        cnt_y = [cntsub[1] for cntsub in cnt]
        u = np.arange(0,len(cnt_x))/float(len(cnt_x))
        
        print len(u)
        print len(cnt_x)
        
        theta_u = []
        
        #iterate up to 2nd last element in theta_u
        for i in range(0,len(cnt_x)-1):

            theta_u.append(np.arctan((cnt_y[i+1]-cnt_y[i])/(cnt_x[i+1]-cnt_x[i])))


        theta_u.append(theta_u[-1])

        return u, theta_u


    def rectRepr(self,u,theta_u,init_x,init_y):


        cnt_x = [init_x]
        cnt_y = [init_y]

        for i in range(0,len(theta_u)-1):
            
            cnt_x.append(cnt_x[-1] + (u[i+1]-u[i])*np.sin(theta_u[i]))
            cnt_y.append(cnt_y[-1] + (u[i+1]-u[i])*np.cos(theta_u[i]))

        return cnt_x,cnt_y



if __name__ == "__main__" :

    mu = ModelUtil()
    cnt = mu.samplefunc()
    plt_h = plt.subplot()
    cnt_x = [cntsub[0] for cntsub in cnt]
    cnt_y = [cntsub[1] for cntsub in cnt]

    u,theta = mu.curveRepr(cnt)
    cnt_x,cnt_y = mu.rectRepr(u,theta,0,0)
    print(len(cnt_x))
    plt_h.plot(cnt_x,cnt_y)
    plt.show()


