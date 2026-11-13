"""Mappa della posizione dell'ISS in tempo reale, disegnata dal programma con gli stessi TLE del Doppler.

Planisfero equirettangolare (Natural Earth 1:110m, dominio pubblico) con zona notte, traccia a terra
(passata tratteggiata, futura continua), cerchio di visibilità calcolato con l'orizzonte radio della stazione
e posizione della stazione. Un clic apre isstracker.pl nel browser.
"""
import json
import math
import os
import time

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QImage, QPainter, QPainterPath, QPen,
                           QPolygonF, QTransform)
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..config import APP_DIR
from ..i18n import tr

ISS_TRACKER_URL = "https://isstracker.pl/en"
LAND_PATH = os.path.join(APP_DIR, "assets", "world_land.json")
LAT_TOP, LAT_BOTTOM = 75.0, -75.0      # l'ISS non supera ±52°: si taglia l'estremo nord e l'Antartide
EARTH_R_KM = 6371.0
TRACK_EVERY_S = 30
NIGHT_EVERY_S = 60

OCEAN = QColor("#16324a")
LAND = QColor("#3f6e4a")
COAST = QColor("#5d8f68")
GRID = QColor(255, 255, 255, 28)
PAST = QColor(255, 255, 255, 140)
FUTURE = QColor("#ffcc33")
ISS = QColor("#ff4b3e")
STATION = QColor("#4fd1ff")
FOOT_IN = QColor("#56e07a")
FOOT_OUT = QColor(255, 255, 255, 150)


def subsolar(unix):
    """Punto sub-solare (lat°, lon°) con le formule approssimate dell'Astronomical Almanac (errore < 0,1°)."""
    n = unix / 86400.0 - 10957.5                       # giorni da J2000.0
    L = math.radians((280.460 + 0.9856474 * n) % 360)
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = L + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 0.0000004 * n)
    dec = math.asin(math.sin(eps) * math.sin(lam))
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    gmst = math.radians((280.46061837 + 360.98564736629 * n) % 360)
    lon = (math.degrees(ra - gmst) + 180.0) % 360.0 - 180.0
    return math.degrees(dec), lon


def footprint(lat, lon, alt_km, horizon_deg, steps=72):
    """Cerchio da cui l'ISS è sopra l'orizzonte dato: lista di (lat°, lon°)."""
    e = math.radians(horizon_deg)
    lam = math.acos(EARTH_R_KM / (EARTH_R_KM + alt_km) * math.cos(e)) - e
    p1, l1 = math.radians(lat), math.radians(lon)
    pts = []
    for k in range(steps + 1):
        b = 2 * math.pi * k / steps
        p2 = math.asin(math.sin(p1) * math.cos(lam) + math.cos(p1) * math.sin(lam) * math.cos(b))
        l2 = l1 + math.atan2(math.sin(b) * math.sin(lam) * math.cos(p1), math.cos(lam) - math.sin(p1) * math.sin(p2))
        pts.append((math.degrees(p2), (math.degrees(l2) + 180.0) % 360.0 - 180.0))
    return pts


def split_antimeridian(lats, lons):
    """Spezza una linea dove attraversa il 180° meridiano, per non tracciare righe da un bordo all'altro."""
    segs, cur = [], []
    prev = None
    for la, lo in zip(lats, lons):
        if prev is not None and abs(lo - prev) > 180.0:
            segs.append(cur)
            cur = []
        cur.append((la, lo))
        prev = lo
    if cur:
        segs.append(cur)
    return [s for s in segs if len(s) > 1]


def _load_land():
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    try:
        with open(LAND_PATH, encoding="utf-8") as f:
            polys = json.load(f)["polygons"]
    except Exception:
        return path
    for poly in polys:
        path.addPolygon(QPolygonF([QPointF(x, -y) for x, y in poly]))
        path.closeSubpath()
    return path


