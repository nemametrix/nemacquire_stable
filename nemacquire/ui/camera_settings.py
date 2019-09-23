from collections import OrderedDict
from PySide import QtGui, QtCore
import sys
sys.path.append('protocol')
sys.path.append("data")

from video import VideoProcess, Command, CamPrm
from hackeeg import send_framerate_cmd

def customizeDialogFlags(d, title=None, close=False):
    # Using WindowsSystemMenuHint will place a nice icon on windows, but then
    # on OS X fails to adhere to the closeButtonHint
    flags = QtCore.Qt.Dialog | QtCore.Qt.CustomizeWindowHint
    if title:
        flags |= QtCore.Qt.WindowTitleHint
        d.setWindowTitle(title)
    if close:
        flags |= QtCore.Qt.WindowCloseButtonHint
    d.setWindowFlags(flags)

class CameraSettings(QtGui.QDialog):
    
    #copied from customization dialog in nemanalysis
    NORMAL = "background: rgb(78,78,78);"
    EDITED = "background: rgb(21,101,157);"
    
    NORMAL_CHECKBOX = "QCheckBox::indicator { border-color : rgb(78,78,78)}"
    EDITED_CHECKBOX = "QCheckBox::indicator { border-color : rgb(21,101,157)}"

    def __init__(self,p,ard_cmd_queue,img_cmd_queue,cfg,base_freq):
        
        self.p = p
        self.recording = False
        self.base_freq = base_freq
        self.verified = True
        self.cfg = cfg
        self.img_cmd_queue = img_cmd_queue
        self.ard_cmd_queue = ard_cmd_queue
        super(CameraSettings,self).__init__(parent=p)

        msg_body =  "Out of range camera settings have been set to closest possible values. "+\
                "Please review camera settings"
        #Parent has to be QMainWindow or mouse events do not get propogated to QMessageBox or QDialog
        #on mac os x
        self.msgbox = QtGui.QMessageBox(QtGui.QMessageBox.Information,
                                        u"Camera settings out of range",
                                        msg_body,
                                        parent=self)
        self.msgbox.setIcon(QtGui.QMessageBox.Warning)
        self.msgbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.msgbox.setText(msg_body)
        self.msgbox_ok_button = self.msgbox.addButton(QtGui.QMessageBox.Ok)
        self.settings_dict = OrderedDict({}) # ordered as that determines order in UI
        self.settings_dict_temp = {}
        
        self.tool_tips = {}
        self.initialize_fields() # fills in self.settings_dict
        verticalLayout = QtGui.QVBoxLayout()
        self.setLayout(verticalLayout)

        self.widget_dict = {}
        settings_dict_keys = self.settings_dict.keys()
        spacerItem1 = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        verticalLayout.addItem(spacerItem1)
        for k in settings_dict_keys :
            value = self.settings_dict[k]
            container_widget = QtGui.QWidget()
            horizontal_layout = QtGui.QHBoxLayout()
            horizontal_layout.setContentsMargins(0,0,0,0)
            container_widget.setLayout(horizontal_layout)

            if k == CamPrm.framerate_div:
                # special case
                self.create_framerate_settingBox(verticalLayout)
                continue

            label = QtGui.QLabel()
            label.setText(k)

            if isinstance(value,bool):
                selection = QtGui.QCheckBox()
                selection.setChecked(value)
                selection.stateChanged.connect(self.field_changed)
                selection.stateChanged.connect(self.disable_unused_params)
                validator = None
            elif isinstance(value,int):
                # For framerate_free and exposure
                selection = QtGui.QLineEdit()
                selection.setText(str(value))
                selection.setFixedWidth(60)
                selection.setAlignment(QtCore.Qt.AlignRight)
                validator = QtGui.QIntValidator(1,1100)
                selection.setValidator(validator)
                selection.textEdited.connect(self.field_changed)
                selection.textEdited.connect(self.disable_unused_params)
            elif isinstance(value,float):
                # for gain
                selection = QtGui.QLineEdit()
                selection.setText(str(value))
                selection.setFixedWidth(60)
                selection.setAlignment(QtCore.Qt.AlignRight)
                validator = QtGui.QDoubleValidator(0.0,30.0,2)
                validator.setNotation(validator.StandardNotation)
                validator.setRange(0.0,30.0)
                validator.setDecimals(2)
                selection.setValidator(validator)
                selection.textEdited.connect(self.field_changed)
                selection.textEdited.connect(self.disable_unused_params)
            else:
                assert False, type(value)
            self.widget_dict[k] = (label, selection, validator, type(value))

            horizontal_layout.addWidget(label)
            # horizontal spacer within label to make right element pushed to righthand side
            spacer = QtGui.QSpacerItem(1, 1, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
            horizontal_layout.addItem(spacer)
            horizontal_layout.addWidget(selection)
            if k in self.tool_tips:
                container_widget.setToolTip(self.tool_tips[k])
            verticalLayout.addWidget(container_widget)

        spacerItem2 = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        verticalLayout.addItem(spacerItem2)

        self.button_box = QtGui.QDialogButtonBox()
        verticalLayout.addWidget(self.button_box)
        self.button_box.addButton(QtGui.QDialogButtonBox.Save)
        self.button_box.addButton(QtGui.QDialogButtonBox.Close)
        self.button_box.addButton(QtGui.QDialogButtonBox.Reset)

        self.button_save = self.button_box.button(QtGui.QDialogButtonBox.Save)
        self.button_reset = self.button_box.button(QtGui.QDialogButtonBox.Reset)
        self.button_reset.setText("Revert")
        self.button_close =\
        self.button_box.button(QtGui.QDialogButtonBox.Close)
        self.button_save.clicked.connect(self.save)
        self.button_reset.clicked.connect(self.reset_fields)
        self.button_close.clicked.connect(self.reset_fields)
        self.button_close.clicked.connect(self.close)
        self.button_close.setText("Close")
        self.update_widget()
        self.update_vid_process()


    def gray_out_when_recording(self):
       
        self.recording = True
        for k in self.widget_dict.keys():
            label, selection, validator, type = self.widget_dict[k]
            selection.parentWidget().setEnabled(False)
        self.button_save.setEnabled(False)
        self.button_reset.setEnabled(False)
        self.button_close.setEnabled(True)

    def revert_after_recording(self):
        
        self.recording = False
        self.update_widget()

    def recording_event(self,recording = False):
        if recording:
            self.gray_out_when_recording()
        else:
            self.revert_after_recording()

    def create_framerate_settingBox(self,verticalLayout):

        value = self.settings_dict[CamPrm.framerate_div]
        container_widget = QtGui.QWidget()
        horizontal_layout = QtGui.QHBoxLayout()
        horizontal_layout.setContentsMargins(0,0,0,0)
        container_widget.setLayout(horizontal_layout)
        
        label = QtGui.QLabel()
        label.setText(CamPrm.framerate_div)
        selection = QtGui.QComboBox()
        selection.setStyleSheet(self.p.style_sheet)
        selection.setFixedWidth(140)
        selection.view().setLayoutDirection(QtCore.Qt.RightToLeft)
        freq = self.base_freq/2.0
        for divisor in range(1,8): 
            selection.insertItem(divisor, "%.6f" % freq) 
            freq = freq/2.0


        validator = None

        self.widget_dict[CamPrm.framerate_div] = (label, selection, validator, type(value))

        self.set_ui_framerate_div(self.settings_dict[CamPrm.framerate_div])
        selection.currentIndexChanged.connect(self.field_changed)
        selection.currentIndexChanged.connect(self.disable_unused_params)
        horizontal_layout.addWidget(label)
        horizontal_layout.addWidget(selection)
        if CamPrm.framerate_div in self.tool_tips:
            container_widget.setToolTip(self.tool_tips[CamPrm.framerate_div])
        verticalLayout.addWidget(container_widget)

    def get_framerate_div_from_ui(self):
        label, selection, validator, value =\
        self.widget_dict[CamPrm.framerate_div] 
        return selection.currentIndex() + 1
    
    def set_ui_framerate_div(self,div):
        label, selection, validator, value =\
        self.widget_dict[CamPrm.framerate_div] 
        selection.setCurrentIndex(div-1)
        
    def update_framerate(self):
        div = self.get_framerate_div_from_ui()
        send_framerate_cmd(self.ard_cmd_queue,div)


    def update_camera_settings_ui(self,cur_settings_dict): 
        settings_out_of_range = False
        ignore_exp_gain = False
        if cur_settings_dict[CamPrm.auto_exp_gain]:
            ignore_exp_gain = True
        for k in cur_settings_dict :
            if k not in self.settings_dict:
                continue    
            phys_value = cur_settings_dict[k]
            soft_value = self.settings_dict[k]
            #print 'physically ' + str(phys_value) + ', softly ' +\
            #str(soft_value)
            old_value = self.settings_dict[k]
        
            val_type = self.widget_dict[k][3]
            #print val_type
            if val_type is int:
                camera_value = int(round(phys_value))
            elif val_type is float:
                camera_value = float(round(phys_value*1000)/1000.0)
            elif val_type is bool:
                camera_value = bool(phys_value)
            else:
                raise ValueError
            if not(( not ignore_exp_gain) and (k == CamPrm.exposure or k == CamPrm.gain)):
                if camera_value != soft_value:
                    settings_out_of_range = True
            self.settings_dict[k] = camera_value

             
        self.verified = True
        self.update_widget()
        self.update_config_variables()
        if self.isVisible():
            if settings_out_of_range:
                self.show_camera_settings_updated_dialog()
            else:
                self.close()
            

    def field_changed(self):
        sender = self.sender()

        if isinstance(sender,QtGui.QCheckBox):
            pass
            #sender.setStyleSheet(CameraSettings.EDITED_CHECKBOX)
        elif isinstance(sender,QtGui.QLineEdit):
            sender.setStyleSheet(CameraSettings.EDITED)

    def field_saved(self,fieldWidget):

        if isinstance(fieldWidget,QtGui.QCheckBox):
            pass
            #fieldWidget.setStyleSheet(CameraSettings.EDITED_CHECKBOX)
        elif isinstance(fieldWidget,QtGui.QLineEdit):
            fieldWidget.setStyleSheet(CameraSettings.NORMAL)

    def updateLimits(self,limits_dict):
        widget_dict_keys = self.widget_dict.keys()

        widget_dict_keys.remove(CamPrm.framerate_div)
        for k in widget_dict_keys:            
            label, selection, validator, val_type = self.widget_dict[k] 
            if val_type is int:
                limits = limits_dict[k]

                if k == CamPrm.framerate_free:
                    validator.setRange(int(limits[0]),200)
                else:
                    validator.setRange(int(limits[0]),int(limits[2]))
            elif val_type is float:
                limits = limits_dict[k]
                #print limits
                validator.setRange(float(limits[0]), float(limits[2]),2)

    def initialize_fields(self): 
        
        self.settings_dict[CamPrm.triggered] = self.cfg.triggered
        self.settings_dict[CamPrm.framerate_div] = self.cfg.framerate_div
        self.settings_dict[CamPrm.framerate_free] = int(self.cfg.framerate_free)
        self.settings_dict[CamPrm.auto_exp_gain] = self.cfg.auto_exp_gain
        self.settings_dict[CamPrm.exposure] = int(self.cfg.exposure_time)
        self.settings_dict[CamPrm.gain] = float(self.cfg.gain)

        self.tool_tips[CamPrm.triggered] =\
                "Set camera to be externally triggered. Camera\n"\
                + "is triggered by Amplifier to achieve synchronization\n"\
                + "with EPG recording."

        self.tool_tips[CamPrm.framerate_div] = "Framerate selection is limited"\
        +" in Synchronized mode."

    def reset_fields(self):
        
        self.initialize_fields()
        self.update_widget()
        
    def open_settings_dialog(self):
        
        self.initialize_fields()
        self.update_widget()
        self.show()


    def update_widget(self):
        if self.recording:
            return
        
        if self.verified:
            self.button_save.setEnabled(True)
        else:
            self.button_save.setEnabled(False)

        self.button_close.setEnabled(True)
        self.button_reset.setEnabled(True)

        widget_dict_keys = self.widget_dict.keys()
        label, selection, validator, value =\
        self.widget_dict[CamPrm.framerate_div]
        
        self.set_ui_framerate_div(self.settings_dict[CamPrm.framerate_div])
        
        if self.verified :
            selection.parentWidget().setEnabled(True)
        else :    
            selection.parentWidget().setEnabled(False)

        widget_dict_keys.remove(CamPrm.framerate_div)
        for k in widget_dict_keys:            
            label, selection, validator, value = self.widget_dict[k]
            if self.verified:
                self.field_saved(selection)
            if value is bool:
                selection.setChecked(self.settings_dict[k])
            elif value is int:
                selection.setText(str(self.settings_dict[k]))
            elif value is float:
                selection.setText("%0.2f"%self.settings_dict[k])
            else : 
                assert False, type(value) 

            if self.verified :
                selection.parentWidget().setEnabled(True)
            else :    
                selection.parentWidget().setEnabled(False)
    
        #We apply additional constraints to determine which 
        #tools we want to disable (nothing is enabled in this 
        #section)

        #Disable right framerate selection tools

        self.disable_unused_params()

    def disable_unused_params(self):


        if self.recording:
            return

        label_m, selection_m, validator_m, value_m =\
        self.widget_dict[CamPrm.triggered]

        label_f, selection_f, validator_f, value_f =\
        self.widget_dict[CamPrm.framerate_free]
        
        label_t, selection_t, validator_t, value_t =\
        self.widget_dict[CamPrm.framerate_div]
        
        #Disable exposure/gain selection when auto exposure and gain is on
        selection_gain = self.widget_dict[CamPrm.gain][1]
        selection_exp = self.widget_dict[CamPrm.exposure][1]
        selection_aeag = self.widget_dict[CamPrm.auto_exp_gain][1]
        
        if self.verified:
            selection_f.parentWidget().setEnabled(True)
            selection_t.parentWidget().setEnabled(True)
            selection_exp.parentWidget().setEnabled(True)
            selection_gain.parentWidget().setEnabled(True)

        if selection_m.isChecked() :
            selection_f.parentWidget().setEnabled(False)

        else :
            selection_t.parentWidget().setEnabled(False)

        if selection_aeag.isChecked():
            selection_gain.parentWidget().setEnabled(False)
            selection_exp.parentWidget().setEnabled(False)

    def update_vid_process(self): 
        self.img_cmd_queue.put((
                        Command.new_settings,
                        self.settings_dict))
          


    def update_config_variables(self):

        self.cfg.framerate_div = self.settings_dict[CamPrm.framerate_div]
        self.cfg.triggered = self.settings_dict[CamPrm.triggered]
        self.cfg.exposure_time =  int(self.settings_dict[CamPrm.exposure])
        #self.cfg.white_balance = self.settings_dict[CamPrm.white_balance]
        self.cfg.framerate_free = int(self.settings_dict[CamPrm.framerate_free])
        self.cfg.gain = self.settings_dict[CamPrm.gain]
        self.cfg.auto_exp_gain = self.settings_dict[CamPrm.auto_exp_gain]
        self.cfg.save()

    def save(self):
        
        widget_dict_keys = self.widget_dict.keys()
        self.settings_dict[CamPrm.framerate_div] = self.get_framerate_div_from_ui()
        widget_dict_keys.remove(CamPrm.framerate_div)
        #TODO save to config file
        for k in widget_dict_keys:
            label, selection, validator, val_type = self.widget_dict[k]
            
            if val_type is bool: 
                value = selection.isChecked()
            elif val_type is int:  
                text =  selection.text()
                value = int(text)
            elif val_type is float:
                text = selection.text()
                value = float(text)
            else :
                assert False, type(value)
            self.settings_dict[k] = value
        
        self.update_framerate()
        self.update_vid_process()
        self.verified = False
        self.update_config_variables()
        self.update_widget()
        
    def show_camera_settings_updated_dialog(self):


        # workaround to prevent model dialog (it's nice to see the data and not drop data)
       
        customizeDialogFlags(self.msgbox,u"Camera settings out of range")
        self.msgbox.show()


    
