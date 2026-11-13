"""Tracciamento ISS: TLE da Celestrak, Doppler, posizione az/el, previsione dei passaggi."""
import math
import os
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

from . import __version__
from .i18n import tr
from skyfield.api import EarthSatellite, load, wgs84

C = 299_792_458.0
TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=tle"
TLE_MAX_AGE_S = 24 * 3600
EARTH_R_M = 6_371_000.0


def radio_horizon(alt_m):
    """Orizzonte della stazione in gradi (negativo): abbassamento dell'orizzonte dovuto alla quota.

    Da una quota h l'orizzonte del mare sta acos(R / (R + h)) sotto l'orizzonte geometrico
    (586 m -> -0,8°). La rifrazione atmosferica dà di solito un altro mezzo grado di margine, non contato.
    """
    h = max(0.0, float(alt_m))
    return -round(math.degrees(math.acos(EARTH_R_M / (EARTH_R_M + h))), 1)


def fmt_el(el):
    """Elevazione per la GUI: un decimale vicino all'orizzonte (dove -0,4° e 0,4° sono diversi), intero altrove."""
    return f"{el:.1f}°" if abs(el) < 10 else f"{el:.0f}°"


class IssTracker:
    def __init__(self, cache_dir):
        self.cache_path = os.path.join(cache_dir, "iss_tle.txt")
        self.horizon = 0.0
        self.ts = load.timescale()
        self.sat = None
        self.tle_epoch = None
        self.topos = None
        self._lock = threading.Lock()

    # --------------------------------------------------------------- TLE
    def load_tle(self, force=False):
        """Carica il TLE (dalla cache se recente, altrimenti da Celestrak). Restituisce un messaggio di stato."""
        msg = ""
        fresh = os.path.exists(self.cache_path) and time.time() - os.path.getmtime(self.cache_path) < TLE_MAX_AGE_S
        if force or not fresh:
            try:
                req = urllib.request.Request(TLE_URL, headers={"User-Agent": f"AssicutaISS/{__version__}"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    text = r.read().decode("ascii", "replace")
                if "1 25544" not in text:
                    raise ValueError("risposta TLE non valida")
                os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
                with open(self.cache_path, "w", encoding="ascii") as f:
                    f.write(text.strip() + "\n")
                msg = tr("TLE ISS aggiornato da Celestrak")
            except Exception as e:  # rete assente: si usa la cache
                msg = tr("Download TLE fallito ({e}); uso la copia locale", e=e)
        if not os.path.exists(self.cache_path):
            return msg + tr(" - nessun TLE disponibile: Doppler disattivato")
        with open(self.cache_path, encoding="ascii") as f:
            lines = [ln.rstrip() for ln in f if ln.strip()]
        l1 = next(ln for ln in lines if ln.startswith("1 "))
        l2 = next(ln for ln in lines if ln.startswith("2 "))
        sat = EarthSatellite(l1, l2, "ISS (ZARYA)", self.ts)
        with self._lock:
            self.sat = sat
            self.tle_epoch = sat.epoch.utc_datetime()
        age = (datetime.now(timezone.utc) - self.tle_epoch).total_seconds() / 86400
        return (msg + "; " if msg else "") + tr("TLE epoca {d} UTC ({age:.1f} giorni)", d=f"{self.tle_epoch:%d/%m %H:%M}", age=age)

    def set_station(self, lat, lon, alt_m, horizon_deg=0.0):
        """horizon_deg: orizzonte usato per passaggi e avvio automatico (vedi radio_horizon)."""
        with self._lock:
            self.topos = wgs84.latlon(lat, lon, elevation_m=alt_m)
            self.horizon = float(horizon_deg)

    @property
    def ready(self):
        return self.sat is not None and self.topos is not None

    # ------------------------------------------------------------ calcoli
    def _t(self, unix=None):
        return self.ts.from_datetime(datetime.fromtimestamp(time.time() if unix is None else unix, timezone.utc))

    def look(self, unix=None):
        """(az°, el°, distanza km, range-rate km/s) oppure None."""
        with self._lock:
            sat, topos = self.sat, self.topos
        if sat is None or topos is None:
            return None
        topo = (sat - topos).at(self._t(unix))
        alt, az, dist = topo.altaz()
        _, _, _, _, _, rr = topo.frame_latlon_and_rates(topos)
        return az.degrees, alt.degrees, dist.km, rr.km_per_s

    def doppler(self, f0, unix=None):
        """(spostamento Doppler Hz, variazione Hz/s) all'istante dato."""
        if not self.ready:
            return 0.0, 0.0
        t = time.time() if unix is None else unix
        r0 = self.look(t)[3]
        r1 = self.look(t + 1.0)[3]
        d0 = -f0 * r0 * 1000.0 / C
        d1 = -f0 * r1 * 1000.0 / C
        return d0, d1 - d0

    def pass_at(self, unix):
        """Passaggio (sopra l'orizzonte della stazione) che contiene l'istante `unix`: dict aos/tca/los (datetime UTC), max_el."""
        with self._lock:
            sat, topos = self.sat, self.topos
        if sat is None or topos is None:
            return None
        t = datetime.fromtimestamp(unix, timezone.utc)
        t0 = self.ts.from_datetime(t - timedelta(minutes=20))
        t1 = self.ts.from_datetime(t + timedelta(minutes=20))
        times, events = sat.find_events(topos, t0, t1, altitude_degrees=self.horizon)
        aos = los = tca = None
        max_el = None
        for tt, e in zip(times, events):
            dt = tt.utc_datetime()
            if e == 0 and dt <= t:
                aos, tca, max_el = dt, None, None
            elif e == 1 and aos is not None:
                tca, max_el = dt, (sat - topos).at(tt).altaz()[0].degrees
            elif e == 2 and dt >= t and aos is not None:
                los = dt
                break
        if aos is None or los is None or tca is None:
            return None
        return {"aos": aos, "tca": tca, "los": los, "max_el": max_el}

    def pass_around(self, unix):
        """Passaggio in corso o che inizia entro 30 minuti dall'istante `unix` (sopra l'orizzonte della stazione).

        Restituisce dict aos/tca/los (datetime UTC) e max_el, oppure None.
        """
        with self._lock:
            sat, topos = self.sat, self.topos
        if sat is None or topos is None:
            return None
        t = datetime.fromtimestamp(unix, timezone.utc)
        t0 = self.ts.from_datetime(t - timedelta(minutes=20))
        t1 = self.ts.from_datetime(t + timedelta(minutes=30))
        times, events = sat.find_events(topos, t0, t1, altitude_degrees=self.horizon)
        cur = {}
        for tt, e in zip(times, events):
            dt = tt.utc_datetime()
            if e == 0:
                cur = {"aos": dt}
            elif e == 1 and "aos" in cur:
                cur["tca"] = dt
                cur["max_el"] = (sat - topos).at(tt).altaz()[0].degrees
            elif e == 2 and "tca" in cur:
                cur["los"] = dt
                if dt > t:
                    return cur
                cur = {}
        return None

    def passes(self, hours=48, min_el=-90.0):
        """Passaggi sopra l'orizzonte della stazione (self.horizon) con elevazione massima >= min_el.

        dict(aos, tca, los: datetime locali, max_el: gradi); aos/los coincidono con avvio/arresto automatici.
        """
        with self._lock:
            sat, topos = self.sat, self.topos
        if sat is None or topos is None:
            return []
        now = datetime.now(timezone.utc)
        t0 = self.ts.from_datetime(now - timedelta(minutes=15))
        t1 = self.ts.from_datetime(now + timedelta(hours=hours))
        times, events = sat.find_events(topos, t0, t1, altitude_degrees=self.horizon)
        out, cur = [], {}
        for t, e in zip(times, events):
            dt = t.utc_datetime().astimezone()
            if e == 0:
                cur = {"aos": dt}
            elif e == 1:
                cur["tca"] = dt
                cur["max_el"] = (sat - topos).at(t).altaz()[0].degrees
            else:
                cur["los"] = dt
                if "aos" in cur and "tca" in cur:
                    out.append(cur)
                cur = {}
        return [p for p in out if p["los"] > now.astimezone() and p["max_el"] >= min_el]

    # ------------------------------------------------------------ mappa
    def cache_age_s(self):
        """Età in secondi della copia locale del TLE (infinito se manca)."""
        try:
            return time.time() - os.path.getmtime(self.cache_path)
        except OSError:
            return float("inf")

    def _times(self, unix, offsets):
        b = datetime.fromtimestamp(unix, timezone.utc)
        sec = b.second + b.microsecond / 1e6 + np.asarray(offsets, float)
        return self.ts.utc(b.year, b.month, b.day, b.hour, b.minute, sec)

    def subpoint(self, unix=None):
        """Punto sotto l'ISS: (lat°, lon°, quota km, velocità km/s) oppure None."""
        with self._lock:
            sat = self.sat
        if sat is None:
            return None
        g = sat.at(self._t(unix))
        sp = wgs84.subpoint_of(g)
        speed = float(np.linalg.norm(g.velocity.km_per_s))
        return sp.latitude.degrees, sp.longitude.degrees, wgs84.height_of(g).km, speed

    def ground_track(self, unix=None, before_s=2700, after_s=5400, step_s=30):
        """Traccia a terra attorno all'istante dato: (offset s, lat°, lon°) come array numpy, oppure None."""
        with self._lock:
            sat = self.sat
        if sat is None:
            return None
        off = np.arange(-before_s, after_s + step_s, step_s, dtype=float)
        sp = wgs84.subpoint_of(sat.at(self._times(time.time() if unix is None else unix, off)))
        return off, sp.latitude.degrees, sp.longitude.degrees
