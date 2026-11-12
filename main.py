"""AssicutaISS - avvio dell'applicazione."""
import sys

from PySide6.QtWidgets import QApplication

from sstv_iss.config import Config
from sstv_iss.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    cfg = Config.load()
    w = MainWindow(cfg)
    w.show()
    rc = app.exec()
    cfg.save()
    sys.exit(rc)


if __name__ == "__main__":
    main()
