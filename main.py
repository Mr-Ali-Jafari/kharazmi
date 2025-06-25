import sys
from cli.cli import main as cli_main
from gui.gui import MainWindow
from PyQt5.QtWidgets import QApplication

if __name__ == "__main__":
    if "--gui" in sys.argv:
        app = QApplication([])
        window = MainWindow()
        window.show()
        app.exec_()
    else:
        cli_main()

