"""IQ sintetico (FM + Doppler + errore di sintonia) -> Receiver con AFC -> decoder Robot36."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sstv_iss.engine import AFC_GAIN  # noqa: E402
from sstv_iss.receiver import BLOCK, FS_IN, Receiver  # noqa: E402
from sstv_iss.sstv.common import FS  # noqa: E402
from sstv_iss.sstv.encoder import encode_robot36, make_test_image  # noqa: E402
from sstv_iss.sstv.robot36 import Robot36Decoder  # noqa: E402

IF = 250_000
DEV = 4_000          # deviazione FM per ampiezza audio 1.0


def doppler(t):
    return 9_000 - 18_000 * t / 40.0     # rampa ±9 kHz, -450 Hz/s (peggio di un passaggio reale)


def test_receiver_doppler_afc(tmp_path):
    rng = np.random.default_rng(3)
    img = make_test_image()
    audio = encode_robot36(img, lead_silence=2.0, tail_silence=1.0).astype(np.float64)
    t_audio = np.arange(len(audio)) / FS
    tle_error = 1_500.0
    rx = Receiver()
    events = []
    dec = Robot36Decoder(out_dir=str(tmp_path), on_event=lambda k, i: events.append((k, i)))
    afc = 0.0
    phase = 0.0
    afc_hist = []
    n_blocks = int(len(audio) / FS * FS_IN) // BLOCK
    for b in range(n_blocks):
        t = (b * BLOCK + np.arange(BLOCK)) / FS_IN
        a = np.interp(t, t_audio, audio)
        f_inst = IF + doppler(t) + tle_error + DEV * a
        ph = phase + 2 * np.pi * np.cumsum(f_inst) / FS_IN
        phase = ph[-1]
        noise = (rng.normal(size=BLOCK) + 1j * rng.normal(size=BLOCK)) * 0.5
        iq = np.exp(1j * ph) * 0.3 + noise                 # SNR in canale ~ 10 dB
        shift = IF + doppler(t[0]) + afc                   # il tracker conosce il Doppler, non l'errore
        r = rx.process(iq.astype(np.complex64), shift)
        if r["snr_db"] > 4.0:
            afc = float(np.clip(afc + AFC_GAIN * r["freq_err"], -5000, 5000))
        afc_hist.append(afc)
        dec.feed(r["audio"])
    dec.flush()
    print("AFC finale", round(afc), "SNR", round(r["snr_db"], 1))
    assert abs(afc - tle_error) < 250
    kinds = [k for k, _ in events]
    assert "image" in kinds, kinds
    info = dict(events)["image"]
    assert info["lines"] >= 230
    mse = np.mean((dec.image.astype(float) - img.astype(float)) ** 2)
    psnr = 10 * np.log10(255 ** 2 / mse)
    print("PSNR", round(psnr, 1))
    assert psnr > 18
