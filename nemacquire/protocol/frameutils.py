import cv2


def ensureColor(img):

    try :
        img_shape = img.shape
    except: 
        print ('Input has to be numpy nd.array')
    if(len(img_shape)==3):
        pass
        #Has color
    elif(len(img_shape)==2):
        #Assume grayscale
        img = cv2.cvtColor(img,cv2.COLOR_GRAY2BGR)
    else:
        raise ValueError('Input image is not valid')


    return img


def ensureGray(img):
    
    try :
        img_shape = img.shape
    except: 
        print ('Input has to be numpy nd.array')
    if(len(img_shape)==2):
        pass
        #Has color
    elif(len(img_shape)==3):
        #Assume grayscale
        img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    else:
        raise ValueError('Input image is not valid')


    return img
    

