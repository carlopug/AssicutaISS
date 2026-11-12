"""Attesa del dongle: assente all'avvio -> collegato -> scollegato a metà immagine -> ricollegato."""
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
from sstv_iss.sdr_source import DongleUnavailable  # noqa: E402
from sstv_iss.sstv.common import FS  # noqa: E402
from sstv_iss.sstv.encoder import encode_robot36, make_test_image  # noqa: E402

AUDIO = encode_robot36(make_test_image(), lead_silence=0.5, tail_silence=0.0).astype(np.float64)


class FakeTracker:
    def doppler(self, f0, t=None):
        return 0.0, 0.0


class FakeSource:
    """Simula il dongle. `plan` controlla le aperture: 'absent' o un numero di secondi di segnale prima della perdita."""
    plan = []
    opened = 0

    def __init__(self, out_queue, *a, **k):
        step = FakeSource.plan.pop(0) if FakeSource.plan else "absent"
        if step == "absent":
            raise DongleUnavailable("nessun dispositivo")
        FakeSource.opened += 1
        self.out, self.seconds = out_queue, step
        self.error, self.ended, self.overflows = None, False, 0
        self._stop = False
        self.last_data = time.time()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        rng = np.random.default_rng(FakeSource.opened)
        t_audio = np.arange(len(AUDIO)) / FS
        phase = 0.0
        for b in range(int(self.seconds * FS_IN) // BLOCK):
            if self._stop:
                return
            t = (b * BLOCK + np.arange(BLOCK)) / FS_IN
            a = np.interp(t, t_audio, AUDIO)
            ph = phase + 2 * np.pi * np.cumsum(250_000 + 4000 * a) / FS_IN
            phase = ph[-1]
            iq = np.exp(1j * ph) * 0.3 + (rng.normal(size=BLOCK) + 1j * rng.normal(size=BLOCK)) * 0.5
            self.out.put(iq.astype(np.complex64))
            self.last_data = time.time()
            time.sleep(0.002)           # più veloce del tempo reale
        self.ended = True               # "strappato via": la lettura finisce da sola

    def lost(self, timeout_s=3.0):
        return self.error is not None or self.ended or time.time() - self.last_data > timeout_s

    def stop(self):
        self._stop = True

    def set_gain(self, g):
        pass

    def set_center(self, hz):
        pass

    def set_ppm(self, p):
        pass


def test_wait_connect_lose_reconnect(monkeypatch):
    monkeypatch.setattr(E, "RtlSource", FakeSource)
    monkeypatch.setattr(E, "RETRY_S", 0.2)
    FakeSource.plan = ["absent", "absent", 20.0, "absent", 5.0]
    FakeSource.opened = 0
    cfg = Config(images_dir=tempfile.mkdtemp(), doppler=False)
    eng = E.Engine(cfg, FakeTracker())
    eng.start()
    assert eng.running
    log = []
    deadline = time.time() + 120
    while time.time() < deadline and FakeSource.opened < 2:
        while not eng.events.empty():
            log.append(eng.events.get())
        time.sleep(0.05)
    time.sleep(0.5)
    snap = eng.snapshot()
    eng.stop()
    while not eng.events.empty():
        log.append(eng.events.get())
    text = [str(i) for _, i in log]
    print("\n".join(text))
    assert FakeSource.opened == 2
    assert any("In attesa del dongle" in t for t in text)
    assert sum("Dongle collegato" in t for t in text) == 2
    assert any("Dongle scollegato" in t for t in text)
    images = [i for k, i in log if k == "image"]
    assert images and images[0]["partial"], "l'immagine interrotta va chiusa e salvata come parziale"
    assert not any(k == "error" for k, _ in log)
    assert snap["running"]
