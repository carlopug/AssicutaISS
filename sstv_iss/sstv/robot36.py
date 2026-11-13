"""Decoder Robot36 a flusso continuo, con rilevamento VIS, avvio su treno di sync e correzione slant."""
import os
import time

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import firwin, lfilter

from ..i18n import tr
from .common import (FS, SYNC, SYNC_PORCH, Y_SCAN, SEPARATOR, PORCH, LINE, WIDTH, HEIGHT,
                     VIS_ROBOT36, freq_to_level, ycbcr_to_rgb)
from .vis import find_vis

MIN_LINES_TO_SAVE = 30      # sotto questa soglia l'immagine è considerata un falso avvio
SYNC_LOSS_LINES = 20        # linee consecutive senza sync prima di chiudere l'immagine (regge brevi affievolimenti)
TRAIN_MIN_PULSES = 6        # sync consecutivi richiesti per partire senza VIS
PULSE_MEDIAN_TOL = 150.0    # Hz: scostamento massimo della mediana di un sync da 1200 Hz
PULSE_MIN_FRACTION = 0.45   # frazione minima di campioni del sync entro ±250 Hz da 1200
MAX_SLANT = 0.01           # errore massimo di clock accettato (1%)
# frazione minima di righe con il proprio sync perché l'immagine sia salvata
MIN_SYNC_QUALITY = {"vis": 0.15, "sync": 0.3}


class ToneDemod:
    """Audio reale -> frequenza istantanea (Hz), via mixer complesso + FIR + discriminatore."""

    def __init__(self, fs=FS, center=1700.0, cutoff=1000.0, taps=97):
        self.fs = fs
        self.center = center
        self.w = 2 * np.pi * center / fs
        self.phase = 0.0
        self.h = firwin(taps, cutoff, fs=fs)
        self.zi = np.zeros(taps - 1, dtype=np.complex128)
        self.prev = 1.0 + 0j

    def process(self, x):
        x = np.asarray(x, dtype=np.float64)
        if len(x) == 0:
            return np.zeros(0, np.float32)
        ph = self.phase + self.w * np.arange(len(x))
        self.phase = (self.phase + self.w * len(x)) % (2 * np.pi)
        z, self.zi = lfilter(self.h, 1.0, x * np.exp(-1j * ph), zi=self.zi)
        prev = np.empty_like(z)
        prev[0] = self.prev
        prev[1:] = z[:-1]
        self.prev = z[-1]
        d = np.angle(z * np.conj(prev))
        return (self.center + d * (self.fs / (2 * np.pi))).astype(np.float32)


class GrowBuffer:
    """Buffer crescente indicizzato con indici di campione globali."""

    def __init__(self, capacity=1 << 20):
        self.data = np.zeros(capacity, np.float32)
        self.base = 0       # indice globale di data[0]
        self.n = 0          # campioni validi

    @property
    def end(self):
        return self.base + self.n

    def append(self, x):
        need = self.n + len(x)
        if need > len(self.data):
            new = np.zeros(max(need, 2 * len(self.data)), np.float32)
            new[:self.n] = self.data[:self.n]
            self.data = new
        self.data[self.n:need] = x
        self.n = need

    def get(self, a, b):
        a = max(int(a), self.base)
        b = min(int(b), self.end)
        return self.data[a - self.base:max(a, b) - self.base]

    def trim_before(self, g):
        g = int(min(max(g, self.base), self.end))
        k = g - self.base
        if k <= 0:
            return
        self.data[:self.n - k] = self.data[k:self.n]
        self.n -= k
        self.base = g


def _box_means(seg, start, stop, count):
    """Media del segnale `seg` su `count` intervalli contigui tra le posizioni frazionarie start..stop."""
    c = np.concatenate(([0.0], np.cumsum(seg, dtype=np.float64)))
    edges = np.linspace(start, stop, count + 1)
    edges = np.clip(edges, 0, len(seg))
    ci = np.interp(edges, np.arange(len(c)), c)
    w = np.diff(edges)
    w[w <= 0] = 1e-9
    return np.diff(ci) / w


