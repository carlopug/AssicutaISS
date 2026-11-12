"""Generatore di segnale Robot36 (usato per test e verifica del decoder)."""
import numpy as np

from .common import (FS, SYNC, SYNC_PORCH, Y_SCAN, SEPARATOR, PORCH, C_SCAN, WIDTH, HEIGHT,
                     F_SYNC, F_BLACK, F_WHITE, F_LEADER, VIS_ROBOT36, level_to_freq, rgb_to_ycbcr)


def vis_segments(code=VIS_ROBOT36):
    segs = [(F_LEADER, 0.300), (F_SYNC, 0.010), (F_LEADER, 0.300), (F_SYNC, 0.030)]
    bits = [(code >> i) & 1 for i in range(7)]
    bits.append(sum(bits) & 1)  # parità pari
    segs += [(1100.0 if b else 1300.0, 0.030) for b in bits]
    segs.append((F_SYNC, 0.030))
    return segs


def encode_robot36(rgb, fs=FS, vis=True, lead_silence=0.5, tail_silence=0.5, clock_ppm=0.0, amplitude=0.7):
    """Restituisce audio float32 a `fs` con l'immagine `rgb` (240x320x3) in Robot36.

    clock_ppm simula l'errore di clock della scheda audio del trasmettitore (slant).
    """
    rgb = np.asarray(rgb)
    assert rgb.shape == (HEIGHT, WIDTH, 3)
    y, cb, cr = rgb_to_ycbcr(rgb)

    freqs = []
    durs = []

    def add(f, d):
        freqs.append(np.atleast_1d(np.asarray(f, dtype=np.float64)))
        durs.append(np.full(freqs[-1].shape, d, dtype=np.float64))

    if vis:
        for f, d in vis_segments():
            add(f, d)
    for r in range(HEIGHT):
        add(F_SYNC, SYNC)
        add(F_BLACK, SYNC_PORCH)
        add(level_to_freq(y[r]), Y_SCAN / WIDTH)
        pair = r - (r % 2)
        if r % 2 == 0:
            chroma = (cr[pair] + cr[pair + 1]) / 2.0
            add(F_BLACK, SEPARATOR)
        else:
            chroma = (cb[pair] + cb[pair + 1]) / 2.0
            add(F_WHITE, SEPARATOR)
        add(F_LEADER, PORCH)
        add(level_to_freq(chroma), C_SCAN / WIDTH)

    f = np.concatenate(freqs)
    d = np.concatenate(durs) * (1.0 + clock_ppm * 1e-6)
    bounds = np.concatenate(([0.0], np.cumsum(d)))
    n = int(bounds[-1] * fs)
    t = (np.arange(n) + 0.5) / fs
    idx = np.clip(np.searchsorted(bounds, t, side="right") - 1, 0, len(f) - 1)
    phase = 2 * np.pi * np.cumsum(f[idx]) / fs
    sig = amplitude * np.sin(phase)
    return np.concatenate([np.zeros(int(lead_silence * fs)), sig,
                           np.zeros(int(tail_silence * fs))]).astype(np.float32)


def make_test_image():
    """Immagine di prova: barre colorate + gradiente + scacchiera."""
    img = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    bars = [(255, 255, 255), (255, 255, 0), (0, 255, 255), (0, 255, 0),
            (255, 0, 255), (255, 0, 0), (0, 0, 255), (0, 0, 0)]
    for i, c in enumerate(bars):
        img[:120, i * 40:(i + 1) * 40] = c
    img[120:180, :, :] = np.linspace(0, 255, WIDTH).astype(np.uint8)[None, :, None]
    yy, xx = np.mgrid[180:240, 0:WIDTH]
    chk = (((yy // 20) + (xx // 20)) % 2 * 255).astype(np.uint8)
    img[180:, :, 0] = chk
    img[180:, :, 1] = 128
    img[180:, :, 2] = 255 - chk
    return img
