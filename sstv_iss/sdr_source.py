"""Sorgenti IQ: dongle RTL-SDR (lettura asincrona in un thread dedicato)."""
import queue
import threading
import time

from .i18n import tr
from .receiver import BLOCK, FS_IN

R820T_GAINS = [0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6, 19.7, 20.7, 22.9, 25.4,
               28.0, 29.7, 32.8, 33.8, 36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6]


class DongleUnavailable(Exception):
    """Dongle assente o occupato da un altro programma: si può riprovare più tardi."""


class RtlSource:
    """Apre il dongle e mette blocchi complessi da BLOCK campioni nella coda `out`.

    Raises:
        RuntimeError: libreria RTL-SDR non caricabile (errore definitivo).
        DongleUnavailable: dongle non collegato o già in uso (si può riprovare).
    """

    def __init__(self, out_queue: queue.Queue, center_hz, gain_db=-1.0, ppm=0, bias_tee=False, device_index=0):
        try:
            from rtlsdr import RtlSdr
        except Exception as e:  # DLL mancante o pacchetto non installato
            raise RuntimeError(tr("Libreria RTL-SDR non disponibile: {e}", e=e)) from e
        self.out = out_queue
        self.overflows = 0
        self.error = None
        self.ended = False              # la lettura è terminata senza che l'abbiamo fermata
        self.last_data = time.time()
        self._stopping = False
        try:
            self.sdr = RtlSdr(device_index)
        except Exception as e:
            raise DongleUnavailable(str(e)) from e
        try:
            self.sdr.sample_rate = FS_IN
            if ppm:
                self.sdr.freq_correction = int(ppm)
            self.sdr.center_freq = int(center_hz)
            self.set_gain(gain_db)
            if bias_tee:
                try:
                    self.sdr.set_bias_tee(True)
                except Exception:
                    pass
        except Exception as e:  # dongle scollegato durante la configurazione
            self._close()
            raise DongleUnavailable(str(e)) from e
        self.thread = threading.Thread(target=self._run, name="rtl-reader", daemon=True)

    def start(self):
        self.last_data = time.time()
        self.thread.start()

    def _cb(self, samples, _ctx):
        self.last_data = time.time()
        try:
            self.out.put_nowait(samples)
        except queue.Full:
            self.overflows += 1

    def _run(self):
        try:
            self.sdr.read_samples_async(self._cb, BLOCK)
        except Exception as e:
            self.error = str(e)
        if not self._stopping:
            self.ended = True

    def lost(self, timeout_s=3.0):
        """True se il dongle non risponde più (errore, lettura terminata o nessun dato da `timeout_s`)."""
        return self.error is not None or self.ended or time.time() - self.last_data > timeout_s

    def set_gain(self, gain_db):
        self.sdr.gain = "auto" if gain_db is None or gain_db < 0 else float(gain_db)

    def set_center(self, hz):
        self.sdr.center_freq = int(hz)

    def set_ppm(self, ppm):
        try:
            self.sdr.freq_correction = int(ppm)
        except Exception:
            pass  # librtlsdr restituisce errore se il valore non cambia

    def stop(self):
        self._stopping = True
        try:
            self.sdr.cancel_read_async()
        except Exception:
            pass
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            # il thread di lettura è bloccato nel driver (dongle strappato via):
            # chiudere ora il dispositivo potrebbe bloccare il programma, lo abbandoniamo
            return
        try:
            self.sdr.set_bias_tee(False)
        except Exception:
            pass
        self._close()

    def _close(self):
        try:
            self.sdr.close()
        except Exception:
            pass
