"""Mappa ISS (punto sub-solare, cerchio di visibilità) e aggiornamento automatico del TLE."""
import math
import os
import sys
import tempfile
from datetime import datetime, timezone

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
from sstv_iss.gui.iss_map import footprint, split_antimeridian, subsolar  # noqa: E402
from sstv_iss.gui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def test_subsolar_equinox_and_solstice():
    lat, lon = subsolar(datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc).timestamp())
    assert abs(lat) < 1.0 and abs(lon) < 3.0
    lat, _ = subsolar(datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc).timestamp())
    assert abs(lat - 23.44) < 0.3


def test_footprint_radius():
    pts = footprint(0.0, 0.0, 420.0, 0.0)
    r = max(abs(la) for la, _ in pts)
    expected = math.degrees(math.acos(6371.0 / (6371.0 + 420.0)))
    assert abs(r - expected) < 0.1
    assert max(abs(la) for la, _ in footprint(0.0, 0.0, 420.0, -0.8)) > r     # orizzonte più basso: cerchio più largo


def test_split_antimeridian():
    segs = split_antimeridian([0, 1, 2, 3], [170, 178, -176, -170])
    assert len(segs) == 2


def make_window():
    w = MainWindow(Config(lat=37.6, lon=15.07, alt_m=586.0, images_dir=os.path.join(_tmp, "img")))
    calls = []
    w._bg = lambda f: calls.append(f)
    w._tle_try = 0.0
    return w, calls


def test_tle_auto_only_when_old_and_idle():
    w, calls = make_window()
    w.tracker.cache_age_s = lambda: 3600.0           # TLE fresco: niente
    w._tle_auto()
    assert not calls
    w.tracker.cache_age_s = lambda: 30 * 3600.0       # vecchio ma ricezione in corso: si aspetta
    w.engine.running = True
    w._tle_auto()
    assert not calls
    w.engine.running = False                          # vecchio e ricevitore fermo: si scarica, una volta all'ora
    w._tle_auto()
    w._tle_auto()
    assert len(calls) == 1
    assert "Aggiornamento automatico del TLE" in w.log.toPlainText()
