"""AssicutaISS - avvio dell'applicazione."""
import os
import sys
import time

from PySide6.QtCore import QLibraryInfo, QLocale, Qt, QTimer, QTranslator
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from sstv_iss import WINDOW_TITLE, __version__
from sstv_iss.config import APP_DIR, Config
from sstv_iss.i18n import set_language, tr

ASSETS = os.path.join(APP_DIR, "assets")
SPLASH_MIN_S = 2.0


def install_qt_translation(app, lang):
    """Traduce i testi standard di Qt (pulsanti Salva/Annulla, Sì/No, finestre file)."""
    qt_tr = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_tr.load(QLocale(lang), "qtbase", "_", path):
        app.installTranslator(qt_tr)


def set_windows_app_id():
    """Su Windows la barra delle applicazioni mostra l'icona del programma invece di quella di Python."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"AssicutaISS.Receiver.{__version__}")
        except Exception:
            pass


def main():
    set_windows_app_id()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    for name in ("icona.ico", "icona.png"):
        if os.path.exists(os.path.join(ASSETS, name)):
            app.setWindowIcon(QIcon(os.path.join(ASSETS, name)))
            break
    cfg = Config.load()
    set_language(cfg.language)
    install_qt_translation(app, cfg.language)

    splash = None
    t0 = time.time()
    splash_path = os.path.join(ASSETS, "splash.png")
    if os.path.exists(splash_path):
        splash = QSplashScreen(QPixmap(splash_path))
        splash.show()

    def status(text):
        if splash:
            splash.showMessage(f"v. {__version__}   ·   {text}", Qt.AlignBottom | Qt.AlignHCenter, QColor(170, 190, 220))
            app.processEvents()

    status(tr("Caricamento delle librerie..."))
    from sstv_iss.gui.main_window import MainWindow   # import pesante (Qt grafico, scipy, skyfield): dopo la splash
    status(tr("Preparazione dell'interfaccia..."))
    w = MainWindow(cfg)
    w.setWindowTitle(WINDOW_TITLE)

    def show_main():
        w.show()
        if splash:
            splash.finish(w)

    remaining = max(0.0, SPLASH_MIN_S - (time.time() - t0)) if splash else 0.0
    status(tr("Pronto"))
    QTimer.singleShot(int(remaining * 1000), show_main)
    rc = app.exec()
    cfg.save()
    sys.exit(rc)


if __name__ == "__main__":
    main()
