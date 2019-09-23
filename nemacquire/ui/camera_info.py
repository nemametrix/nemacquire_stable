from PySide import QtGui

class CameraInfo(QtGui.QDialog):

    def __init__(self,p):

        super(CameraInfo,self).__init__(parent=p)
        self.setWindowTitle("Camera Information")
        self.p = p
        self.resize(290,142)
        self.disconnected_str = "Not Detected"

        self.verticalLayout = QtGui.QVBoxLayout(self)
        self.setLayout(self.verticalLayout) 
        self.camera_info = self.createLineInfoGraphic(
                            'Camera Model:',
                            self.disconnected_str,
                            self.verticalLayout)
    
        self.frames_rxd = self.createLineInfoGraphic(
                            'Frames Recieved:',
                            0,
                            self.verticalLayout)
        
        self.frames_lost = self.createLineInfoGraphic(
                            'Frames Lost:',
                            0,
                            self.verticalLayout)





    @staticmethod
    def createLineInfoGraphic(name,value,parentLayout):

        horizontalLayout = QtGui.QHBoxLayout()

        name_widget = QtGui.QLabel()
        name_widget.setText(str(name))
        horizontalLayout.addWidget(name_widget)

        value_widget = QtGui.QLabel()
        value_widget.setText(str(value))
        horizontalLayout.addWidget(value_widget)

        parentLayout.addLayout(horizontalLayout)

        return (name_widget, value_widget)

    def updateValues(self,camera_info_str,frames_lost, frames_rxd):
                
        self.camera_info[1].setText(camera_info_str)
        self.frames_lost[1].setText(str(frames_lost))
        self.frames_rxd[1].setText(str(frames_rxd))

    def reset(self):
        self.camera_info[1].setText(self.disconnected_str)
        self.frames_lost[1].setText(str(0))
        self.frames_rxd[1].setText(str(0))

