"""Orizzonte radio unico: calcolo dalla quota, passaggi radenti, avvio automatico, impostazione a mano."""
import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skyfield.api import EarthSatellite  # noqa: E402

from sstv_iss.config import Config  # noqa: E402
from sstv_iss.doppler import IssTracker, fmt_el, radio_horizon  # noqa: E402

# TLE del 13/11/2026 e passaggio radente reale di quel giorno (14:21-14:26 UTC, el. max -0,1° da JM77mo, 586 m)
L1 = "1 25544U 98067A   26317.20662175  .00008559  00000+0  16132-3 0  9990"
L2 = "2 25544  51.6325 282.6584 0007349  20.2588 339.8690 15.49346920594859"
GRAZING = datetime(2026, 11, 13, 14, 23, 30, tzinfo=timezone.utc).timestamp()


def tracker(horizon):
    t = IssTracker(tempfile.mkdtemp())
    t.sat = EarthSatellite(L1, L2, "ISS (ZARYA)", t.ts)
    t.set_station(37.6136, 15.0731, 586.0, horizon)
    return t


def test_radio_horizon_from_altitude():
    assert radio_horizon(0) == 0.0
    assert radio_horizon(-20) == 0.0
    assert radio_horizon(586) == -0.8
    assert radio_horizon(2000) == -1.4


def test_config_horizon_auto_and_manual():
    c = Config(alt_m=586.0)
    assert c.horizon == -0.8
    c.horizon_deg = 2.5          # montagne: orizzonte alzato a mano
    assert c.horizon == 2.5


def test_grazing_pass_found_only_with_radio_horizon():
    assert tracker(0.0).pass_around(GRAZING) is None
    p = tracker(-0.8).pass_around(GRAZING)
    assert p is not None
    assert -0.8 < p["max_el"] < 0.0
    assert p["aos"] < datetime.fromtimestamp(GRAZING, timezone.utc) < p["los"]


def test_fmt_el():
    assert fmt_el(-0.12) == "-0.1°"
    assert fmt_el(37.4) == "37°"
