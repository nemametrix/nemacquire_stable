from camera_settings import CameraSettings
from PySide.QtGui import QApplication
from PySide import QtGui
from multiprocessing.queues import SimpleQueue
import sys

sys.path.append('protocol')

from video import VideoProcess, Command, CamPrm, get_framerate
import unittest

_instance = None

#Methods to check for varying levels of object equivalence
def is_variable_dict_equivalent(obj1, obj2):
   

    #all keys in 1 exist in 2, all keys in 2 exist in 1
    #implies they have same keys

    for k in obj1.__dict__:
        if k in obj2.__dict__:
            if obj2.__dict__[k] == obj1.__dict__[k]:
                pass
            else:
                return False
        else :
            return False


    for k in obj2.__dict__:
        if k in obj1.__dict__:
            if obj2.__dict__[k] == obj1.__dict__[k]:
                pass
            else:
                return False
        else :
            return False

    return True

def is_dict_equivalent(dict1, dict2):
   

    #all keys in 1 exist in 2, all keys in 2 exist in 1
    #implies they have same keys

    for k in dict1:
        if k in dict2:
            if dict2[k] == dict1[k]:
                pass
            else:
                return False
        else :
            return False


    for k in dict2:

        if k in dict1:
            if dict2[k] == dict1[k]:
                pass
            else:
                return False
        else :
            return False

    return True

class BaseQWidgetTestCase(unittest.TestCase):

    def setUp(self):
        super(BaseQWidgetTestCase, self).setUp()
        #singleton pattern for QApplication
        global _instance
        if _instance is None:
            _instance = QApplication([])


        self.app = _instance

    def tearDown(self):
        super(BaseQWidgetTestCase,self).tearDown()
        del self.app


class MockCFG():
    def __init__(self):
        self.triggered = False
        self.framerate_div = 0
        self.exposure_time = 1
        self.white_balance = True
        self.framerate_free = 10

    def save(self):
        pass

class MockNemacquire(QtGui.QWidget):

    def update_verified_exposure(self,exposure):
        pass

class CameraSettingsTestCase(BaseQWidgetTestCase):

    def setUp(self):

        super(CameraSettingsTestCase,self).setUp()
        self.test_ard_cmd_queue = SimpleQueue()
        self.test_img_cmd_queue = SimpleQueue()
        self.mock_cfg = MockCFG()
        self.mock_nemacquire = MockNemacquire()
        self.camera_settings_widget = CameraSettings(
                                self.mock_nemacquire,
                                self.test_ard_cmd_queue,
                                self.test_img_cmd_queue,
                                self.mock_cfg,
                                250)        


    def tearDown(self):
        super(CameraSettingsTestCase,self).tearDown()

    def test_reset(self):
        #check if reset action resets camera_settings_values to cfg values
        self.camera_settings_widget.initialize_fields()
        self.mock_cfg_old = self.mock_cfg
        self.camera_settings_widget.reset_fields()
        assert is_variable_dict_equivalent(self.mock_cfg_old, self.mock_cfg)

    def test_save(self):
        #test all values are set correctly after a save

        #Value Change
        self.camera_settings_widget.save()
        cmd, data = self.test_img_cmd_queue.get()
        results_dict = self.camera_diff_physical_values(data)
        self.camera_settings_widget.verifySettings(results_dict)
        assert is_dict_equivalent(results_dict,
                self.camera_settings_widget.settings_dict)
        
        #Type change - reset to old value if type conversion fails
        self.camera_settings_widget.save()
        cmd, data = self.test_img_cmd_queue.get()
        results_dict = self.camera_diff_physical_values(data,
                            diffType = "type change")
        self.camera_settings_widget.verifySettings(results_dict)
        assert is_dict_equivalent(results_dict,
                self.camera_settings_widget.settings_dict)

        #Missing value - keep old values if there is no corresponding key

    def test_save_error(self):
        #error during saving process
        #how to test?
        return True


    def camera_diff_physical_values(self,cur_settings_dict,
    diffType = "numerical change"):

        result_dict = {}
        if diffType == "type change":
            
            for key,value in cur_settings_dict.iteritems():

                if isinstance(value,bool):
                    result_dict[key] = None

                else:
                    result_dict[key] = None
        
        if diffType == "numerical change":
            
            for key,value in cur_settings_dict.iteritems():

                if isinstance(value,bool):
                    result_dict[key] = not value

                else:
                    result_dict[key] = value + 1

        if diffType == "missing values":
            pass


        return result_dict
        #send different values than what came in

    def check_type_of_settings(self):
        #check type of all settings in cfg and camera settings widget 
        return (
        isinstance(self.camera_settings_widget.settings_dict[CamPrm.triggered],int)
        
        and isinstance(self.camera_settings_widget.settings_dict[CamPrm.framerate_div],int)
        and isinstance(self.camera_settings_widget.settings_dict[CamPrm.exposure],int)
        and isinstance(self.camera_settings_widget.settings_dict[CamPrm.white_balance],bool)
        and isinstance(self.camera_settings_widget.settings_dict[CamPrm.framerate_free],int)

        and isinstance(self.camera_settings_widget.cfg.triggered,int)
        and isinstance(self.camera_settings_widget.cfg.framerate_div,int)
        and isinstance(self.camera_settings_widget.cfg.exposure_time,int)
        and isinstance(self.camera_settings_widget.cfg.white_balance,bool)
        and isinstance(self.camera_settings_widget.cfg.framerate_free,int))

if __name__ == "__main__":

    unittest.main()
