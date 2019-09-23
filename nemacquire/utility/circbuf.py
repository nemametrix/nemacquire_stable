from collections import deque


class CircularBuffer(deque) :
    def __init__(self, len) :
        super(CircularBuffer, self).__init__(maxlen = len)
        self.len = len
        self.sum = 0
        
    def append(self,obj) :
        if len(self) == self.len :
            self.sum -= super(CircularBuffer,self).popleft()
        self.sum += obj
        super(CircularBuffer, self).append(obj)
            
    def getSum(self) :
        return self.sum
    
    def getAve(self) : 
        if len(self) is not 0 : 
            return self.sum/float(len(self))
        else : 
            return 0
        
        
        
if __name__ == '__main__' :
    #test
    circbuf = CircularBuffer(5)
    for x in range(20) :
        circbuf.append(x)
        print(circbuf.getAve())
        print 'length is' + str(len(circbuf))
    
    