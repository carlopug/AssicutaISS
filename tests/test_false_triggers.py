"""Falsi avvii sul rumore FM (il caso reale di fine passaggio) e immagine seguita da solo rumore."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sstv_iss.receiver import BLOCK, FS_IN, Receiver  # noqa: E402
from sstv_iss.sstv.common import FS  # noqa: E402
from sstv_iss.sstv.encoder import encode_robot36, make_test_image  # noqa: E402
from sstv_iss.sstv.robot36 import Robot36Decoder  # noqa: E402

IF = 250_000
DEV = 4_000
SIGNAL_GATE_DB = 0.5


def run(audio_signal, noise_seconds, seed, amp=0.3):
    """Modula in FM `audio_signal` (può essere None) e aggiunge `noise_seconds` di solo rumore."""
    rng = np.random.default_rng(seed)
    rx = Receiver()
    events = []
    dec = Robot36Decoder(out_dir=None, on_event=lambda k, i: events.append((k, i)))
    sig_blocks = 0
    if audio_signal is not None:
        t_audio = np.arange(len(audio_signal)) / FS
        sig_blocks = int(len(audio_signal) / FS * FS_IN) // BLOCK
    n_blocks = sig_blocks + int(noise_seconds * FS_IN) // BLOCK
    phase = 0.0
    for b in range(n_blocks):
        noise = (rng.normal(size=BLOCK) + 1j * rng.normal(size=BLOCK)) * 0.5
        if b < sig_blocks:
            t = (b * BLOCK + np.arange(BLOCK)) / FS_IN
            a = np.interp(t, t_audio, audio_signal)
            ph = phase + 2 * np.pi * np.cumsum(IF + DEV * a) / FS_IN
            phase = ph[-1]
            iq = np.exp(1j * ph) * amp + noise
        else:
            iq = noise
        r = rx.process(iq.astype(np.complex64), IF)
        dec.feed(r["audio"], signal_present=r["snr_db"] >= SIGNAL_GATE_DB)
    dec.flush()
    return events


def test_fm_noise_no_images():
    ev = run(None, 120, seed=11)
    starts = [i for k, i in ev if k == "start"]
    images = [i for k, i in ev if k == "image"]
    print("rumore FM: start", len(starts), "image", len(images))
    assert not images
    assert len(starts) <= 1


def test_image_then_noise_single_image():
    audio = encode_robot36(make_test_image(), lead_silence=1.0, tail_silence=0.2).astype(np.float64)
    ev = run(audio, 100, seed=12)
    images = [i for k, i in ev if k == "image"]
    print("immagine + rumore:", [(i["lines"], i["partial"]) for i in images],
          "start", sum(1 for k, _ in ev if k == "start"))
    assert len(images) == 1
    assert images[0]["lines"] >= 230
