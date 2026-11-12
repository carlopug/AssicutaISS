"""Catena DSP: IQ 960 kS/s -> NCO (offset IF + Doppler + AFC) -> decimazione -> FM -> audio 48 kHz."""
import numpy as np
from scipy.signal import butter, firwin, lfilter, sosfilt, sosfilt_zi, upfirdn

FS_IN = 960_000
FS_MID = 192_000
FS_AUDIO = 48_000
BLOCK = 61_440          # 64 ms a 960 kS/s (multiplo di 20 e di 256)
FFT_N = 2048
SPAN_HZ = 25_000        # metà della larghezza mostrata nel waterfall


class Decimator:
    """Decimatore FIR polifase con stato tra un blocco e l'altro."""

    def __init__(self, taps, down):
        self.h = np.asarray(taps, dtype=np.float64)
        self.down = down
        m = len(self.h) - 1
        self.m = -(-m // down) * down
        self.hist = np.zeros(self.m, dtype=np.complex128)

    def process(self, x):
        ext = np.concatenate((self.hist, x))
        y = upfirdn(self.h, ext, down=self.down)
        k0 = self.m // self.down
        out = y[k0:k0 + len(x) // self.down]
        self.hist = ext[-self.m:]
        return out


class Receiver:
    def __init__(self, fs_in=FS_IN, deemph_us=750.0, channel_hz=9_000):
        assert fs_in == FS_IN, "la catena è progettata per 960 kS/s"
        self.fs_in = fs_in
        self.phase = 0.0
        self.dec1 = Decimator(firwin(41, 70_000, fs=FS_IN), 5)
        self.dec2 = Decimator(firwin(63, 15_000, fs=FS_MID), 4)
        self.chan_h = firwin(65, channel_hz, fs=FS_AUDIO)
        self.chan_zi = np.zeros(len(self.chan_h) - 1, np.complex128)
        self.prev = 1.0 + 0j
        self.set_deemphasis(deemph_us)
        self.bp = butter(4, [300, 3000], btype="band", fs=FS_AUDIO, output="sos")
        self.bp_zi = sosfilt_zi(self.bp) * 0.0
        self.win = np.hanning(FFT_N)
        freqs = np.fft.fftshift(np.fft.fftfreq(FFT_N, 1 / FS_MID))
        self.spec_sel = np.flatnonzero(np.abs(freqs) <= SPAN_HZ)
        self.spec_freqs = freqs[self.spec_sel]
        self.sig_mask = np.abs(freqs) <= 7_500
        self.noise_mask = (np.abs(freqs) >= 30_000) & (np.abs(freqs) <= 60_000)

    def set_deemphasis(self, us):
        if us and us > 0:
            alpha = 1.0 - np.exp(-1.0 / (FS_AUDIO * us * 1e-6))
            self.de_b, self.de_a = [alpha], [1.0, alpha - 1.0]
        else:
            self.de_b, self.de_a = [1.0], [1.0]
        self.de_zi = np.zeros(1)

    def process(self, iq, shift_hz):
        """Elabora un blocco IQ. shift_hz = frequenza (in banda base) del segnale da portare a 0 Hz.

        Restituisce dict con: audio (float32, 48 kHz), freq_err (Hz, media discriminatore),
        snr_db, spectrum_db (array per waterfall).
        """
        n = len(iq)
        w = 2 * np.pi * shift_hz / self.fs_in
        ph = self.phase + w * np.arange(n)
        self.phase = (self.phase + w * n) % (2 * np.pi)
        x = np.asarray(iq, dtype=np.complex128) * np.exp(-1j * ph)

        mid = self.dec1.process(x)                      # 192 kS/s
        spec, snr = self._spectrum(mid)
        bb = self.dec2.process(mid)                     # 48 kS/s
        bb, self.chan_zi = lfilter(self.chan_h, 1.0, bb, zi=self.chan_zi)

        prev = np.empty_like(bb)
        prev[0] = self.prev
        prev[1:] = bb[:-1]
        self.prev = bb[-1]
        disc = np.angle(bb * np.conj(prev)) * (FS_AUDIO / (2 * np.pi))   # Hz
        freq_err = float(np.mean(disc))
        sstv_ratio = self._sstv_ratio(disc - freq_err)

        a, self.de_zi = lfilter(self.de_b, self.de_a, disc, zi=self.de_zi)
        a, self.bp_zi = sosfilt(self.bp, a, zi=self.bp_zi)
        audio = (a / 5000.0).astype(np.float32)
        return {"audio": audio, "freq_err": freq_err, "snr_db": snr, "spectrum_db": spec, "sstv_ratio": sstv_ratio}

    def _sstv_ratio(self, d):
        """Quota dell'energia audio (300-3000 Hz) che cade nella banda dei toni SSTV (1050-2400 Hz).

        Calcolata sull'uscita del discriminatore prima della de-enfasi: alta per un segnale SSTV,
        bassa per voce, portanti non modulate e rumore.
        """
        P = np.abs(np.fft.rfft(d * self._win_audio(len(d)))) ** 2
        f = np.fft.rfftfreq(len(d), 1 / FS_AUDIO)
        tot = P[(f >= 300) & (f <= 3000)].sum() + 1e-12
        return float(P[(f >= 1050) & (f <= 2400)].sum() / tot)

    def _win_audio(self, n):
        if getattr(self, "_wa", None) is None or len(self._wa) != n:
            self._wa = np.hanning(n)
        return self._wa

    def _spectrum(self, mid):
        k = len(mid) // FFT_N
        if k == 0:
            return None, -99.0
        frames = mid[:k * FFT_N].reshape(k, FFT_N) * self.win
        p = np.mean(np.abs(np.fft.fftshift(np.fft.fft(frames, axis=1), axes=1)) ** 2, axis=0) + 1e-20
        noise = float(np.median(p[self.noise_mask]))
        sig = float(np.sum(p[self.sig_mask]))
        nsig = noise * int(self.sig_mask.sum())
        snr = 10 * np.log10(max(sig - nsig, 1e-20) / nsig)
        return (10 * np.log10(p[self.spec_sel])).astype(np.float32), max(snr, -20.0)
