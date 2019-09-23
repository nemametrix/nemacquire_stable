from PySide import QtGui, QtCore
 

class NoiseTestDialog(QtGui.QDialog):
    pass_str = "Result: PASS\n\nYou're all set for recording!"
    fail_str = "Result: FAIL\n\nPlease resolve before recording"
    s1 = """
<ul>
<li><b>Step 1:</b> Set notch filter to None (top right filter dropdown)<br></li>
<li><b>Step 2:</b> Check that the microfludic channel is:<br>
<ul>
<li>Filled with saline solution (e.g. M9)</li>
<li>Free from debris and no worm is present</li>
<li>Free from bubbles<br></li>
</ul>"""
    s2 = """
<style>
a:link {
    color: rgb(33, 150, 243); 
}
</style>
<ul><li><b>Step 3</b>: If the noise level is <b>above 20uV</b>,<br>
adjust the setup following the <a href="https://nemametrix.com/troubleshoot/#noise">noise reduction guide.</a>
<br>
</ul>"""
    s3 = """
<style>
a:link {
    color: rgb(33, 150, 243); 
}
</style>
<br>
Feel free to contact technical support at 1.844.663.8749 or <br>
<a href="mailto:support@nemametrix.com">support@nemametrix.com</a> if you have any questions."""


    def __init__(self, p, threshold = 20):
        super(NoiseTestDialog, self).__init__(parent=p)

        self.threshold = threshold
        self.prev_vpp_uV = 0

        self.setWindowTitle(u"Noise Test")
        verticalLayout = QtGui.QVBoxLayout()
        self.setLayout(verticalLayout)
        
        s1_label = QtGui.QLabel()
        s1_label.setTextFormat(QtCore.Qt.RichText)
        s1_label.setText(self.s1)
        verticalLayout.addWidget(s1_label)
        s2_label = QtGui.QLabel()
        s2_label.setTextFormat(QtCore.Qt.RichText)
        s2_label.setText(self.s2)
        s2_label.setOpenExternalLinks(True)
        verticalLayout.addWidget(s2_label)

        self.groupbox =  QtGui.QGroupBox("")
        self.groupbox.setStyle(QtGui.QStyleFactory.create('plastique'))
        groupbox_v_layout = QtGui.QVBoxLayout(self.groupbox)
        self.vpp_name_label, self.vpp_label, self.container_widget = self.createLineInfo('Noise Level (uV):',
                                                  '000000',
                                                  groupbox_v_layout)
        
        self.result_label = QtGui.QLabel(self.fail_str)
        self.result_label.setAlignment(QtCore.Qt.AlignHCenter)	
        groupbox_v_layout.addWidget(self.result_label)
        self.groupbox.adjustSize()
        self.groupbox.setFixedWidth(self.groupbox.sizeHint().width())
        verticalLayout.addWidget(self.groupbox)
        verticalLayout.setAlignment(self.groupbox, QtCore.Qt.AlignHCenter)

        
        s3_label = QtGui.QLabel(self.s3)
        s3_label.setAlignment(QtCore.Qt.AlignHCenter)
        s3_label.setOpenExternalLinks(True)
        verticalLayout.addWidget(s3_label)

        
        self.button_box = QtGui.QDialogButtonBox()
        verticalLayout.addWidget(self.button_box)
        ok = self.button_box.addButton(QtGui.QDialogButtonBox.Close)
        ok.clicked.connect(self.close)
        
    #On windows sizeHint before render isn't reliable so we reimplement the fixed width logic after 
    #a resizeEvent (called upon first render)
    def resizeEvent(self,event):
        super(QtGui.QDialog,self).resizeEvent(event)
        self.vpp_label.setFixedWidth(self.vpp_label.sizeHint().width())
        self.vpp_name_label.setFixedWidth(self.vpp_name_label.sizeHint().width())
        self.container_widget.setFixedWidth(self.container_widget.sizeHint().width())
        self.groupbox.setFixedWidth(self.groupbox.sizeHint().width())
        
        
        
    @staticmethod
    def createLineInfo(name, value, parentLayout):
        
        container_widget = QtGui.QWidget()
        horizontalLayout = QtGui.QHBoxLayout()
        container_widget.setLayout(horizontalLayout)

        # spacer = QtGui.QSpacerItem(100, 1, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        # horizontalLayout.addItem(spacer)

        name_label = QtGui.QLabel()
        name_label.setText(str(name))
        horizontalLayout.addWidget(name_label)

        value_label = QtGui.QLabel()
        value_label.setText(str(value))
        value_label.adjustSize()
        value_label.setFixedWidth(value_label.sizeHint().width())
        value_label.setAlignment(QtCore.Qt.AlignRight)
        horizontalLayout.addWidget(value_label)

        container_widget.adjustSize()
        container_widget.setFixedWidth(container_widget.sizeHint().width())

        # spacer = QtGui.QSpacerItem(100, 1, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        # horizontalLayout.addItem(spacer)

        parentLayout.addWidget(container_widget)
        parentLayout.setAlignment(container_widget, QtCore.Qt.AlignHCenter)
        
        return (name_label, value_label, container_widget)

    def updateVpp(self, vpp):
        vpp_uV = int(vpp*1000000)
        if vpp_uV != self.prev_vpp_uV:
            # self.setIcon(QtGui.QMessageBox.Warning)
            self.vpp_label.setText("%6d" % vpp_uV)
            if vpp_uV <= self.threshold:
                self.result_label.setText(self.pass_str)
                self.result_label.setStyleSheet('color: rgb(50,255,50)')
            else:
                self.result_label.setText(self.fail_str)
                self.result_label.setStyleSheet('color: rgb(255,100,100)')                
            self.prev_vpp_uV = vpp_uV
