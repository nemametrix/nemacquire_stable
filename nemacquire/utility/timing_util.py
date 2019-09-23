import time
from circbuf import CircularBuffer



#Inspired by
#https://www.andreas-jung.com/contents/a-python-decorator-for-measuring-the-execution-time-of-methods
#

class TimingUtil():
    
    #decorator that finds execution time of a method and converts it to 'Hz'
    #Overhead seems less than 0.5ms (tested with time.sleep())
    @classmethod
    def freqit(cls,method):
        #calling with decorator effectively replaced 'method' with 'timed'
        def timed(*args,**kw):
            ts = time.time()
            #ensure original method is still called
            result = method(*args, **kw)
            #attach circular buffer to object binding method
            te = time.time()
            timed.circ_buf.append(1.0/(te-ts))
            b = '%r (%r, %r)' % \
                (method.__name__, args, kw )
            timed.bufferedprint(timed.circ_buf,b)
            
        def bufferedprint(circbuf,b):
            bufferedprint.print_count += 1

            if bufferedprint.print_count % 50 == 1:
                print b + ("%2.2f" % (circbuf.getAve())) + 'Hz'
            

        #should be defined once, act as initializers for these things
        timed.circ_buf = CircularBuffer(20)
        timed.bufferedprint = bufferedprint
        bufferedprint.print_count = 0
        print("Instantiated")
        return timed  

    #decorator that finds execution time of a method and displays it
    @classmethod
    def timeit(cls,method):
        #calling with decorator effectively replaced 'method' with 'timed'
        def timed(*args,**kw):
            ts = time.time()
            #ensure original method is still called
            result = method(*args, **kw)
            #attach circular buffer to object binding method
            te = time.time()
            timed.circ_buf.append(1000.0*(te-ts))
            b = '%r (%r, %r)' % \
                (method.__name__, args, kw )
            timed.bufferedprint(timed.circ_buf,b)
            
        def bufferedprint(circbuf,b):
            bufferedprint.print_count += 1
        #    print(bufferedprint.print_count)
            if bufferedprint.print_count % 50 == 1:
                print  b + ("%2.2f" % (circbuf.getAve())) + 'ms'
            

        #should be defined once, act as initializers for these things
        timed.circ_buf = CircularBuffer(20)
        timed.bufferedprint = bufferedprint
        bufferedprint.print_count = 0
        print("Instantiated")
        return timed  

    #decorator that finds the time difference between subsequent calls to a
    #function
    @classmethod
    def timebetweenit(cls,method):
        #calling with decorator effectively replaced 'method' with 'timed'
        def timed(*args,**kw):
            te = time.time()
            #ensure original method is still called
            result = method(*args, **kw)
            #attach circular buffer to object binding method
            if not timed.ts is None:
                timed.circ_buf.append(1000.0*(te-timed.ts))
                b = '%r (%r, %r)' % \
                    (method.__name__, args, kw )
                timed.bufferedprint(timed.circ_buf,b)
            timed.ts = te
            
        def bufferedprint(circbuf,b):
            bufferedprint.print_count += 1

            if bufferedprint.print_count % 50 == 1:
                print  b + ("%2.2f" % (circbuf.getAve())) + 'ms'
            

        #should be defined once, act as initializers for these things
        timed.circ_buf = CircularBuffer(20)
        timed.bufferedprint = bufferedprint
        bufferedprint.print_count = 0
        timed.ts = None
        print("Instantiated")
        return timed  

    #Decorator that finds execution time between subsequent calls to a function
    #closest to true fps
    @classmethod
    def freqbetweenit(cls,method):
        #calling with decorator effectively replaced 'method' with 'timed'
        def timed(*args,**kw):
            te = time.time()
            #ensure original method is still called
            result = method(*args, **kw)
            #attach circular buffer to object binding method
            if not timed.ts is None:
                timed.circ_buf.append(1.0/(te-timed.ts))
                b = '%r (%r, %r)' % \
                    (method.__name__, args, kw )
                timed.bufferedprint(timed.circ_buf,b)
            timed.ts = te
            
        def bufferedprint(circbuf,b):
            bufferedprint.print_count += 1

            if bufferedprint.print_count % 50 == 1:
                print  b + ("%2.2f" % (circbuf.getAve())) + 'Hz'
            

        #should be defined once, act as initializers for these things
        timed.circ_buf = CircularBuffer(20)
        timed.bufferedprint = bufferedprint
        bufferedprint.print_count = 0
        timed.ts = None
        print("Instantiated")
        return timed  

#TestClass with time.sleep()
#May not be accurate enough past sub-ms
class TestClass():
    @TimingUtil.timeit
    @TimingUtil.timeit
    def testMethod(self):
        time.sleep(0.01)#10ms


if __name__ == "__main__" :

    test = TestClass()
    for x in range (200):
        time.sleep(0.02)#20ms
        test.testMethod()
    
