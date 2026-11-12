"""Finestra principale di AssicutaISS."""
import os
import queue
import re
import threading
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGridLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QSlider, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import WINDOW_TITLE, __version__, audio_out
from ..config import APP_DIR
from ..i18n import tr, weekday
from ..doppler import IssTracker
from ..engine import Engine
from ..sdr_source import R820T_GAINS
from ..report import maidenhead, write_report
from ..telemetry import SessionLog, settings_diff, settings_items, settings_text
from ..sstv.robot36 import decode_audio_file
from .widgets import Gallery, LiveImage, StationDialog, WaterfallWidget


def fmt_hz(v):
    return f"{v:+,.0f} Hz".replace(",", ".")


class MainWindow(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        os.makedirs(cfg.images_dir, exist_ok=True)
        self.tracker = IssTracker(os.path.join(APP_DIR, "data"))
        self.engine = Engine(cfg, self.tracker)
        self.ui_q = queue.Queue()             # funzioni da eseguire nel thread GUI
        self.passes = []            # passaggi mostrati (el. max >= soglia)
        self.all_passes = []        # tutti i passaggi delle prossime 48 h
        self.last_img_ver = -1
        self.auto_started = False
        self._auto_pass = None      # passaggio valutato per l'avvio automatico (cache fino al LOS)
        self._auto_skipped = None   # AOS del passaggio già annunciato come saltato
        self.lang_at_start = cfg.language
        self.session_log = SessionLog()
        self._settings = dict(settings_items(cfg))
        self._diff_timer = QTimer(self)
        self._diff_timer.setSingleShot(True)
        self._diff_timer.timeout.connect(self._log_settings_diff)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1400, 820)
        self._build()
        self._load_settings_into_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)
        self.slow = QTimer(self)
        self.slow.timeout.connect(self._slow_tick)
        self.slow.start(1000)

        if cfg.station_set:
            self.tracker.set_station(cfg.lat, cfg.lon, cfg.alt_m)
        self.log_msg(tr("{app} avviato. Registro: {p}", app=WINDOW_TITLE, p=self.session_log.path or "-")
                     + "\n" + tr("Impostazioni:") + "\n" + settings_text(cfg))
        self._settings = dict(settings_items(cfg))
        self._bg(self._load_tle_and_passes)
        if not cfg.station_set:
            QTimer.singleShot(300, self._edit_station)

    # ================================================================ UI
    def _build(self):
        central = QWidget()
        root = QVBoxLayout(central)

        # ---- barra controlli
        bar = QHBoxLayout()
        self.btn_start = QPushButton(tr("▶  Avvia ricezione"))
        self.btn_start.setMinimumWidth(170)
        self.btn_start.setStyleSheet("font-weight:bold; padding:6px;")
        self.btn_start.clicked.connect(self._toggle)
        bar.addWidget(self.btn_start)

        bar.addWidget(QLabel(tr("Frequenza")))
        self.freq = QDoubleSpinBox()
        self.freq.setRange(24.0, 1766.0)
        self.freq.setDecimals(4)
        self.freq.setSuffix(" MHz")
        self.freq.setSingleStep(0.005)
        self.freq.editingFinished.connect(self._freq_changed)
        bar.addWidget(self.freq)

        bar.addWidget(QLabel(tr("Guadagno")))
        self.gain = QComboBox()
        self.gain.addItem("Auto", -1.0)
        for g in R820T_GAINS:
            self.gain.addItem(f"{g:.1f} dB", g)
        self.gain.currentIndexChanged.connect(self._gain_changed)
        bar.addWidget(self.gain)

        bar.addWidget(QLabel("PPM"))
        self.ppm = QSpinBox()
        self.ppm.setRange(-200, 200)
        self.ppm.editingFinished.connect(self._ppm_changed)
        bar.addWidget(self.ppm)

        self.chk_doppler = QCheckBox("Doppler")
        self.chk_afc = QCheckBox("AFC")
        self.chk_bias = QCheckBox("Bias-T")
        self.chk_wav = QCheckBox(tr("Registra WAV"))
        self.chk_auto = QCheckBox(tr("Avvio automatico ai passaggi"))
        bar2 = QHBoxLayout()
        for c in (self.chk_doppler, self.chk_afc, self.chk_bias, self.chk_wav, self.chk_auto):
            c.toggled.connect(self._checks_changed)
            bar2.addWidget(c)
        bar2.addWidget(QLabel(tr("con el. max ≥")))
        self.auto_min_el = QSpinBox()
        self.auto_min_el.setRange(0, 90)
        self.auto_min_el.setSuffix("°")
        self.auto_min_el.setToolTip(tr("Soglia unica: la tabella mostra e l'avvio automatico riceve solo "
                                       "i passaggi con elevazione massima almeno pari a questo valore"))
        self.auto_min_el.valueChanged.connect(self._auto_min_el_changed)
        bar2.addWidget(self.auto_min_el)
        bar2.addSpacing(24)
        self.chk_mon = QCheckBox(tr("Ascolto"))
        self.chk_mon.setToolTip(tr("Riproduce l'audio demodulato per sentire il segnale"))
        self.cmb_out = QComboBox()
        self.cmb_out.setMinimumWidth(260)
        self.cmb_out.addItem(tr("Uscita predefinita di Windows"), "")
        for name in audio_out.list_outputs():
            self.cmb_out.addItem(name, name)
        self.sld_vol = QSlider(Qt.Horizontal)
        self.sld_vol.setRange(0, 100)
        self.sld_vol.setFixedWidth(120)
        self.chk_mute = QCheckBox(tr("Silenzia senza segnale"))
        bar2.addWidget(self.chk_mon)
        bar2.addWidget(self.cmb_out)
        bar2.addWidget(QLabel("Volume"))
        bar2.addWidget(self.sld_vol)
        bar2.addWidget(self.chk_mute)
        if not audio_out.available():
            for w in (self.chk_mon, self.cmb_out, self.sld_vol, self.chk_mute):
                w.setEnabled(False)
            self.chk_mon.setToolTip(tr("Ascolto non disponibile: {e}", e=audio_out.IMPORT_ERROR))
        self.chk_mon.toggled.connect(self._monitor_changed)
        self.cmb_out.currentIndexChanged.connect(self._monitor_changed)
        self.sld_vol.valueChanged.connect(self._monitor_volume)
        self.chk_mute.toggled.connect(self._monitor_volume)
        bar2.addStretch(1)

        bar.addWidget(QLabel("Offset"))
        self.offset = QSpinBox()
        self.offset.setRange(-20000, 20000)
        self.offset.setSingleStep(100)
        self.offset.setSuffix(" Hz")
        self.offset.valueChanged.connect(self._offset_changed)
        bar.addWidget(self.offset)

        bar.addWidget(QLabel("Squelch AFC"))
        self.squelch = QDoubleSpinBox()
        self.squelch.setRange(-10, 40)
        self.squelch.setDecimals(1)
        self.squelch.setSuffix(" dB")
        self.squelch.valueChanged.connect(
            lambda v: None if getattr(self, "_loading", False) else (setattr(self.cfg, "squelch_db", v),
                                                                       self._settings_changed()))
        bar.addWidget(self.squelch)
        bar.addStretch(1)
        root.addLayout(bar)
        root.addLayout(bar2)

        # ---- corpo
        split = QSplitter(Qt.Horizontal)

        # pannello sinistro
        left = QWidget()
        ll = QVBoxLayout(left)
        g_freq = QGroupBox(tr("Frequenze"))
        gf = QGridLayout(g_freq)
        big = QFont()
        big.setPointSize(13)
        big.setBold(True)
        self.lbl_nom = QLabel()
        self.lbl_dop = QLabel()
        self.lbl_afc = QLabel()
        self.lbl_eff = QLabel()
        self.lbl_eff.setFont(big)
        for i, (t, w) in enumerate(((tr("Nominale"), self.lbl_nom), ("Doppler (TLE)", self.lbl_dop),
                                    ("AFC", self.lbl_afc), (tr("Sintonia effettiva"), self.lbl_eff))):
            gf.addWidget(QLabel(t), i, 0)
            gf.addWidget(w, i, 1)
        btn_afc = QPushButton(tr("Azzera AFC"))
        btn_afc.clicked.connect(self.engine.reset_afc)
        gf.addWidget(btn_afc, 4, 0, 1, 2)
        ll.addWidget(g_freq)

        g_sig = QGroupBox(tr("Segnale"))
        gs = QVBoxLayout(g_sig)
        self.snr_bar = QProgressBar()
        self.snr_bar.setRange(-5, 40)
        self.snr_bar.setFormat("SNR %v dB")
        gs.addWidget(self.snr_bar)
        self.lbl_sq = QLabel()
        self.lbl_dec = QLabel()
        self.lbl_dec.setWordWrap(True)
        gs.addWidget(self.lbl_sq)
        gs.addWidget(self.lbl_dec)
        ll.addWidget(g_sig)

        g_iss = QGroupBox("ISS")
        gi = QVBoxLayout(g_iss)
        self.lbl_iss = QLabel("-")
        self.lbl_iss.setFont(big)
        self.lbl_next = QLabel("-")
        self.lbl_next.setWordWrap(True)
        self.lbl_tle = QLabel(tr("TLE: caricamento..."))
        self.lbl_tle.setWordWrap(True)
        self.lbl_tle.setStyleSheet("color:#888;")
        gi.addWidget(self.lbl_iss)
        gi.addWidget(self.lbl_next)
        hb = QHBoxLayout()
        b1 = QPushButton(tr("Stazione e nominativo..."))
        b1.clicked.connect(self._edit_station)
        b2 = QPushButton(tr("Aggiorna TLE"))
        b2.clicked.connect(lambda: self._bg(lambda: self._load_tle_and_passes(force=True)))
        hb.addWidget(b1)
        hb.addWidget(b2)
        gi.addLayout(hb)
        gi.addWidget(self.lbl_tle)
        ll.addWidget(g_iss)

        g_pass = QGroupBox()
        self.g_pass = g_pass
        gp = QVBoxLayout(g_pass)
        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels([tr("Giorno"), tr("Inizio"), tr("Fine"), tr("El. max")])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        gp.addWidget(self.tbl)
        ll.addWidget(g_pass, 1)
        left.setMinimumWidth(300)
        split.addWidget(left)

        # centro: waterfall
        self.wf = WaterfallWidget()
        split.addWidget(self.wf)

        # destra: immagine + galleria
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel(tr("Immagine in ricezione")))
        self.live = LiveImage()
        rl.addWidget(self.live, 3)
        hb2 = QHBoxLayout()
        b_dec = QPushButton(tr("Decodifica file WAV..."))
        b_dec.clicked.connect(self._decode_file)
        b_open = QPushButton(tr("Apri cartella immagini"))
        b_open.clicked.connect(lambda: os.startfile(self.cfg.images_dir))
        hb2.addWidget(b_dec)
        hb2.addWidget(b_open)
        rl.addLayout(hb2)
        rl.addWidget(QLabel(tr("Immagini ricevute (doppio clic per aprire)")))
        self.gallery = Gallery(self.cfg.images_dir)
        rl.addWidget(self.gallery, 2)
        right.setMinimumWidth(360)
        split.addWidget(right)
        split.setSizes([320, 640, 440])
        root.addWidget(split, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        root.addWidget(self.log)
        self.setCentralWidget(central)

    def _load_settings_into_ui(self):
        self._loading = True
        try:
            self._fill_ui()
        finally:
            self._loading = False
        self._monitor_volume()
        if self.cfg.monitor:
            self._monitor_changed()

    def _monitor_volume(self):
        if getattr(self, "_loading", False):
            return
        self.cfg.monitor_volume = self.sld_vol.value()
        self.cfg.monitor_mute = self.chk_mute.isChecked()
        # curva quadratica: il fruscio FM è quasi a fondo scala, serve finezza sui valori bassi
        self.engine.monitor.volume = (self.cfg.monitor_volume / 100.0) ** 2
        self.engine.monitor.mute_without_signal = self.cfg.monitor_mute
        self._settings_changed()

    def _monitor_changed(self):
        if getattr(self, "_loading", False):
            return
        c = self.cfg
        c.monitor = self.chk_mon.isChecked()
        c.monitor_device = self.cmb_out.currentData() or ""
        mon = self.engine.monitor
        self._settings_changed()
        if not c.monitor:
            if mon.active:
                mon.stop()
                self.log_msg(tr("Ascolto disattivato"))
            return
        try:
            mon.start(c.monitor_device or None)
            self.log_msg(tr("Ascolto su: {o}", o=self.cmb_out.currentText()))
        except Exception as e:
            self.log_msg(tr("Impossibile aprire l'uscita audio: {e}", e=e))
            self._loading = True
            self.chk_mon.setChecked(False)
            self._loading = False
            c.monitor = False

    def _fill_ui(self):
        c = self.cfg
        self.freq.setValue(c.freq_hz / 1e6)
        idx = self.gain.findData(c.gain_db)
        self.gain.setCurrentIndex(idx if idx >= 0 else 0)
        self.ppm.setValue(c.ppm)
        self.chk_doppler.setChecked(c.doppler)
        self.chk_afc.setChecked(c.afc)
        self.chk_bias.setChecked(c.bias_tee)
        self.chk_wav.setChecked(c.record_wav)
        self.chk_auto.setChecked(c.auto_pass)
        self.auto_min_el.setValue(int(round(c.auto_min_el)))
        self.offset.setValue(int(c.manual_offset_hz))
        self.squelch.setValue(c.squelch_db)
        idx = self.cmb_out.findData(c.monitor_device)
        self.cmb_out.setCurrentIndex(idx if idx >= 0 else 0)
        self.sld_vol.setValue(int(c.monitor_volume))
        self.chk_mute.setChecked(c.monitor_mute)
        self.chk_mon.setChecked(c.monitor and audio_out.available())

    # =========================================================== azioni
    def log_msg(self, text):
        self.log.appendPlainText(f"{datetime.now():%H:%M:%S}  {text}")
        self.session_log.write(text)

    def _settings_changed(self):
        """Da chiamare dopo ogni modifica: dopo 1,5 s di calma registra le differenze."""
        self._diff_timer.start(1500)

    def _log_settings_diff(self):
        new = dict(settings_items(self.cfg))
        for line in settings_diff(self._settings, new):
            self.log_msg(tr("Impostazione modificata - {c}", c=line))
        self._settings = new

    def _bg(self, fn):
        def run():
            try:
                fn()
            except Exception as e:
                self.ui_q.put(lambda: self.log_msg(tr("Errore: {e}", e=e)))
        threading.Thread(target=run, daemon=True).start()

    def _load_tle_and_passes(self, force=False):
        msg = self.tracker.load_tle(force)
        self.ui_q.put(lambda: (self.lbl_tle.setText(msg), self.log_msg(msg)))
        self._compute_passes()

    def _compute_passes(self):
        p = self.tracker.passes(48, 0.0)
        self.ui_q.put(lambda: self._show_passes(p))

    def _show_passes(self, all_passes):
        now = datetime.now().astimezone()
        self.all_passes = [p for p in all_passes if p["los"] > now]
        passes = [p for p in self.all_passes if p["max_el"] >= self.cfg.auto_min_el]
        self.passes = passes
        self.g_pass.setTitle(tr("Prossimi passaggi (48 h, el. max ≥ {e:.0f}°)", e=self.cfg.auto_min_el))
        self.tbl.setRowCount(len(passes))
        for r, p in enumerate(passes):
            vals = [f"{weekday(p['aos'])} {p['aos']:%d/%m}", f"{p['aos']:%H:%M:%S}", f"{p['los']:%H:%M:%S}", f"{p['max_el']:.0f}°"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignCenter)
                if p["max_el"] >= 40:
                    it.setForeground(Qt.darkGreen)
                self.tbl.setItem(r, c, it)

    def _edit_station(self):
        d = StationDialog(self.cfg, self)
        if d.exec():
            d.apply(self.cfg)
            self.cfg.save_station()
            self.tracker.set_station(self.cfg.lat, self.cfg.lon, self.cfg.alt_m)
            c = self.cfg
            self._log_settings_diff()
            self.log_msg(tr("Stazione {call}: {lat:.4f}, {lon:.4f}, {alt:.0f} m, locator {grid} - salvata in stazione.json",
                            call=c.callsign or "SWL", lat=c.lat, lon=c.lon, alt=c.alt_m, grid=maidenhead(c.lat, c.lon)))
            if c.language != self.lang_at_start:
                self._offer_restart()
            self._bg(self._compute_passes)

    def _toggle(self):
        if self.engine.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        try:
            self.engine.reset_afc()
            self.engine.start()
        except Exception as e:  # solo errori definitivi: se il dongle manca, l'engine resta in attesa
            QMessageBox.critical(self, tr("Errore ricevitore"), str(e))
            self.log_msg(str(e))
            return False
        self._log_settings_diff()
        look = self.tracker.look()
        iss = tr("ISS: az {az:.0f}°, el {el:+.1f}°, distanza {d:.0f} km", az=look[0], el=look[1], d=look[2]) \
            if look else tr("ISS: posizione non disponibile")
        self.log_msg(tr("=== Avvio ricezione (AssicutaISS v. {v}) ===", v=__version__) + "\n"
                     + settings_text(self.cfg) + "\n  " + iss + "\n  " + self.lbl_tle.text())
        self.btn_start.setText(tr("■  Ferma ricezione"))
        self.btn_start.setStyleSheet("font-weight:bold; padding:6px; background:#c62828; color:white;")
        return True

    def _stop(self):
        self.engine.stop()
        self.btn_start.setText(tr("▶  Avvia ricezione"))
        self.btn_start.setStyleSheet("font-weight:bold; padding:6px;")

    def _freq_changed(self):
        hz = int(round(self.freq.value() * 1e6))
        if hz != self.cfg.freq_hz:
            self.cfg.freq_hz = hz
            self.engine.retune()
            self.engine.reset_afc()
            self.cfg.save()
            self._settings_changed()

    def _gain_changed(self):
        if getattr(self, "_loading", False):
            return
        self.cfg.gain_db = float(self.gain.currentData())
        self.engine.set_gain(self.cfg.gain_db)
        self._settings_changed()

    def _ppm_changed(self):
        if self.ppm.value() != self.cfg.ppm:
            self.cfg.ppm = self.ppm.value()
            self.engine.set_ppm(self.cfg.ppm)
            self._settings_changed()

    def _auto_min_el_changed(self, v):
        if getattr(self, "_loading", False):
            return
        self.cfg.auto_min_el = float(v)
        self._show_passes(self.all_passes)
        self._settings_changed()

    def _offset_changed(self, v):
        if getattr(self, "_loading", False):
            return
        self.cfg.manual_offset_hz = float(v)
        self._settings_changed()

    def _checks_changed(self):
        if getattr(self, "_loading", False):
            return
        c = self.cfg
        c.doppler = self.chk_doppler.isChecked()
        c.afc = self.chk_afc.isChecked()
        c.bias_tee = self.chk_bias.isChecked()
        c.auto_pass = self.chk_auto.isChecked()
        wav = self.chk_wav.isChecked()
        if wav != c.record_wav:
            c.record_wav = wav
            if self.engine.running:
                self.engine.start_wav() if wav else self.engine.stop_wav()
        self._settings_changed()

    def _decode_file(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Decodifica registrazione audio"), self.cfg.images_dir,
                                              "Audio WAV (*.wav)")
        if not path:
            return
        self.log_msg(tr("Decodifica di {f}...", f=os.path.basename(path)))

        def ev(kind, info):
            if kind == "image" and info.get("path"):
                try:
                    write_report(info["path"], info, self.cfg, self.tracker, None,
                                 source=tr("decodifica del file {f} (orario da {when})", f=os.path.basename(path), when=when))
                except Exception as e:
                    self.ui_q.put(lambda e=e: self.log_msg(tr("Scheda .txt non scritta: {e}", e=e)))
            self.ui_q.put(lambda: self._handle_event(kind, info))

        when = tr("nome del file") if re.search(r"\d{8}_\d{6}Z", os.path.basename(path)) else tr("data del file, stima")

        def run():
            dec = decode_audio_file(path, self.cfg.images_dir, on_event=ev)
            self.ui_q.put(lambda: self.log_msg(tr("Decodifica file terminata: {n} immagini", n=dec.image_count)))
        self._bg(run)

    # ============================================================ timer
    def _handle_event(self, kind, info):
        if kind == "log":
            self.log_msg(info)
        elif kind == "error":
            self.log_msg(info)
            self._stop()
        elif kind == "vis":
            if info["supported"]:
                self.log_msg(tr("VIS Robot36 rilevato: inizio immagine"))
            else:
                self.log_msg(tr("VIS codice {c} (non Robot36 o parità errata) ignorato", c=info["code"]))
        elif kind == "start":
            if info["mode"] == "sync":
                self.log_msg(tr("Treno di sync Robot36 rilevato (VIS perso): inizio immagine"))
        elif kind == "image":
            tag = tr(" (parziale)") if info["partial"] else ""
            self.log_msg(tr("Immagine salvata{tag}: {f} [{n} righe, slant {ppm:+.0f} ppm]", tag=tag,
                            f=os.path.basename(info["path"] or ""), n=info["lines"], ppm=info.get("slant_ppm", 0)))
            self.gallery.refresh()
        elif kind == "discard":
            self.log_msg(tr("Falso avvio scartato ({n} righe)", n=info["lines"]))

    def _tick(self):
        while True:
            try:
                fn = self.ui_q.get_nowait()
            except queue.Empty:
                break
            fn()
        while True:
            try:
                kind, info = self.engine.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(kind, info)

        s = self.engine.snapshot()
        rows = self.engine.pop_spectrum()
        if rows and self.engine.spec_freqs is not None:
            self.wf.add_rows(self.engine.spec_freqs, rows)
        if s["image_version"] != self.last_img_ver:
            self.last_img_ver = s["image_version"]
            self.live.set_image(s["image"])

        f0 = self.cfg.freq_hz
        eff = f0 + s["doppler"] + s["afc"] + self.cfg.manual_offset_hz
        self.lbl_nom.setText(f"{f0 / 1e6:.4f} MHz")
        self.lbl_dop.setText(fmt_hz(s["doppler"]) if self.cfg.doppler else tr("disattivato"))
        self.lbl_afc.setText(fmt_hz(s["afc"]) if self.cfg.afc else tr("disattivato"))
        self.lbl_eff.setText(f"{eff / 1e6:.5f} MHz")
        if s["waiting"]:
            self.snr_bar.setValue(-5)
            self.lbl_sq.setText(tr("In attesa del dongle… (collegalo o chiudi SDR#/SDR++)"))
            self.lbl_sq.setStyleSheet("color:#e08a2c; font-weight:bold;")
        elif s["running"]:
            self.snr_bar.setValue(int(round(s["snr"])))
            self.lbl_sq.setText(tr("Segnale presente (AFC attivo)") if s["squelch"] else tr("Nessun segnale"))
            self.lbl_sq.setStyleSheet("color:#2e7d32; font-weight:bold;" if s["squelch"] else "color:#888;")
        else:
            self.snr_bar.setValue(-5)
            self.lbl_sq.setText(tr("Ricevitore fermo"))
            self.lbl_sq.setStyleSheet("color:#888;")
        self.lbl_dec.setText(s["status"])

    def _slow_tick(self):
        look = self.tracker.look()
        now = datetime.now().astimezone()
        if look:
            az, el, dist, _ = look
            self.lbl_iss.setText(f"Az {az:5.1f}°   El {el:+5.1f}°   {dist:,.0f} km".replace(",", "."))
            self.lbl_iss.setStyleSheet("color:#2e7d32;" if el > 0 else "color:#555;")
        else:
            self.lbl_iss.setText(tr("Imposta la posizione della stazione"))
        nxt = next((p for p in self.passes if p["los"] > now), None)
        if nxt:
            if nxt["aos"] <= now:
                self.lbl_next.setText(tr("PASSAGGIO IN CORSO - fine alle {t}, el. max {el:.0f}°",
                                         t=f"{nxt['los']:%H:%M:%S}", el=nxt["max_el"]))
            else:
                dt = int((nxt["aos"] - now).total_seconds())
                self.lbl_next.setText(tr("Prossimo passaggio tra {h:d}h {m:02d}m {s:02d}s (el. max {el:.0f}°)",
                                         h=dt // 3600, m=dt % 3600 // 60, s=dt % 60, el=nxt["max_el"]))
        elif self.passes == [] and self.tracker.ready:
            self.lbl_next.setText(tr("Nessun passaggio nelle prossime 48 h"))
        # ricalcolo passaggi quando la lista si esaurisce
        if self.tracker.ready and self.all_passes and self.all_passes[0]["los"] < now:
            self._show_passes(self.all_passes)
            if len(self.all_passes) < 3:
                self._bg(self._compute_passes)
        # avvio/arresto automatico (orizzonte: elevazione > -1°)
        if self.cfg.auto_pass and look:
            el = look[1]
            if el > -1.0 and not self.engine.running:
                p = self._auto_pass_info()
                max_el = p["max_el"] if p else None
                if max_el is not None and max_el < self.cfg.auto_min_el:
                    if self._auto_skipped != p["aos"]:
                        self._auto_skipped = p["aos"]
                        self.log_msg(tr("Avvio automatico: passaggio saltato, el. max {e:.0f}° sotto la soglia di {s:.0f}°",
                                        e=max_el, s=self.cfg.auto_min_el))
                elif self._start():
                    self.auto_started = True
                    self.log_msg(tr("Avvio automatico: ISS in arrivo (el. max {e})",
                                    e=f"{max_el:.0f}°" if max_el is not None else "?"))
                else:
                    self.chk_auto.setChecked(False)
                    self.log_msg(tr("Avvio automatico disattivato: libreria RTL-SDR non utilizzabile"))
            elif el < -2.0 and self.engine.running and self.auto_started:
                self._stop()
                self.auto_started = False
                self.log_msg(tr("Arresto automatico: ISS sotto l'orizzonte"))

    def _offer_restart(self):
        r = QMessageBox.question(self, tr("Lingua"),
                                 tr("La nuova lingua sarà usata al prossimo avvio. Riavviare ora AssicutaISS?"))
        if r == QMessageBox.Yes:
            import subprocess
            import sys
            self.close()
            subprocess.Popen([sys.executable, os.path.join(APP_DIR, "main.py")], cwd=APP_DIR)
            from PySide6.QtWidgets import QApplication
            QApplication.quit()

    def _auto_pass_info(self):
        """Passaggio in corso o imminente, calcolato una volta e tenuto fino al suo LOS."""
        now = datetime.now().astimezone()
        p = self._auto_pass
        if p is None or p["los"] <= now:
            p = self.tracker.pass_around(now.timestamp())
            self._auto_pass = p
        return p

    def closeEvent(self, e):
        self.engine.stop()
        self.engine.monitor.stop()
        while not self.engine.events.empty():   # ultimi messaggi dell'engine (es. "Ricevitore fermato")
            try:
                self._handle_event(*self.engine.events.get_nowait())
            except Exception:
                break
        self._log_settings_diff()
        self.log_msg(tr("Programma chiuso"))
        self.session_log.close()
        self.cfg.save()
        super().closeEvent(e)
