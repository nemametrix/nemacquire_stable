from cv2 import VideoCapture as vc
class CameraApplication():
    
    def __init__ (self) : 
        for i in range(10):
            self.cam = vc( i ) #XIMEA Api        
            print(self.cam.isOpened())






if __name__ == "__main__" : 
    cameraApplication = CameraApplication()
