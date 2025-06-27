import sys
from gui.gui import MainWindow
from PyQt5.QtWidgets import QApplication

if __name__ == "__main__":

    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
