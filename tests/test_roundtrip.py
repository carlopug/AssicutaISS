"""Round-trip: encoder Robot36 -> decoder, in condizioni pulite e degradate."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sstv_iss.sstv.common import FS  # noqa: E402
from sstv_iss.sstv.encoder import encode_robot36, make_test_image  # noqa: E402
from sstv_iss.sstv.robot36 import Robot36Decoder  # noqa: E402


def psnr(a, b):
    mse = np.mean((a.astype(float) - b.astype(float)) ** 2)
    return 10 * np.log10(255 ** 2 / max(mse, 1e-9))


def run_decoder(audio, out_dir=None, chunk=3072):
    events = []
    dec = Robot36Decoder(out_dir=out_dir, on_event=lambda k, i: events.append((k, i)))
    for i in range(0, len(audio), chunk):
        dec.feed(audio[i:i + chunk])
    dec.flush()
    return dec, events


@pytest.mark.parametrize("ppm", [0, 600, -600])
def test_clean(ppm, tmp_path):
    img = make_test_image()
    audio = encode_robot36(img, clock_ppm=ppm)
    dec, ev = run_decoder(audio, str(tmp_path))
    kinds = [k for k, _ in ev]
    assert "vis" in kinds and "image" in kinds, kinds
    info = dict(ev)["image"]
    assert not info["partial"]
    assert os.path.exists(info["path"])
    p = psnr(dec.image, img)
    print(f"ppm={ppm} PSNR={p:.1f} dB slant={info['slant_ppm']:+.0f}")
    assert p > 22


def test_noise(tmp_path):
    rng = np.random.default_rng(1)
    img = make_test_image()
    audio = encode_robot36(img, amplitude=0.5)
    audio = audio + rng.normal(0, 0.5 / np.sqrt(2) / 10 ** (10 / 20), len(audio)).astype(np.float32)  # SNR 10 dB
    dec, ev = run_decoder(audio, str(tmp_path))
    assert "image" in [k for k, _ in ev]
    p = psnr(dec.image, img)
    print(f"noise PSNR={p:.1f}")
    assert p > 18


def test_missing_vis_starts_on_sync(tmp_path):
    img = make_test_image()
    audio = encode_robot36(img, vis=False)
    dec, ev = run_decoder(audio, str(tmp_path))
    kinds = [k for k, _ in ev]
    assert ("start", {"mode": "sync"}) in ev
    assert "image" in kinds
    assert dict(ev)["image"]["lines"] >= 200


def test_no_false_trigger_on_noise():
    rng = np.random.default_rng(2)
    noise = rng.normal(0, 0.3, FS * 20).astype(np.float32)
    dec, ev = run_decoder(noise)
    assert not [k for k, _ in ev if k == "image"]
