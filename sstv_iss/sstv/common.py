"""Costanti e funzioni comuni del modo SSTV Robot36."""
import numpy as np

FS = 48000  # frequenza di campionamento audio interna

# Temporizzazioni Robot36 (secondi)
SYNC = 0.009
SYNC_PORCH = 0.003
Y_SCAN = 0.088
SEPARATOR = 0.0045
PORCH = 0.0015
C_SCAN = 0.044
LINE = SYNC + SYNC_PORCH + Y_SCAN + SEPARATOR + PORCH + C_SCAN  # 0.150 s

WIDTH = 320
HEIGHT = 240

F_SYNC = 1200.0
F_BLACK = 1500.0
F_WHITE = 2300.0
F_LEADER = 1900.0

VIS_ROBOT36 = 8


def freq_to_level(f):
    """Frequenza (Hz) -> livello 0..255."""
    return np.clip((np.asarray(f) - F_BLACK) * (255.0 / (F_WHITE - F_BLACK)), 0.0, 255.0)


def level_to_freq(v):
    return F_BLACK + np.asarray(v, dtype=np.float64) * ((F_WHITE - F_BLACK) / 255.0)


def rgb_to_ycbcr(rgb):
    """RGB uint8 -> Y, Cb, Cr in 'studio swing' (BT.601), come MMSSTV."""
    rgb = rgb.astype(np.float64)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = 16.0 + (65.738 * r + 129.057 * g + 25.064 * b) / 256.0
    cb = 128.0 + (-37.945 * r - 74.494 * g + 112.439 * b) / 256.0
    cr = 128.0 + (112.439 * r - 94.154 * g - 18.285 * b) / 256.0
    return y, cb, cr


def ycbcr_to_rgb(y, cb, cr):
    y = 1.164 * (np.asarray(y, dtype=np.float64) - 16.0)
    cb = np.asarray(cb, dtype=np.float64) - 128.0
    cr = np.asarray(cr, dtype=np.float64) - 128.0
    r = y + 1.596 * cr
    g = y - 0.813 * cr - 0.391 * cb
    b = y + 2.018 * cb
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)