class IssMap(QWidget):
    def __init__(self, tracker, horizon, station, parent=None):
        """horizon(): orizzonte radio in gradi; station(): (lat, lon) oppure None."""
        super().__init__(parent)
        self.tracker = tracker
        self.horizon = horizon
        self.station = station
        self.land = _load_land()
        self.sub = None
        self.track = None
        self.track_at = 0.0
        self.night = None
        self.night_at = 0.0
        self.visible = False
        self.setMinimumSize(300, 130)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("Posizione dell'ISS calcolata dal TLE. Clic per aprire isstracker.pl nel browser"))

    # ------------------------------------------------------------ dati
    def refresh(self, iss_el=None):
        """Da chiamare una volta al secondo. iss_el: elevazione attuale vista dalla stazione (o None)."""
        now = time.time()
        if not getattr(self.tracker, "sat", None):
            self.sub = None
            self.update()
            return
        self.sub = self.tracker.subpoint(now)
        self.visible = iss_el is not None and iss_el > self.horizon()
        if self.track is None or now - self.track_at >= TRACK_EVERY_S:
            self.track = self.tracker.ground_track(now)
            self.track_at = now
        if self.night is None or now - self.night_at >= NIGHT_EVERY_S:
            self.night = self._night_image(now)
            self.night_at = now
        self.update()

    def reset_track(self):
        """Nuovo TLE o nuova stazione: ricalcola subito traccia e cerchio."""
        self.track = None

    @staticmethod
    def _night_image(unix):
        dec, lon_s = subsolar(unix)
        lats = np.linspace(LAT_TOP, LAT_BOTTOM, 76)
        lons = np.linspace(-180.0, 180.0, 181)
        la = np.radians(lats)[:, None]
        dl = np.radians(lons[None, :] - lon_s)
        d = math.radians(dec)
        cosz = np.sin(la) * math.sin(d) + np.cos(la) * math.cos(d) * np.cos(dl)
        alpha = (np.clip((0.10 - cosz) / 0.20, 0.0, 1.0) * 120).astype(np.uint8)   # crepuscolo sfumato
        rgba = np.zeros(alpha.shape + (4,), np.uint8)
        rgba[..., 2] = 20                     # notte blu scuro
        rgba[..., 3] = alpha
        h, w = alpha.shape
        img = QImage(rgba.tobytes(), w, h, 4 * w, QImage.Format_RGBA8888)
        return img.copy()

    # ------------------------------------------------------------ disegno
    def _map_rect(self, info_h):
        w, h = self.width(), self.height() - info_h
        aspect = 360.0 / (LAT_TOP - LAT_BOTTOM)
        if w / max(h, 1) > aspect:
            mw, mh = h * aspect, h
        else:
            mw, mh = w, w / aspect
        return QRectF((w - mw) / 2, (h - mh) / 2, mw, mh)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        small = QFont(self.font())
        small.setPointSizeF(max(7.5, small.pointSizeF() - 1))
        p.setFont(small)
        info_h = p.fontMetrics().height() + 6
        r = self._map_rect(info_h)
        sx = r.width() / 360.0
        sy = r.height() / (LAT_TOP - LAT_BOTTOM)

        def xy(lat, lon):
            return QPointF(r.left() + (lon + 180.0) * sx, r.top() + (LAT_TOP - lat) * sy)

        p.fillRect(r, OCEAN)
        p.save()
        p.setClipRect(r)
        # terre emerse (coordinate lon, -lat)
        p.save()
        p.setTransform(QTransform(sx, 0, 0, sy, r.left() + 180.0 * sx, r.top() + LAT_TOP * sy))
        pen = QPen(COAST)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(LAND)
        p.drawPath(self.land)
        p.restore()
        # reticolo ogni 30°
        p.setPen(QPen(GRID, 1))
        for lon in range(-150, 180, 30):
            p.drawLine(xy(LAT_TOP, lon), xy(LAT_BOTTOM, lon))
        for lat in (-60, -30, 0, 30, 60):
            p.drawLine(xy(lat, -180), xy(lat, 180))
        if self.night is not None:
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(r, self.night)
        # traccia a terra
        if self.track is not None:
            off, lats, lons = self.track
            now_off = time.time() - self.track_at
            past = off <= now_off
            for mask, color, style in ((past, PAST, Qt.DashLine), (~past, FUTURE, Qt.SolidLine)):
                p.setPen(QPen(color, 1.4, style))
                for seg in split_antimeridian(lats[mask], lons[mask]):
                    p.drawPolyline(QPolygonF([xy(a, b) for a, b in seg]))
        # cerchio di visibilità e ISS
        if self.sub is not None:
            lat, lon, alt, _ = self.sub
            fp = footprint(lat, lon, alt, self.horizon())
            p.setPen(QPen(FOOT_IN if self.visible else FOOT_OUT, 1.6 if self.visible else 1.0))
            p.setBrush(Qt.NoBrush)
            for seg in split_antimeridian([a for a, _ in fp], [b for _, b in fp]):
                p.drawPolyline(QPolygonF([xy(a, b) for a, b in seg]))
        st = self.station()
        if st:
            c = xy(*st)
            p.setPen(QPen(Qt.black, 1))
            p.setBrush(STATION)
            p.drawPolygon(QPolygonF([c + QPointF(0, -5), c + QPointF(4.5, 3.5), c + QPointF(-4.5, 3.5)]))
        if self.sub is not None:
            c = xy(self.sub[0], self.sub[1])
            p.setPen(QPen(Qt.white, 1.5))
            p.setBrush(ISS)
            p.drawEllipse(c, 5.5, 5.5)
            p.setPen(Qt.white)
            p.drawText(c + QPointF(8, 4), "ISS")
        p.restore()
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
        # riga informativa
        p.setPen(self.palette().windowText().color())
        if self.sub is not None:
            lat, lon, alt, v = self.sub
            text = tr("ISS {lat} {lon} · {alt:.0f} km · {v:.2f} km/s · clic: isstracker.pl",
                      lat=f"{abs(lat):.1f}°{'N' if lat >= 0 else 'S'}", lon=f"{abs(lon):.1f}°{'E' if lon >= 0 else 'W'}",
                      alt=alt, v=v)
        else:
            text = tr("TLE non disponibile")
        p.drawText(QRectF(0, self.height() - info_h, self.width(), info_h), Qt.AlignCenter, text)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            QDesktopServices.openUrl(QUrl(ISS_TRACKER_URL))
