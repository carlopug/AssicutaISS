"""Ascolto opzionale dell'audio demodulato su un'uscita audio a scelta (PortAudio via sounddevice)."""
import threading

import numpy as np

from .i18n import tr

try:
    import sounddevice as sd
    IMPORT_ERROR = None
except Exception as e:  # pacchetto mancante o PortAudio non caricabile
    sd = None
    IMPORT_ERROR = str(e)

FS = 48_000
MAX_BUFFER_S = 0.4          # oltre questa coda si scarta l'audio più vecchio (latenza bassa)
PREFERRED_HOSTAPIS = ("Windows DirectSound", "MME")


def available():
    return sd is not None


def list_outputs():
    """Nomi delle uscite audio di un solo host API (evita i doppioni MME/DirectSound/WASAPI)."""
    if sd is None:
        return []
    try:
        apis = sd.query_hostapis()
        devs = sd.query_devices()
    except Exception:
        return []
    for api_name in PREFERRED_HOSTAPIS:
        idx = next((i for i, a in enumerate(apis) if a["name"] == api_name), None)
        if idx is None:
            continue
        names = [d["name"] for d in devs if d["hostapi"] == idx and d["max_output_channels"] > 0]
        if names:
            return names
    return [d["name"] for d in devs if d["max_output_channels"] > 0]


def _device_index(name):
    apis = sd.query_hostapis()
    devs = sd.query_devices()
    for api_name in PREFERRED_HOSTAPIS:
        for i, d in enumerate(devs):
            if d["name"] == name and d["max_output_channels"] > 0 and apis[d["hostapi"]]["name"] == api_name:
                return i
    return None


class AudioMonitor:
    def __init__(self):
        self.stream = None
        self.volume = 0.3
        self.mute_without_signal = False
        self._buf = np.zeros(0, np.float32)
        self._lock = threading.Lock()
        self.device_name = None

    @property
    def active(self):
        return self.stream is not None

    def start(self, device_name=None):
        """Apre l'uscita. device_name None = uscita predefinita di Windows."""
        if sd is None:
            raise RuntimeError(tr("Ascolto non disponibile: {e}", e=IMPORT_ERROR))
        self.stop()
        dev = _device_index(device_name) if device_name else None
        with self._lock:
            self._buf = np.zeros(0, np.float32)
        self.stream = sd.OutputStream(samplerate=FS, channels=1, dtype="float32", device=dev,
                                      blocksize=1024, latency="high", callback=self._callback)
        self.stream.start()
        self.device_name = device_name

    def stop(self):
        s, self.stream = self.stream, None
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass

    def push(self, audio, signal_present=True):
        """Chiamata dal thread DSP: non blocca mai (al massimo scarta l'audio più vecchio)."""
        if self.stream is None:
            return
        if self.mute_without_signal and not signal_present:
            audio = np.zeros(len(audio), np.float32)
        else:
            audio = np.clip(np.asarray(audio, np.float32) * self.volume, -1.0, 1.0)
        with self._lock:
            buf = np.concatenate((self._buf, audio))
            limit = int(MAX_BUFFER_S * FS)
            self._buf = buf[-limit:] if len(buf) > limit else buf

    def _callback(self, outdata, frames, _time, _status):
        try:
            with self._lock:
                n = min(frames, len(self._buf))
                outdata[:n, 0] = self._buf[:n]
                self._buf = self._buf[n:]
            outdata[n:, 0] = 0.0
        except Exception:
            outdata.fill(0)
