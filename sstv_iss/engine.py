"""Motore di ricezione: SDR -> Receiver (Doppler + AFC) -> decoder Robot36. Thread-safe verso la GUI."""
import collections
import os
import queue
import threading
import time
import wave

import numpy as np

from .audio_out import AudioMonitor
from .receiver import BLOCK, FS_AUDIO, FS_IN, Receiver
from .report import write_report
from .sdr_source import DongleUnavailable, RtlSource
from .sstv.robot36 import Robot36Decoder

AFC_GAIN = 0.05             # per blocco da 64 ms -> costante di tempo ~1.3 s
DOPPLER_REFRESH_S = 0.5
# soglia SNR (più bassa dello squelch AFC) sotto la quale il decoder non parte senza VIS:
# a vuoto l'SNR misurato sta fra -8 e -3 dB
SIGNAL_GATE_DB = 0.5
RETRY_S = 3.0               # intervallo fra i tentativi di apertura del dongle
DATA_TIMEOUT_S = 3.0        # senza dati per questo tempo il dongle è considerato perso


class Engine:
    def __init__(self, cfg, tracker):
        self.cfg = cfg
        self.tracker = tracker
        self.events = queue.Queue()          # (tipo, dati) verso la GUI
        self.spec_rows = collections.deque(maxlen=64)
        self.lock = threading.Lock()
        self.running = False
        self.src = None
        self.iq_q = None
        self.dsp_thread = None
        self.decoder = Robot36Decoder(out_dir=cfg.images_dir, on_event=self._dec_event)
        self.monitor = AudioMonitor()
        self.afc_hz = 0.0
        self.doppler_hz = 0.0
        self.doppler_rate = 0.0
        self._dop_t = 0.0
        self.snr_db = -20.0
        self.snr_hist = collections.deque(maxlen=2000)     # (istante, SNR dB): ~2 minuti a 15,6 blocchi/s
        self.squelch_open = False
        self.wav = None
        self.wav_path = None
        self.spec_freqs = None

    # ---------------------------------------------------------- controllo
    # `running` = l'utente (o l'avvio automatico) vuole ricevere.
    # `connected` = il dongle è aperto e manda dati. Se running e non connected, siamo in attesa del dongle:
    # il thread supervisore riprova ogni RETRY_S secondi e riprende la ricezione appena il dongle c'è.

    @property
    def connected(self):
        return self.src is not None

    @property
    def waiting(self):
        return self.running and self.src is None

    def start(self):
        """Avvia la ricezione. Non fallisce se il dongle manca: entra in attesa.

        Raises:
            RuntimeError: solo se la libreria RTL-SDR non è utilizzabile.
        """
        if self.running:
            return
        try:
            import rtlsdr  # noqa: F401  (errore definitivo: inutile aspettare)
        except Exception as e:
            raise RuntimeError(f"Libreria RTL-SDR non disponibile: {e}") from e
        self.iq_q = queue.Queue(maxsize=40)
        self.rx = Receiver(FS_IN, deemph_us=self.cfg.deemph_us)
        self.spec_freqs = self.rx.spec_freqs
        self.running = True
        self._wake = threading.Event()
        self._dop_t = 0.0
        self.dsp_thread = threading.Thread(target=self._dsp_loop, name="dsp", daemon=True)
        self.dsp_thread.start()
        if self.cfg.record_wav:
            self.start_wav()
        self.sup_thread = threading.Thread(target=self._supervise, name="dongle-supervisor", daemon=True)
        self.sup_thread.start()

    def stop(self):
        if not self.running:
            return
        self.running = False
        self._wake.set()
        self.sup_thread.join(timeout=5)
        src, self.src = self.src, None
        if src:
            src.stop()
        if self.dsp_thread:
            self.dsp_thread.join(timeout=3)
        with self.lock:
            self.decoder.flush()
        self.stop_wav()
        self.events.put(("log", "Ricevitore fermato"))

    def _connect(self):
        src = RtlSource(self.iq_q, self.hw_center(), self.cfg.gain_db, self.cfg.ppm, self.cfg.bias_tee)
        self._drain_queue()
        src.start()
        self.src = src

    def _drain_queue(self):
        while True:
            try:
                self.iq_q.get_nowait()
            except queue.Empty:
                return

    def _supervise(self):
        announced_wait = False
        while self.running:
            if self.src is None:
                try:
                    self._connect()
                    announced_wait = False
                    self.events.put(("log", f"Dongle collegato: ricezione su {self.cfg.freq_hz / 1e6:.4f} MHz"))
                except DongleUnavailable as e:
                    if not announced_wait:
                        self.events.put(("log", "In attesa del dongle RTL-SDR (collegalo o chiudi SDR#/SDR++): "
                                                f"riprovo ogni {RETRY_S:.0f} s. [{e}]"))
                        announced_wait = True
                except Exception as e:
                    self.events.put(("error", f"Errore dongle: {e}"))
                    return
            elif self.src.lost(DATA_TIMEOUT_S):
                src, self.src = self.src, None
                reason = src.error or ("nessun dato dal dongle" if not src.ended else "lettura interrotta")
                self.events.put(("log", f"Dongle scollegato ({reason}): chiudo l'immagine in corso e attendo"))
                threading.Thread(target=src.stop, daemon=True).start()  # può bloccarsi nel driver
                with self.lock:
                    self.decoder.flush()
                self.snr_db = -20.0
                self.squelch_open = False
                announced_wait = True
                self.events.put(("log", f"In attesa del dongle RTL-SDR: riprovo ogni {RETRY_S:.0f} s"))
            self._wake.wait(RETRY_S if self.src is None else 0.5)

    def hw_center(self):
        return self.cfg.freq_hz - self.cfg.if_offset_hz

    def _src_call(self, fn):
        src = self.src
        if src is None:
            return
        try:
            fn(src)
        except Exception as e:  # dongle appena scollegato: se ne accorgerà il supervisore
            self.events.put(("log", f"Comando al dongle non riuscito: {e}"))

    def retune(self):
        self._src_call(lambda s: s.set_center(self.hw_center()))

    def set_gain(self, g):
        self._src_call(lambda s: s.set_gain(g))

    def set_ppm(self, ppm):
        self._src_call(lambda s: s.set_ppm(ppm))

    def reset_afc(self):
        self.afc_hz = 0.0

    # --------------------------------------------------------------- WAV
    def start_wav(self):
        if self.wav:
            return
        os.makedirs(self.cfg.images_dir, exist_ok=True)
        self.wav_path = os.path.join(self.cfg.images_dir, time.strftime("rec_%Y%m%d_%H%M%SZ.wav", time.gmtime()))
        w = wave.open(self.wav_path, "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS_AUDIO)
        self.wav = w
        self.events.put(("log", f"Registrazione audio: {self.wav_path}"))

    def stop_wav(self):
        w, self.wav = self.wav, None
        if w:
            w.close()

    # ---------------------------------------------------------------- DSP
    def _doppler_now(self):
        """Doppler attuale: ricalcolato dal TLE ogni 0,5 s, estrapolato linearmente solo in mezzo."""
        now = time.time()
        if now - self._dop_t > DOPPLER_REFRESH_S:
            self.doppler_hz, self.doppler_rate = self.tracker.doppler(self.cfg.freq_hz, now)
            self._dop_t = now
            return self.doppler_hz
        return self.doppler_hz + self.doppler_rate * min(now - self._dop_t, 1.0)

    def current_shift(self):
        dop = self._doppler_now() if self.cfg.doppler else 0.0
        afc = self.afc_hz if self.cfg.afc else 0.0
        return self.cfg.if_offset_hz + dop + afc + self.cfg.manual_offset_hz, dop

    def _dsp_loop(self):
        while self.running:
            try:
                iq = self.iq_q.get(timeout=0.5)
            except queue.Empty:
                continue        # dongle assente o perso: lo gestisce il supervisore
            if len(iq) != BLOCK:
                continue
            shift, dop = self.current_shift()
            r = self.rx.process(iq, shift)
            self.snr_db = r["snr_db"]
            self.snr_hist.append((time.time(), self.snr_db))
            self.squelch_open = self.snr_db >= self.cfg.squelch_db
            if self.cfg.afc and self.squelch_open:
                lim = self.cfg.afc_limit_hz
                self.afc_hz = float(np.clip(self.afc_hz + AFC_GAIN * r["freq_err"], -lim, lim))
            if r["spectrum_db"] is not None:
                self.spec_rows.append(r["spectrum_db"])
            with self.lock:
                self.decoder.feed(r["audio"], signal_present=self.snr_db >= SIGNAL_GATE_DB)
            self.monitor.push(r["audio"], signal_present=self.squelch_open)
            if self.wav:
                pcm = np.clip(r["audio"] * 16000, -32767, 32767).astype("<i2")
                try:
                    self.wav.writeframes(pcm.tobytes())
                except Exception:
                    pass

    def _dec_event(self, kind, info):
        if kind == "image" and info.get("path"):
            # la scheda .txt richiede calcoli orbitali: la scriviamo fuori dal thread DSP
            stats = self.snr_stats(info.get("start_time"), info.get("end_time"))
            threading.Thread(target=self._write_report, args=(info, stats), daemon=True).start()
        self.events.put((kind, info))

    def snr_stats(self, t0, t1):
        """(mediana, massimo) dell'SNR in dB durante l'immagine, oppure None."""
        if not t0 or not t1:
            return None
        vals = [s for t, s in list(self.snr_hist) if t0 <= t <= t1 + 0.5]
        if not vals:
            return None
        return float(np.median(vals)), float(np.max(vals))

    def _write_report(self, info, stats):
        try:
            txt = write_report(info["path"], info, self.cfg, self.tracker, stats)
            self.events.put(("log", f"Scheda ARISS: {os.path.basename(txt)}"))
        except Exception as e:
            self.events.put(("log", f"Scheda .txt non scritta: {e}"))

    # ---------------------------------------------------------- per la GUI
    def snapshot(self):
        # con il dongle che manda dati il Doppler lo aggiorna il thread DSP; altrimenti lo ricalcoliamo qui
        src = self.src
        dop = self._doppler_now() if src is None else \
            self.doppler_hz + self.doppler_rate * min(time.time() - self._dop_t, 1.0)
        with self.lock:
            img = self.decoder.image.copy()
            ver = self.decoder.image_version
            status = self.decoder.status
        return {
            "running": self.running,
            "waiting": self.running and src is None,
            "doppler": dop if self.cfg.doppler else 0.0,
            "afc": self.afc_hz if self.cfg.afc else 0.0,
            "snr": self.snr_db,
            "squelch": self.squelch_open,
            "image": img,
            "image_version": ver,
            "status": status,
            "overflows": src.overflows if src else 0,
        }

    def pop_spectrum(self):
        rows = []
        while self.spec_rows:
            try:
                rows.append(self.spec_rows.popleft())
            except IndexError:
                break
        return rows
