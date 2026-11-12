"""AFC: una portante su un canale vicino non deve trascinare la sintonia; un segnale SSTV sì.

Riproduce il passaggio del 12/11 ore 19:19: una portante a ~+3,5 kHz all'inizio aveva portato l'AFC
al limite di +5 kHz, lasciando il ricevitore fuori centro durante le trasmissioni dell'ISS.
"""
import os
import sys
import tempfile
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sstv_iss.engine as E  # noqa: E402
from sstv_iss.config import Config  # noqa: E402
from sstv_iss.receiver import BLOCK, FS_IN  # noqa: E402
from sstv_iss.sstv.common import FS  # noqa: E402
from sstv_iss.sstv.encoder import encode_robot36, make_test_image  # noqa: E402

IF = 250_000
CARRIER_S, GAP_S = 10.0, 4.0
SSTV_OFFSET = 600.0
AUDIO = encode_robot36(make_test_image(), lead_silence=0.5, tail_silence=1.0).astype(np.float64)
SSTV_S = len(AUDIO) / FS


class FakeTracker:
    ready = False

    def doppler(self, f0, t=None):
        return 0.0, 0.0


class ScenarioSource:
    """Portante spostata di 3,5 kHz, poi rumore, poi un'immagine SSTV spostata di 600 Hz."""
    afc_trace = []

    def __init__(self, out_queue, *a, **k):
        self.out = out_queue
        self.error, self.ended, self.overflows = None, False, 0
        self._stop = False
        self.last_data = time.time()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        rng = np.random.default_rng(7)
        t_audio = np.arange(len(AUDIO)) / FS
        total = CARRIER_S + GAP_S + SSTV_S
        phase = 0.0
        for b in range(int(total * FS_IN) // BLOCK):
            if self._stop:
                return
            t = (b * BLOCK + np.arange(BLOCK)) / FS_IN
            t0 = t[0]
            noise = (rng.normal(size=BLOCK) + 1j * rng.normal(size=BLOCK)) * 0.5
            if t0 < CARRIER_S:
                ph = phase + 2 * np.pi * (IF + 3500.0) * np.arange(1, BLOCK + 1) / FS_IN
                iq = np.exp(1j * ph) * 1.0 + noise
            elif t0 < CARRIER_S + GAP_S:
                ph = phase + 2 * np.pi * IF * np.arange(1, BLOCK + 1) / FS_IN
                iq = noise
            else:
                a = np.interp(t - CARRIER_S - GAP_S, t_audio, AUDIO)
                ph = phase + 2 * np.pi * np.cumsum(IF + SSTV_OFFSET + 4000 * a) / FS_IN
                iq = np.exp(1j * ph) * 0.25 + noise
            phase = ph[-1]
            self.out.put(iq.astype(np.complex64))
            self.last_data = time.time()
            ScenarioSource.afc_trace.append((t0, ENGINE.afc_hz))
            time.sleep(0.004)
        self.ended = True

    def lost(self, timeout_s=3.0):
        return False

    def stop(self):
        self._stop = True

    def set_gain(self, g):
        pass

    def set_center(self, hz):
        pass

    def set_ppm(self, p):
        pass


ENGINE = None


def test_afc_ignores_carrier_and_tracks_sstv(monkeypatch):
    global ENGINE
    monkeypatch.setattr(E, "RtlSource", ScenarioSource)
    ScenarioSource.afc_trace = []
    cfg = Config(images_dir=tempfile.mkdtemp(), doppler=False, afc=True, record_wav=False)
    ENGINE = E.Engine(cfg, FakeTracker())
    events = []
    ENGINE.start()
    deadline = time.time() + 180
    total = CARRIER_S + GAP_S + SSTV_S
    while time.time() < deadline:
        while not ENGINE.events.empty():
            events.append(ENGINE.events.get())
        if ScenarioSource.afc_trace and ScenarioSource.afc_trace[-1][0] > total - 0.2:
            break
        time.sleep(0.1)
    time.sleep(1.0)
    ENGINE.stop()
    while not ENGINE.events.empty():
        events.append(ENGINE.events.get())
    tr = np.array(ScenarioSource.afc_trace)
    during_carrier = tr[tr[:, 0] < CARRIER_S + GAP_S, 1]
    during_sstv_end = tr[tr[:, 0] > CARRIER_S + GAP_S + SSTV_S * 0.5, 1]
    print(f"AFC max durante la portante: {np.max(np.abs(during_carrier)):.0f} Hz; "
          f"AFC nella seconda metà dell'immagine: {np.median(during_sstv_end):.0f} Hz")
    assert np.max(np.abs(during_carrier)) < 200, "la portante su canale vicino ha trascinato l'AFC"
    assert abs(np.median(during_sstv_end) - SSTV_OFFSET) < 250, "l'AFC non ha agganciato il segnale SSTV"
    assert any(k == "image" for k, _ in events), [k for k, _ in events]
    assert not any("AFC spostato" in str(i) for _, i in events)
