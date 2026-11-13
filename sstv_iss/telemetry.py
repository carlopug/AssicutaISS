"""Registro di sessione su file, riepilogo delle impostazioni e telemetria al secondo accanto ai WAV."""
import csv
import os
import threading
import time

from .config import APP_DIR
from .i18n import tr
from .report import maidenhead

LOG_DIR = os.path.join(APP_DIR, "logs")


class SessionLog:
    """Un file per ogni avvio del programma: logs/AAAAMMGG_HHMMSSZ.log, righe con orario UTC."""

    def __init__(self):
        self.path = None
        self._f = None
        self._lock = threading.Lock()
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            self.path = os.path.join(LOG_DIR, time.strftime("%Y%m%d_%H%M%SZ.log", time.gmtime()))
            self._f = open(self.path, "a", encoding="utf-8")
        except OSError:
            self._f = None

    def write(self, text):
        if not self._f:
            return
        stamp = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
        with self._lock:
            for i, line in enumerate(str(text).splitlines() or [""]):
                self._f.write(f"{stamp}  {line}\n" if i == 0 else f"{' ' * len(stamp)}  {line}\n")
            self._f.flush()

    def close(self):
        if self._f:
            self._f.close()
            self._f = None


def _onoff(v):
    return tr("attivo") if v else tr("disattivo")


def settings_items(cfg):
    """Impostazioni del ricevitore e della stazione come lista (nome, valore) da registrare e confrontare."""
    gain = tr("automatico") if cfg.gain_db < 0 else f"{cfg.gain_db:g} dB"
    mon = _onoff(cfg.monitor)
    if cfg.monitor:
        mon += f", {cfg.monitor_device or tr('uscita predefinita')}, volume {cfg.monitor_volume}%"
        if cfg.monitor_mute:
            mon += ", " + tr("silenziato senza segnale")
    preamp = f"{cfg.preamp} ({cfg.preamp_gain_db:g} dB)" if cfg.preamp else tr("nessuno")
    return [
        (tr("Frequenza"), f"{cfg.freq_hz / 1e6:.4f} MHz"),
        (tr("Guadagno"), gain),
        ("PPM", str(cfg.ppm)),
        ("Offset", f"{cfg.manual_offset_hz:+.0f} Hz"),
        ("Doppler", _onoff(cfg.doppler)),
        ("AFC", tr("{s}, limite ±{l:.0f} Hz", s=_onoff(cfg.afc), l=cfg.afc_range_hz)),
        ("Squelch AFC", f"{cfg.squelch_db:g} dB"),
        ("Bias-T", _onoff(cfg.bias_tee)),
        (tr("Registra WAV"), _onoff(cfg.record_wav)),
        (tr("Avvio automatico ai passaggi"), _onoff(cfg.auto_pass)),
        (tr("Elevazione massima minima dei passaggi (tabella e avvio automatico)"), f"{cfg.auto_min_el:g}°"),
        (tr("Ascolto"), mon),
        (tr("De-enfasi"), f"{cfg.deemph_us:g} us"),
        (tr("Offset di sintonia del dongle"), f"{cfg.if_offset_hz / 1000:g} kHz"),
        (tr("Nominativo"), cfg.callsign or "SWL"),
        ("Locator", maidenhead(cfg.lat, cfg.lon) if cfg.station_set else tr("(non impostato)")),
        (tr("Altitudine s.l.m."), f"{cfg.alt_m:.0f} m"),
        (tr("Orizzonte radio"), tr("{h} (automatico dalla quota)", h=f"{cfg.horizon:.1f}°") if cfg.horizon_deg is None
         else tr("{h} (impostato a mano)", h=f"{cfg.horizon:.1f}°")),
        ("Antenna", f"{cfg.antenna or 'n/a'} ({cfg.antenna_gain_dbi:g} dBi)"),
        (tr("Preamplificatore"), preamp),
        (tr("Cavo"), tr("{c} (perdita {l:g} dB)", c=cfg.cable or "n/a", l=cfg.cable_loss_db)),
        (tr("Ricevitore"), f"{cfg.receiver}, NF {cfg.rx_nf_db:g} dB"),
        (tr("Lingua"), cfg.language),
    ]


def settings_text(cfg):
    items = settings_items(cfg)
    w = max(len(k) for k, _ in items)
    return "\n".join(f"  {k:<{w}} : {v}" for k, v in items)


def settings_diff(old, new):
    """Righe 'nome: vecchio → nuovo' fra due dict di impostazioni."""
    return [f"{k}: {old.get(k, '?')} → {v}" for k, v in new.items() if old.get(k) != v]


CSV_FIELDS = ["utc", "snr_db_mean", "snr_db_max", "signal", "sstv_ratio", "doppler_hz", "afc_hz", "manual_offset_hz",
              "tuned_mhz", "gain", "ppm", "iss_az_deg", "iss_el_deg", "iss_range_km", "decoder", "decoder_line",
              "iq_overflows"]


class TelemetryCsv:
    """Una riga al secondo accanto al WAV (stesso nome, estensione .csv)."""

    def __init__(self, wav_path):
        self.path = os.path.splitext(wav_path)[0] + ".csv"
        self._f = open(self.path, "w", newline="", encoding="utf-8")
        self._w = csv.writer(self._f)
        self._w.writerow(CSV_FIELDS)

    def row(self, values):
        self._w.writerow([values.get(k, "") for k in CSV_FIELDS])
        self._f.flush()

    def close(self):
        self._f.close()
