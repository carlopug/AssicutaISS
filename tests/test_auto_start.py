"""Avvio automatico: i passaggi con elevazione massima sotto la soglia vengono saltati."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sstv_iss.config as C  # noqa: E402
import sstv_iss.telemetry as T  # noqa: E402

_tmp = tempfile.mkdtemp()
C.CONFIG_PATH = os.path.join(_tmp, "config.json")
C.STATION_PATH = os.path.join(_tmp, "stazione.json")
T.LOG_DIR = os.path.join(_tmp, "logs")

from PySide6.QtWidgets import QApplication  # noqa: E402

from sstv_iss.config import Config  # noqa: E402
from sstv_iss.gui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def make_window(max_el, threshold):
    cfg = Config(lat=37.6, lon=15.07, images_dir=os.path.join(_tmp, "img"), auto_pass=True, auto_min_el=threshold)
    w = MainWindow(cfg)
    now = datetime.now(timezone.utc)
    fake_pass = {"aos": now + timedelta(seconds=15), "tca": now + timedelta(minutes=5),
                 "los": now + timedelta(minutes=10), "max_el": max_el}
    w.tracker.look = lambda unix=None: (120.0, -0.5, 2300.0, -6.5)   # ISS a -0,5°: soglia di avvio superata
    w.tracker.pass_around = lambda unix: fake_pass
    started = []

    def fake_start():
        started.append(True)
        w.engine.running = True
        return True
    w._start = fake_start
    return w, started


def test_low_pass_is_skipped_once():
    w, started = make_window(max_el=5.0, threshold=10.0)
    for _ in range(3):
        w._slow_tick()
    log = w.log.toPlainText()
    assert not started
    assert log.count("passaggio saltato") == 1


def test_high_pass_starts():
    w, started = make_window(max_el=30.0, threshold=10.0)
    w._slow_tick()
    assert started == [True]
    assert "Avvio automatico: ISS in arrivo (el. max 30°)" in w.log.toPlainText()
    w.engine.running = False
