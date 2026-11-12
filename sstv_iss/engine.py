"""Motore di ricezione: SDR -> Receiver (Doppler + AFC) -> decoder Robot36. Thread-safe verso la GUI."""
import collections
import os
import queue
import threading
import time
import wave

import numpy as np

from .audio_out import AudioMonitor
from .i18n import tr
from .receiver import BLOCK, FS_AUDIO, FS_IN, Receiver
from .report import write_report
from .telemetry import TelemetryCsv
from .sdr_source import DongleUnavailable, RtlSource
from .sstv.robot36 import Robot36Decoder

AFC_GAIN = 0.05             # per blocco da 64 ms -> costante di tempo ~1.3 s
AFC_LEAK = 0.9968           # senza segnale SSTV l'AFC torna verso 0 (costante di tempo ~20 s)
SSTV_RATIO_MIN = 0.70       # quota di energia audio nella banda SSTV oltre la quale il segnale è SSTV
AFC_WARN_HZ = 1000.0        # sopra questo spostamento l'AFC lo segnala nel registro
DOPPLER_REFRESH_S = 0.5
# soglia SNR (più bassa dello squelch AFC) sotto la quale il decoder non parte senza VIS:
# a vuoto l'SNR misurato sta fra -8 e -3 dB
SIGNAL_GATE_DB = 0.5
RETRY_S = 3.0               # intervallo fra i tentativi di apertura del dongle
DATA_TIMEOUT_S = 3.0
STATUS_LOG_S = 30.0          # riga di stato nel registro durante la ricezione        # senza dati per questo tempo il dongle è considerato perso


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
        self.csv = None
        self._sec = None            # secondo in corso per la telemetria
        self._sec_snr = []
        self._sec_sig = False
        self._last_status = 0.0
        self._afc_warned = False
        self.sstv_ratio = 0.0
        self._sec_ratio = []
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
            raise RuntimeError(tr("Libreria RTL-SDR non disponibile: {e}", e=e)) from e
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
        self.events.put(("log", tr("Ricevitore fermato")))

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
                    self.events.put(("log", tr("Dongle collegato: ricezione su {f:.4f} MHz", f=self.cfg.freq_hz / 1e6)))
                except DongleUnavailable as e:
                    if not announced_wait:
                        self.events.put(("log", tr("In attesa del dongle RTL-SDR (collegalo o chiudi SDR#/SDR++): "
                                                   "riprovo ogni {s:.0f} s. [{e}]", s=RETRY_S, e=e)))
                        announced_wait = True
                except Exception as e:
                    self.events.put(("error", tr("Errore dongle: {e}", e=e)))
                    return
            elif self.src.lost(DATA_TIMEOUT_S):
                src, self.src = self.src, None
                reason = src.error or (tr("nessun dato dal dongle") if not src.ended else tr("lettura interrotta"))
                self.events.put(("log", tr("Dongle scollegato ({r}): chiudo l'immagine in corso e attendo", r=reason)))
                threading.Thread(target=src.stop, daemon=True).start()  # può bloccarsi nel driver
                with self.lock:
                    self.decoder.flush()
                self.snr_db = -20.0
                self.squelch_open = False
                announced_wait = True
                self.events.put(("log", tr("In attesa del dongle RTL-SDR: riprovo ogni {s:.0f} s", s=RETRY_S)))
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
            self.events.put(("log", tr("Comando al dongle non riuscito: {e}", e=e)))

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
        try:
            self.csv = TelemetryCsv(self.wav_path)
        except OSError:
            self.csv = None
        self.events.put(("log", tr("Registrazione audio: {p}", p=self.wav_path)))
        if self.csv:
            self.events.put(("log", tr("Telemetria al secondo: {p}", p=self.csv.path)))

    def stop_wav(self):
        w, self.wav = self.wav, None
        if w:
            w.close()
        c, self.csv = self.csv, None
        if c:
            c.close()

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
            self.update_afc(r["freq_err"], r["sstv_ratio"])
            self.sstv_ratio = r["sstv_ratio"]
            if r["spectrum_db"] is not None:
                self.spec_rows.append(r["spectrum_db"])
            with self.lock:
                self.decoder.feed(r["audio"], signal_present=self.snr_db >= SIGNAL_GATE_DB)
            self.monitor.push(r["audio"], signal_present=self.squelch_open)
            self._telemetry(dop)
            if self.wav:
                pcm = np.clip(r["audio"] * 16000, -32767, 32767).astype("<i2")
                try:
                    self.wav.writeframes(pcm.tobytes())
                except Exception:
                    pass

    def update_afc(self, freq_err, sstv_ratio):
        """Insegue l'errore di frequenza solo su segnali SSTV (o durante un'immagine), entro ±afc_range_hz.

        Senza segnale SSTV l'AFC torna lentamente verso 0: una portante o una voce su un canale vicino
        non possono più trascinare la sintonia e lasciarla spostata.
        """
        if not self.cfg.afc:
            return
        decoding = self.decoder.state == "decoding"
        if self.squelch_open and (sstv_ratio >= SSTV_RATIO_MIN or decoding):
            lim = self.cfg.afc_range_hz
            self.afc_hz = float(np.clip(self.afc_hz + AFC_GAIN * freq_err, -lim, lim))
        else:
            self.afc_hz *= AFC_LEAK
        if abs(self.afc_hz) > AFC_WARN_HZ and not self._afc_warned:
            self._afc_warned = True
            self.events.put(("log", tr("AFC spostato di {a:+.0f} Hz: verificare PPM o disturbi vicini alla frequenza",
                                       a=self.afc_hz)))
        elif abs(self.afc_hz) < AFC_WARN_HZ / 2:
            self._afc_warned = False

    def _telemetry(self, dop):
        """Aggrega l'SNR per secondo: riga nel CSV accanto al WAV e, ogni 30 s, una riga di stato nel registro."""
        now = time.time()
        sec = int(now)
        if self._sec is None:
            self._sec = sec
        if sec != self._sec and self._sec_snr:
            snr_mean = float(np.mean(self._sec_snr))
            snr_max = float(np.max(self._sec_snr))
            look = self.tracker.look(now) if getattr(self.tracker, "ready", False) else None
            afc = self.afc_hz if self.cfg.afc else 0.0
            if self.csv:
                src = self.src
                with self.lock:
                    dstate, dline = self.decoder.state, self.decoder.line
                try:
                    self.csv.row({
                        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._sec)),
                        "snr_db_mean": f"{snr_mean:.1f}", "snr_db_max": f"{snr_max:.1f}",
                        "signal": int(self._sec_sig), "doppler_hz": f"{dop:.0f}", "afc_hz": f"{afc:.0f}",
                        "sstv_ratio": f"{max(self._sec_ratio):.2f}" if self._sec_ratio else "",
                        "manual_offset_hz": f"{self.cfg.manual_offset_hz:.0f}",
                        "tuned_mhz": f"{(self.cfg.freq_hz + dop + afc + self.cfg.manual_offset_hz) / 1e6:.6f}",
                        "gain": "auto" if self.cfg.gain_db < 0 else f"{self.cfg.gain_db:g}", "ppm": self.cfg.ppm,
                        "iss_az_deg": f"{look[0]:.1f}" if look else "", "iss_el_deg": f"{look[1]:.1f}" if look else "",
                        "iss_range_km": f"{look[2]:.0f}" if look else "",
                        "decoder": dstate, "decoder_line": dline if dstate == "decoding" else "",
                        "iq_overflows": src.overflows if src else "",
                    })
                except (OSError, ValueError):
                    pass
            if now - self._last_status >= STATUS_LOG_S:
                self._last_status = now
                el = tr(", ISS el {el:.1f}°", el=look[1]) if look else ""
                self.events.put(("log", tr("Stato: SNR {m:.1f} dB (max {x:.1f}), Doppler {d:+.0f} Hz, AFC {a:+.0f} Hz{el}",
                                           m=snr_mean, x=snr_max, d=dop, a=afc, el=el)))
            self._sec_snr = []
            self._sec_ratio = []
            self._sec_sig = False
            self._sec = sec
        self._sec_snr.append(self.snr_db)
        self._sec_ratio.append(self.sstv_ratio)
        self._sec_sig = self._sec_sig or self.squelch_open

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
            self.events.put(("log", tr("Scheda ARISS: {f}", f=os.path.basename(txt))))
        except Exception as e:
            self.events.put(("log", tr("Scheda .txt non scritta: {e}", e=e)))

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
