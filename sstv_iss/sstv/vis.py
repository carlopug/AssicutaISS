"""Rilevamento dell'intestazione VIS SSTV.

Struttura: leader 300 ms @1900 Hz, break 10 ms @1200, leader 300 ms @1900,
start bit 30 ms @1200, 7 bit dati LSB-first (1100 Hz = 1, 1300 Hz = 0),
bit di parità pari, stop bit 30 ms @1200. L'immagine inizia subito dopo.
"""
import numpy as np


def _frac(cum, a, b):
    return (cum[b] - cum[a]) / np.maximum(b - a, 1)


def find_vis(trace_ms):
    """Cerca un VIS in una traccia di frequenza con 1 campione/ms.

    Restituisce (indice_ms_inizio_start_bit, codice, parita_ok) oppure None.
    L'indice è quello del primo ms dello start bit.
    """
    tr = np.asarray(trace_ms, dtype=np.float64)
    n = len(tr)
    if n < 620:
        return None
    near19 = np.concatenate(([0], np.cumsum(np.abs(tr - 1900.0) < 110.0)))
    near12 = np.concatenate(([0], np.cumsum(np.abs(tr - 1200.0) < 110.0)))
    cum = np.concatenate(([0.0], np.cumsum(tr)))

    i = np.arange(300, n - 300)
    if len(i) == 0:
        return None
    lead = _frac(near19, i - 290, i)
    start = _frac(near12, i + 4, i + 26)
    stop = _frac(near12, i + 274, i + 296)
    ok = (lead > 0.7) & (start > 0.6) & (stop > 0.5)
    bits = np.zeros((8, len(i)))
    for k in range(8):
        a = i + 30 + 30 * k + 5
        m = (cum[a + 20] - cum[a]) / 20.0
        bits[k] = m
        ok &= (m > 1000.0) & (m < 1400.0)
    if not ok.any():
        return None
    score = np.where(ok, lead + start + stop, -1.0)
    j = int(np.argmax(score))
    b = (bits[:, j] < 1200.0).astype(int)
    code = int(sum(int(b[k]) << k for k in range(7)))
    parity_ok = (int(b[:7].sum()) & 1) == int(b[7])
    return int(i[j]), code, parity_ok