class Robot36Decoder:
    """Riceve audio a 48 kHz (blocchi qualsiasi) e produce immagini Robot36.

    on_event(kind, info) viene chiamata con:
      'vis'     {'code', 'supported'}
      'start'   {'mode': 'vis'|'sync'}
      'image'   {'path', 'partial', 'lines'}
      'discard' {'lines'}
    """

    def __init__(self, out_dir=None, on_event=None, fs=FS, clock=None):
        """clock(): istante unix corrispondente all'ultimo campione ricevuto (default: ora attuale).
        Per i file si passa un orologio basato sulla posizione nel file."""
        self.clock = clock or time.time
        self.fs = fs
        self.out_dir = out_dir
        self.on_event = on_event or (lambda kind, info: None)
        self.T_nom = LINE * fs
        self.demod = ToneDemod(fs)
        self.buf = GrowBuffer()
        self.pulses = []
        self.scan_pos = 0
        self.vis_skip_until = 0
        self.image = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
        self.state = "search"
        self.mode = None
        self.line = 0
        self.last_vis = None
        self.image_count = 0
        self.image_version = 0      # incrementato a ogni nuova riga (per la GUI)
        self.start_wallclock = None
        self._reset_image()

    # ------------------------------------------------------------------ API
    def feed(self, audio, signal_present=True):
        """signal_present: dal ricevitore (SNR sopra una soglia bassa). Serve solo per gli avvii senza VIS."""
        self.signal_present = signal_present
        f = self.demod.process(audio)
        self.buf.append(f)
        self._scan_pulses()
        if self.state == "search":
            if not self._try_vis():
                self._try_train()
            if self.state == "search":
                self.buf.trim_before(self.buf.end - 3 * self.fs)
                self.pulses = [p for p in self.pulses if p >= self.buf.end - 3 * self.fs]
        if self.state == "decoding":
            self._decode_ready()

    def flush(self):
        """Chiude un'eventuale immagine in corso (fine file / stop ricevitore)."""
        if self.state == "decoding":
            self._finalize()

    @property
    def status(self):
        if self.state == "search":
            return tr("In attesa di segnale SSTV")
        return tr("Decodifica Robot36 ({m}) - riga {n}/{h}", m='VIS' if self.mode == 'vis' else 'sync', n=self.line, h=HEIGHT)

    # ------------------------------------------------------- impulsi di sync
    def _scan_pulses(self):
        fs = self.fs
        a = max(self.scan_pos - int(0.030 * fs), self.buf.base)
        b = self.buf.end - int(0.010 * fs)
        if b - a < int(0.020 * fs):
            return
        seg = self.buf.get(a, b)
        sm = uniform_filter1d(seg, int(0.002 * fs), mode="nearest")
        low = (sm < 1350.0).astype(np.int8)
        d = np.diff(np.concatenate(([0], low, [0])))
        starts = np.flatnonzero(d == 1)
        ends = np.flatnonzero(d == -1)
        lo, hi = 0.005 * fs, 0.014 * fs
        last = self.pulses[-1] if self.pulses else -1e18
        m = int(0.001 * fs)
        for s, e in zip(starts, ends):
            if s == 0 or e >= len(seg):
                continue
            if lo <= e - s <= hi:
                # un vero sync è un tono stabile a 1200 Hz; i click del rumore FM scendono di kHz
                # (mediana e frazione di campioni: un click isolato dentro un sync vero non lo invalida)
                core = seg[s + m:e - m]
                if len(core) < m or abs(float(np.median(core)) - 1200.0) > PULSE_MEDIAN_TOL \
                        or np.mean(np.abs(core - 1200.0) < 250.0) < PULSE_MIN_FRACTION:
                    continue
                # il fronte di salita sync(1200)->porch(1500) ha forma costante: lo usiamo come riferimento
                # (il fronte di discesa dipende dal colore dell'ultimo pixel della riga precedente)
                p = a + e - 0.5 - SYNC * fs
                if p > last + 0.020 * fs:
                    self.pulses.append(p)
                    last = p
        self.scan_pos = b

    # ---------------------------------------------------------------- avvio
    def _try_vis(self):
        fs = self.fs
        spm = fs // 1000  # campioni per ms
        a = max(self.buf.base, self.buf.end - int(1.3 * fs), self.vis_skip_until)
        a0 = -(-a // spm) * spm
        nms = (self.buf.end - a0) // spm
        if nms < 620:
            return False
        tr = self.buf.get(a0, a0 + nms * spm).reshape(nms, spm).mean(axis=1)
        res = find_vis(tr)
        if res is None:
            return False
        i, code, parity_ok = res
        g = a0 + i * spm
        # affina il fronte 1900 -> 1200 Hz dello start bit
        w0, w1 = g - 10 * spm, g + 10 * spm
        seg = self.buf.get(w0, w1)
        edge = g
        if len(seg) > 10:
            sm = uniform_filter1d(seg, spm // 2, mode="nearest")
            cross = np.flatnonzero((sm[:-1] >= 1550.0) & (sm[1:] < 1550.0))
            if len(cross):
                edge = max(w0, self.buf.base) + cross[np.argmin(np.abs(cross + max(w0, self.buf.base) - g))] + 1
        self.vis_skip_until = int(edge + 0.300 * fs)
        supported = parity_ok and code == VIS_ROBOT36
        self.last_vis = code
        self.on_event("vis", {"code": code, "supported": supported, "parity_ok": parity_ok})
        if supported:
            self._start(edge + 0.300 * fs, "vis")
            return True
        return False

    def _separator_class(self, q):
        """Livello del separatore della riga con sync in q: 0 = 1500 Hz (R-Y), 1 = 2300 Hz (B-Y), None = né l'uno né l'altro."""
        fs = self.fs
        a = q + (SYNC + SYNC_PORCH + Y_SCAN + 0.0005) * fs
        seg = self.buf.get(a, a + (SEPARATOR - 0.001) * fs)
        if len(seg) < 10:
            return None
        f = float(np.median(seg))
        if abs(f - 1500.0) < 150.0:
            return 0
        if abs(f - 2300.0) < 150.0:
            return 1
        return None

    def _try_train(self):
        """Avvio senza VIS: serve un treno regolare di sync con separatori validi e alternati."""
        if not getattr(self, "signal_present", True) or len(self.pulses) < TRAIN_MIN_PULSES:
            return False
        T = self.T_nom
        p = self.pulses[-1]
        chain = []
        for q in self.pulses:
            if p - 2.0 * self.fs <= q <= p:
                k = (p - q) / T
                if abs(k - round(k)) * T < 0.001 * self.fs:
                    chain.append(q)
        if len(chain) < TRAIN_MIN_PULSES or (p - chain[0]) < (TRAIN_MIN_PULSES - 1) * T * 0.99:
            return False
        cls = [(round((q - chain[0]) / T), self._separator_class(q)) for q in chain]
        valid = [c for c in cls if c[1] is not None]
        if len(valid) < 0.7 * len(cls):
            return False
        pairs = [(a, b) for a, b in zip(valid, valid[1:]) if b[0] - a[0] == 1]
        if pairs and sum(a[1] != b[1] for a, b in pairs) < 0.7 * len(pairs):
            return False
        self._start(chain[0], "sync")
        return True

    def _start(self, t0, mode):
        self.state = "decoding"
        self.mode = mode
        self.t0 = float(t0)
        self.fit = (self.t0, self.T_nom)
        self.row_off = 0 if mode == "vis" else None
        self.line = 0
        self.last_sync_line = 0
        # istante (unix) del primo sync: ora corrispondente alla fine del buffer meno il tempo già bufferizzato
        self.start_wallclock = self.clock() - (self.buf.end - self.t0) / self.fs
        self.pulses = [q for q in self.pulses if q >= self.t0 - 0.01 * self.fs]
        self._reset_image()
        self.on_event("start", {"mode": mode})

    def _reset_image(self):
        self.Y = np.zeros((HEIGHT, WIDTH))
        self.C = np.full((HEIGHT, WIDTH), 128.0)
        self.have = np.zeros(HEIGHT, bool)
        self.image[:] = 0
        self.image_version += 1

    # -------------------------------------------------------------- decodifica
    def _fit_lines(self):
        """Regressione lineare posizione_sync = a + n*b (correzione slant)."""
        fs = self.fs
        a, b = self.fit
        p = np.array([q for q in self.pulses if q >= self.t0 - 0.01 * fs])
        if len(p) == 0:
            return a, b, np.zeros(0, int)
        for _ in range(3):
            n = np.round((p - a) / b)
            r = p - (a + n * b)
            keep = (np.abs(r) < 0.003 * fs) & (n >= 0) & (n < HEIGHT)
            if keep.sum() >= 6 and np.ptp(n[keep]) >= 10:
                bb, aa = np.polyfit(n[keep], p[keep], 1)
                if abs(bb / self.T_nom - 1.0) < MAX_SLANT:
                    a, b = aa, bb
                    continue
            if keep.any():
                a = a + float(np.median(r[keep]))
        n = np.round((p - a) / b)
        r = p - (a + n * b)
        matched = n[(np.abs(r) < 0.003 * fs) & (n >= 0)].astype(int)
        return a, b, matched

    def _decode_ready(self):
        fs = self.fs
        while self.state == "decoding":
            a, b, matched = self._fit_lines()
            self.fit = (a, b)
            if len(matched):
                self.last_sync_line = max(self.last_sync_line, int(matched.max()))
            n = self.line
            row_limit = HEIGHT - (self.row_off or 0)
            if n >= row_limit:
                self._finalize()
                return
            ls = a + n * b
            if ls + b + 0.005 * fs > self.buf.end:
                return
            self._decode_line(n, ls, b, live=True)
            self.line += 1
            self.matched = matched
            if self.line - self.last_sync_line > SYNC_LOSS_LINES:
                self._finalize()
                return
            # un avvio senza VIS che dopo 20 righe ha pochi sync è rumore: si abbandona subito
            if self.mode == "sync" and self.line >= 20 and self._quality(matched, self.line) < MIN_SYNC_QUALITY["sync"]:
                self._abort()
                return

    @staticmethod
    def _quality(matched, lines):
        if lines <= 0:
            return 0.0
        return len(set(int(n) for n in matched if 0 <= n < lines)) / lines

    def _abort(self):
        self.on_event("discard", {"lines": self.line})
        self._reset_image()
        self._back_to_search()

    def _back_to_search(self):
        self.state = "search"
        self.mode = None
        self.vis_skip_until = max(self.vis_skip_until, self.buf.end)
        self.pulses = []
        self.buf.trim_before(self.buf.end - int(0.5 * self.fs))

    def _decode_line(self, n, ls, b, live):
        fs = self.fs
        s = b / self.T_nom
        o = int(np.floor(ls)) - 2
        seg = self.buf.get(o, o + int(b) + 8)
        if len(seg) < int(b):
            return
        rel = ls - o

        def at(t):
            return rel + t * s * fs

        t_y0 = SYNC + SYNC_PORCH
        t_y1 = t_y0 + Y_SCAN
        t_c0 = t_y1 + SEPARATOR + PORCH
        y = freq_to_level(_box_means(seg, at(t_y0), at(t_y1), WIDTH))
        sep = float(np.mean(_box_means(seg, at(t_y1 + 0.0005), at(t_y1 + SEPARATOR - 0.0005), 1)))
        c = freq_to_level(_box_means(seg, at(t_c0), at(LINE), WIDTH))
        if self.row_off is None:
            # avvio senza VIS: la parità della riga si ricava dal separatore
            self.row_off = 1 if sep > 1900.0 else 0
        row = n + self.row_off
        if row >= HEIGHT:
            return
        self.Y[row] = y
        self.C[row] = c
        self.have[row] = True
        self._compose(row // 2)
        if live:
            self.image_version += 1

    def _compose(self, k):
        r0, r1 = 2 * k, 2 * k + 1
        cr = self.C[r0] if self.have[r0] else np.full(WIDTH, 128.0)
        cb = self.C[r1] if r1 < HEIGHT and self.have[r1] else np.full(WIDTH, 128.0)
        for r in (r0, r1):
            if r < HEIGHT and self.have[r]:
                self.image[r] = ycbcr_to_rgb(self.Y[r], cb, cr)

    def _finalize(self):
        a, b, matched = self._fit_lines()
        last_line = self.line
        partial = self.line < HEIGHT - (self.row_off or 0)
        if partial:
            last_line = min(self.line, self.last_sync_line + 1)
        # passata finale con la stima definitiva del periodo di riga
        self.have[:] = False
        for n in range(last_line):
            self._decode_line(n, a + n * b, b, live=False)
        for k in range(HEIGHT // 2):
            self._compose(k)
        self.image[~self.have] = 0
        self.image_version += 1
        lines = int(self.have.sum())
        quality = self._quality(matched, last_line)
        if lines >= MIN_LINES_TO_SAVE and quality >= MIN_SYNC_QUALITY[self.mode]:
            path = self._save()
            end_time = self.start_wallclock + last_line * b / self.fs
            self.on_event("image", {"path": path, "partial": partial or lines < HEIGHT, "lines": lines,
                                    "slant_ppm": (b / self.T_nom - 1.0) * 1e6, "sync_quality": quality,
                                    "start_time": self.start_wallclock, "end_time": end_time,
                                    "mode": self.mode})
        else:
            self.on_event("discard", {"lines": lines, "sync_quality": quality})
        self._back_to_search()

    def _save(self):
        """Salva il PNG come AAAAMMGG_HHMMSSZ.png (UTC di inizio immagine); i dettagli vanno nella scheda .txt."""
        self.image_count += 1
        path = None
        if self.out_dir:
            from PIL import Image
            os.makedirs(self.out_dir, exist_ok=True)
            name = time.strftime("%Y%m%d_%H%M%SZ.png", time.gmtime(self.start_wallclock or time.time()))
            path = os.path.join(self.out_dir, name)
            k = 1
            while os.path.exists(path):
                k += 1
                path = os.path.join(self.out_dir, name.replace(".png", f"_{k}.png"))
            Image.fromarray(self.image.copy()).save(path)
        return path


def load_audio(path):
    """Legge un WAV (qualsiasi frequenza, mono/stereo, int/float) e lo porta a 48 kHz mono float."""
    from math import gcd
    from scipy.io import wavfile
    from scipy.signal import resample_poly
    rate, x = wavfile.read(path)
    if x.dtype.kind == "i":
        x = x.astype(np.float32) / float(np.iinfo(x.dtype).max)
    elif x.dtype.kind == "u":
        x = (x.astype(np.float32) - 128.0) / 128.0
    x = np.asarray(x, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if rate != FS:
        g = gcd(int(rate), FS)
        x = resample_poly(x, FS // g, int(rate) // g).astype(np.float32)
    return x


def wav_start_time(path, n_samples):
    """Istante di inizio di una registrazione: dal nome rec_AAAAMMGG_HHMMSSZ.wav se presente,
    altrimenti data di modifica del file meno la durata."""
    import calendar
    import re
    m = re.search(r"(\d{8})_(\d{6})Z", os.path.basename(path))
    if m:
        return calendar.timegm(time.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")), "nome del file"
    return os.path.getmtime(path) - n_samples / FS, "data del file (stima)"


def decode_audio_file(path, out_dir, on_event=None, chunk=4096):
    """Decodifica un file WAV audio (per es. registrato con SDR#/SDR++ o da questa utility)."""
    x = load_audio(path)
    t0, _ = wav_start_time(path, len(x))
    dec = None
    dec = Robot36Decoder(out_dir=out_dir, on_event=on_event, clock=lambda: t0 + dec.buf.end / FS)
    for i in range(0, len(x), chunk):
        dec.feed(x[i:i + chunk])
    dec.feed(np.zeros(FS // 2, np.float32))
    dec.flush()
    return dec
