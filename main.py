"""AssicutaISS - avvio dell'applicazione."""
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from sstv_iss.config import Config
from sstv_iss.gui.main_window import MainWindow
from sstv_iss.i18n import set_language


def install_qt_translation(app, lang):
    """Traduce i testi standard di Qt (pulsanti Salva/Annulla, Sì/No, finestre file)."""
    tr = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if tr.load(QLocale(lang), "qtbase", "_", path):
        app.installTranslator(tr)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    cfg = Config.load()
    set_language(cfg.language)
    install_qt_translation(app, cfg.language)
    w = MainWindow(cfg)
    w.show()
    rc = app.exec()
    cfg.save()
    sys.exit(rc)


if __name__ == "__main__":
    main()
