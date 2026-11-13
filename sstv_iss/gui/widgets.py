"""Widget grafici: waterfall/spettro, immagine live, galleria, dialogo stazione."""
import glob
import os

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ..i18n import LANGUAGES, tr
from ..doppler import fmt_el, radio_horizon
from ..report import maidenhead

pg.setConfigOptions(antialias=False, imageAxisOrder="row-major")


def np_to_pixmap(img):
    img = np.ascontiguousarray(img)
    h, w, _ = img.shape
    q = QImage(img.data, w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(q.copy())


class WaterfallWidget(pg.GraphicsLayoutWidget):
    ROWS = 300

    def __init__(self, parent=None):
        super().__init__(parent)
        self.freqs = None
        self.data = None
        self.spec_plot = self.addPlot(row=0, col=0)
        self.spec_plot.setLabel("left", "dB")
        self.spec_plot.setLabel("bottom", tr("Scostamento dalla frequenza corretta"), units="Hz")
        self.spec_plot.showGrid(x=True, y=True, alpha=0.3)
        self.spec_plot.setMouseEnabled(x=False, y=False)
        self.curve = self.spec_plot.plot(pen=pg.mkPen("#4fc3f7", width=1))
        self.band = pg.LinearRegionItem([-7500, 7500], movable=False, brush=(255, 200, 0, 30), pen=(255, 200, 0, 80))
        self.spec_plot.addItem(self.band)
        self.spec_plot.addItem(pg.InfiniteLine(0, angle=90, pen=pg.mkPen("#ffcc00", style=Qt.DashLine)))
        self.wf_plot = self.addPlot(row=1, col=0)
        self.wf_plot.hideAxis("left")
        self.wf_plot.setMouseEnabled(x=False, y=False)
        self.wf_plot.setXLink(self.spec_plot)
        self.img = pg.ImageItem()
        self.img.setLookupTable(pg.colormap.get("inferno").getLookupTable(nPts=256))
        self.wf_plot.addItem(self.img)
        self.ci.layout.setRowStretchFactor(0, 1)
        self.ci.layout.setRowStretchFactor(1, 3)
        self.floor = None

    def add_rows(self, freqs, rows):
        if not rows:
            return
        if self.data is None or self.freqs is None or len(freqs) != self.data.shape[1]:
            self.freqs = freqs
            self.data = np.full((self.ROWS, len(freqs)), np.median(rows[-1]), np.float32)
            df = freqs[1] - freqs[0]
            self.img.setRect(freqs[0] - df / 2, 0, len(freqs) * df, self.ROWS)
            self.spec_plot.setXRange(freqs[0], freqs[-1], padding=0)
        k = min(len(rows), self.ROWS)
        self.data = np.roll(self.data, k, axis=0)
        self.data[:k] = np.array(rows[-k:])[::-1]
        last = rows[-1]
        fl = float(np.median(last))
        self.floor = fl if self.floor is None else 0.9 * self.floor + 0.1 * fl
        self.curve.setData(self.freqs, last)
        self.spec_plot.setYRange(self.floor - 10, self.floor + 45, padding=0)
        self.img.setImage(self.data[::-1], autoLevels=False, levels=(self.floor - 3, self.floor + 30))


class LiveImage(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#111; border:1px solid #333;")
        self._pix = None

    def set_image(self, img):
        self._pix = np_to_pixmap(img)
        self._rescale()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rescale()

    def _rescale(self):
        if self._pix:
            self.setPixmap(self._pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class Gallery(QListWidget):
    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.folder = folder
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(160, 120))
        self.setResizeMode(QListWidget.Adjust)
        self.setSpacing(4)
        self.itemDoubleClicked.connect(lambda it: os.startfile(it.data(Qt.UserRole)))
        self.refresh()

    def refresh(self):
        self.clear()
        files = sorted(glob.glob(os.path.join(self.folder, "*.png")), key=os.path.getmtime, reverse=True)
        for f in files[:200]:
            it = QListWidgetItem(QIcon(f), os.path.basename(f).replace("_robot36", "")[:-4])
            it.setData(Qt.UserRole, f)
            it.setToolTip(f)
            self.addItem(it)


CONTINENTS = ["Africa", "Antarctica", "Asia", "Australia", "Europe", "North America", "Oceania", "South America"]
CATEGORIES = [
    ("", "Nessuna"),  # etichette tradotte con tr() quando si costruisce il menu
    ("I am a formal or informal educator at the undergraduate level or higher.", "Educatore - università o superiore"),
    ("I am a formal or informal educator at the high school level or lower.", "Educatore - scuola superiore o inferiore"),
    ("I am a student at the undergraduate level or higher.", "Studente - università o superiore"),
    ("I am a student at the high school level or lower.", "Studente - scuola superiore o inferiore"),
]


class StationDialog(QDialog):
    """Maschera dei dati fissi della stazione (salvati in stazione.json)."""

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Stazione"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # --- operatore
        f1 = self._tab(tabs, tr("Operatore"),
                       tr("Dati per il modulo ARISS SSTV Gallery. Finiscono nella scheda .txt di ogni immagine."))
        self.callsign = self._text(cfg.callsign, tr("es. IT9XXX, oppure SWL se non hai un nominativo"))
        self.name = self._text(cfg.operator_name, tr("nome mostrato nella galleria ARISS"))
        self.email = self._text(cfg.email, tr("serve ad ARISS per inviare il certificato"))
        self.category = QComboBox()
        for value, label in CATEGORIES:
            self.category.addItem(tr(label), value)
        self.category.setCurrentIndex(max(0, self.category.findData(cfg.category)))
        self.campaign = QComboBox()
        self.campaign.setEditable(True)
        self.campaign.addItem(cfg.campaign)
        self.campaign.setToolTip(tr("Testo esatto della campagna nel menu del modulo ARISS"))
        self.language = QComboBox()
        for code, label in LANGUAGES:
            self.language.addItem(label, code)
        self.language.setCurrentIndex(max(0, self.language.findData(cfg.language)))
        self.language.setToolTip(tr("Lingua del programma e delle schede .txt (richiede un riavvio)"))
        f1.addRow(tr("Lingua"), self.language)
        f1.addRow(tr("Nominativo"), self.callsign)
        f1.addRow(tr("Nome"), self.name)
        f1.addRow("Email", self.email)
        f1.addRow(tr("Categoria"), self.category)
        f1.addRow(tr("Campagna SSTV"), self.campaign)

        # --- posizione
        f2 = self._tab(tabs, tr("Posizione"), tr("Coordinate del punto di ricezione: servono per Doppler, passaggi e locator.\n"
                                                "Su Google Maps: clic destro sul punto e copia le coordinate."))
        self.lat = self._spin(-90, 90, cfg.lat, 6, "°")
        self.lon = self._spin(-180, 180, cfg.lon, 6, "°")
        self.alt = self._spin(-100, 5000, cfg.alt_m, 0, " m")
        self.grid = QLabel()
        self.grid.setStyleSheet("font-weight:bold;")
        self.continent = QComboBox()
        self.continent.addItems(CONTINENTS)
        self.continent.setCurrentText(cfg.continent if cfg.continent in CONTINENTS else "Europe")
        for s in (self.lat, self.lon):
            s.valueChanged.connect(self._update_grid)
        self.hz_auto = QCheckBox()
        self.hz_auto.setChecked(cfg.horizon_deg is None)
        self.hz = self._spin(-5, 10, cfg.horizon, 1, "°")
        self.hz.setSingleStep(0.1)
        hz_tip = tr("Elevazione sotto la quale l'ISS è considerata tramontata: vale per la tabella dei passaggi, "
                    "l'avvio e l'arresto automatici. In automatico è l'abbassamento dell'orizzonte dovuto alla quota "
                    "(586 m: -0,8°). Inserisci un valore a mano se montagne o palazzi coprono il cielo basso.")
        hz_row = QWidget()
        hl = QHBoxLayout(hz_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.hz)
        hl.addWidget(self.hz_auto, 1)
        for w in (self.hz, self.hz_auto, hz_row):
            w.setToolTip(hz_tip)
        self.hz_auto.toggled.connect(self._update_horizon)
        self.alt.valueChanged.connect(self._update_horizon)
        f2.addRow(tr("Latitudine (N +)"), self.lat)
        f2.addRow(tr("Longitudine (E +)"), self.lon)
        f2.addRow(tr("Altitudine s.l.m."), self.alt)
        f2.addRow(tr("Locator (calcolato)"), self.grid)
        f2.addRow(tr("Orizzonte radio"), hz_row)
        f2.addRow(tr("Continente"), self.continent)
        self._update_grid()
        self._update_horizon()

        # --- attrezzatura
        f3 = self._tab(tabs, tr("Attrezzatura"), tr("Dati richiesti da ARISS per caratterizzare il segnale SSTV."))
        self.receiver = self._text(cfg.receiver, "")
        self.sens = self._text(cfg.rx_sensitivity, tr("es. 0.5 uV (-113 dBm)"))
        self.nf = self._spin(0, 20, cfg.rx_nf_db, 1, " dB")
        self.nf.setToolTip(tr("Usata per stimare il livello in dBm e l'S-meter dall'SNR misurato"))
        self.antenna = self._text(cfg.antenna, tr("es. Yagi 7 elementi 70 cm, ground-plane..."))
        self.ant_gain = self._spin(-10, 30, cfg.antenna_gain_dbi, 1, " dBi")
        self.preamp = self._text(cfg.preamp, tr("vuoto se non usi un preamplificatore"))
        self.pre_gain = self._spin(0, 40, cfg.preamp_gain_db, 1, " dB")
        self.cable = self._text(cfg.cable, tr("es. RG-58, 10 m"))
        self.cable_loss = self._spin(0, 30, cfg.cable_loss_db, 1, " dB")
        self.notes = self._text(cfg.station_notes, tr("facoltativo, finisce nei commenti ARISS"))
        f3.addRow(tr("Ricevitore"), self.receiver)
        f3.addRow(tr("Sensibilità FM"), self.sens)
        f3.addRow(tr("Cifra di rumore (stima)"), self.nf)
        f3.addRow("Antenna", self.antenna)
        f3.addRow(tr("Guadagno antenna"), self.ant_gain)
        f3.addRow(tr("Preamplificatore"), self.preamp)
        f3.addRow(tr("Guadagno preamp."), self.pre_gain)
        f3.addRow(tr("Cavo"), self.cable)
        f3.addRow(tr("Perdita cavo stimata"), self.cable_loss)
        f3.addRow(tr("Note"), self.notes)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    @staticmethod
    def _tab(tabs, title, intro):
        w = QWidget()
        v = QVBoxLayout(w)
        lbl = QLabel(intro)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#888;")
        v.addWidget(lbl)
        form = QFormLayout()
        v.addLayout(form)
        v.addStretch(1)
        tabs.addTab(w, title)
        return form

    @staticmethod
    def _text(value, placeholder):
        e = QLineEdit(value)
        e.setPlaceholderText(placeholder)
        return e

    @staticmethod
    def _spin(lo, hi, val, dec, suffix):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(dec)
        s.setValue(val)
        s.setSuffix(suffix)
        return s

    def _update_grid(self):
        self.grid.setText(maidenhead(self.lat.value(), self.lon.value()))

    def _update_horizon(self):
        auto = radio_horizon(self.alt.value())
        self.hz_auto.setText(tr("automatico dalla quota ({h})", h=fmt_el(auto)))
        self.hz.setEnabled(not self.hz_auto.isChecked())
        if self.hz_auto.isChecked():
            self.hz.setValue(auto)

    def apply(self, cfg):
        cfg.language = self.language.currentData() or "it"
        cfg.callsign = self.callsign.text().strip().upper()
        cfg.operator_name = self.name.text().strip()
        cfg.email = self.email.text().strip()
        cfg.category = self.category.currentData() or ""
        cfg.campaign = self.campaign.currentText().strip()
        cfg.lat, cfg.lon = self.lat.value(), self.lon.value()
        cfg.alt_m = self.alt.value()
        cfg.horizon_deg = None if self.hz_auto.isChecked() else round(self.hz.value(), 1)
        cfg.continent = self.continent.currentText()
        cfg.receiver = self.receiver.text().strip()
        cfg.rx_sensitivity = self.sens.text().strip()
        cfg.rx_nf_db = self.nf.value()
        cfg.antenna = self.antenna.text().strip()
        cfg.antenna_gain_dbi = self.ant_gain.value()
        cfg.preamp = self.preamp.text().strip()
        cfg.preamp_gain_db = self.pre_gain.value()
        cfg.cable = self.cable.text().strip()
        cfg.cable_loss_db = self.cable_loss.value()
        cfg.station_notes = self.notes.text().strip()
