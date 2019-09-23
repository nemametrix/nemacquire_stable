from PySide import QtGui, QtCore

class ArdUpdateDialog(QtGui.QDialog):

    def __init__(self,p):

        super(ArdUpdateDialog,self).__init__(parent=p)
        self.p = p

        self.horizontalLayout = QtGui.QHBoxLayout()
        self.setLayout(self.horizontalLayout)
        
        self.message_label = QtGui.QLabel()
        self.message_label.setText\
        ("Updating Arduino Firmware, do not disconnect amplifier !")
        self.horizontalLayout.addWidget(self.message_label)
        
        self.loading_qmovie = QtGui.QMovie(":/icon/busy_circle.gif")

        self.loading_label = QtGui.QLabel()
        self.loading_label.setMovie(self.loading_qmovie)
        self.loading_label.setMaximumSize(QtCore.QSize(25,25))
        self.loading_label.setScaledContents(True)
        self.horizontalLayout.addWidget(self.loading_label)        

                    
