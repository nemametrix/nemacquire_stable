# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_comm_stats.ui'
#
# Created: Wed Nov 16 17:01:33 2016
#      by: pyside-uic 0.2.15 running on PySide 1.2.2
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_CommStats(object):
    def setupUi(self, CommStats):
        CommStats.setObjectName("CommStats")
        CommStats.resize(290, 142)
        self.verticalLayout = QtGui.QVBoxLayout(CommStats)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.status_label = QtGui.QLabel(CommStats)
        self.status_label.setObjectName("status_label")
        self.horizontalLayout.addWidget(self.status_label)
        self.status_value = QtGui.QLabel(CommStats)
        self.status_value.setObjectName("status_value")
        self.horizontalLayout.addWidget(self.status_value)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.samples_rxd_label = QtGui.QLabel(CommStats)
        self.samples_rxd_label.setObjectName("samples_rxd_label")
        self.horizontalLayout_2.addWidget(self.samples_rxd_label)
        self.samples_rxd = QtGui.QLabel(CommStats)
        self.samples_rxd.setText("")
        self.samples_rxd.setObjectName("samples_rxd")
        self.horizontalLayout_2.addWidget(self.samples_rxd)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.horizontalLayout_3 = QtGui.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.samples_lost_label = QtGui.QLabel(CommStats)
        self.samples_lost_label.setObjectName("samples_lost_label")
        self.horizontalLayout_3.addWidget(self.samples_lost_label)
        self.samples_lost = QtGui.QLabel(CommStats)
        self.samples_lost.setText("")
        self.samples_lost.setObjectName("samples_lost")
        self.horizontalLayout_3.addWidget(self.samples_lost)
        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.retranslateUi(CommStats)
        QtCore.QMetaObject.connectSlotsByName(CommStats)

    def retranslateUi(self, CommStats):
        CommStats.setWindowTitle(QtGui.QApplication.translate("CommStats", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.status_label.setText(QtGui.QApplication.translate("CommStats",
            "Amplifier Version:", None, QtGui.QApplication.UnicodeUTF8))
        self.status_value.setText(QtGui.QApplication.translate("CommStats", "Disconnected", None, QtGui.QApplication.UnicodeUTF8))
        self.samples_rxd_label.setText(QtGui.QApplication.translate("CommStats", "Samples received:", None, QtGui.QApplication.UnicodeUTF8))
        self.samples_lost_label.setText(QtGui.QApplication.translate("CommStats", "Samples lost:", None, QtGui.QApplication.UnicodeUTF8))

