
from PySide import QtGui, QtCore


#Use Qdialog instead of QMessagebox to prevent blocking !
class TimeoutWarningDialog(QtGui.QDialog):

    def __init__(self,p):

        super(TimeoutWarningDialog,self).__init__(parent=p)
        self.setWindowTitle("Camera not grabbing frames")
        self.messageLabel = QtGui.QLabel("Check connection from amplifier to "
                + "camera or disable Synchronized mode by unchecking:<br><br>"
               + "<b>Camera > Settings > Synchronized</b>")
        self.verticalLayout = QtGui.QVBoxLayout()
        self.setLayout(self.verticalLayout)
        self.verticalLayout.addWidget(self.messageLabel)
        self.button_box = QtGui.QDialogButtonBox()
        self.messageLabel.setMaximumWidth(600)
        self.messageLabel.setMinimumWidth(400)
        self.messageLabel.setWordWrap(True)
        self.verticalLayout.addWidget(self.button_box)
        ok = self.button_box.addButton(QtGui.QDialogButtonBox.Ok)
        ok.clicked.connect(self.close)
