from PySide import QtGui, QtCore


#Use Qdialog instead of QMessagebox to prevent blocking !
class SyncWarningDialog(QtGui.QDialog):

    def __init__(self,p):

        super(SyncWarningDialog,self).__init__(parent=p)

        self.setWindowTitle("Camera is not in Synchronized mode")
        self.messageLabel = QtGui.QLabel("With an Amplifier connected, synchronized recording can be enabled using the Camera->Settings->Synchronized checkbox")
        self.verticalLayout = QtGui.QVBoxLayout()
        self.setLayout(self.verticalLayout)
        self.verticalLayout.addWidget(self.messageLabel)
        self.button_box = QtGui.QDialogButtonBox()
        self.verticalLayout.addWidget(self.button_box)
        ok = self.button_box.addButton(QtGui.QDialogButtonBox.Ok)
        ok.clicked.connect(self.close)
