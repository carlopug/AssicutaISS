"""Scheda di ricezione (.txt accanto al PNG) con i dati per il modulo ARISS SSTV Gallery."""
import math
import os
from datetime import datetime, timezone

from . import APP_NAME, __version__

S9_DBM = -93.0              # IARU, sopra 30 MHz
DB_PER_S = 6.0
CHANNEL_BW_HZ = 15_000      # banda in cui il ricevitore misura l'SNR (±7,5 kHz)
ARISS_URL = "https://ariss-usa.org/ARISS_SSTV/submit.php"


def maidenhead(lat, lon):
    """Locator Maidenhead a 6 caratteri (es. JM77mo)."""
    lon += 180.0
    lat += 90.0
    a = chr(ord("A") + int(lon // 20)) + chr(ord("A") + int(lat // 10))
    b = str(int((lon % 20) // 2)) + str(int(lat % 10))
    c = chr(ord("a") + int((lon % 2) * 12)) + chr(ord("a") + int((lat % 1) * 24))
    return a + b + c


def noise_floor_dbm(nf_db):
    return -174.0 + 10 * math.log10(CHANNEL_BW_HZ) + nf_db


def s_meter(dbm):
    """Livello in dBm -> stringa S (S1..S9, S9+NN dB)."""
    if dbm >= S9_DBM:
        over = dbm - S9_DBM
        return "S9" if over < 3 else f"S9+{int(round(over))} dB"
    s = 9 - (S9_DBM - dbm) / DB_PER_S
    return f"S{max(1, int(round(s)))}"


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc)


def png_name(start_ts):
    return utc(start_ts).strftime("%Y%m%d_%H%M%SZ.png")


def write_report(png_path, info, cfg, tracker=None, snr_stats=None, source="ricezione diretta"):
    """Scrive <png>.txt. info: evento 'image' del decoder; snr_stats: (mediana dB, massimo dB) o None."""
    start = info.get("start_time")
    end = info.get("end_time")
    t_start = utc(start) if start else None
    grid = maidenhead(cfg.lat, cfg.lon) if cfg.station_set else "(non impostato)"

    # passaggio e posizione dell'ISS
    pas = tracker.pass_at(start) if start and getattr(tracker, "ready", False) else None
    look = tracker.look(start) if start and getattr(tracker, "ready", False) else None
    dop = tracker.doppler(cfg.freq_hz, start)[0] if look else None

    # segnale
    if snr_stats is not None:
        snr_med, snr_max = snr_stats
        floor = noise_floor_dbm(cfg.rx_nf_db)
        dbm_med, dbm_max = floor + snr_med, floor + snr_max
        s_med, s_max = s_meter(dbm_med), s_meter(dbm_max)
    else:
        s_med = s_max = None

    def hm(d):
        return d.strftime("%H:%M") if d else "?"

    L = []
    add = L.append
    add("SCHEDA DI RICEZIONE SSTV - ISS")
    add("=" * 60)
    add(f"Immagine          : {os.path.basename(png_path)}")
    add(f"Origine           : {source}")
    add(f"Software          : {APP_NAME} v. {__version__}")
    add("")
    add(f"--- Modulo ARISS SSTV Gallery ({ARISS_URL}) ---")
    add(f"Name              : {cfg.operator_name or '(da compilare)'}")
    if cfg.category:
        add(f"Categoria         : {cfg.category}")
    add(f"Callsign          : {cfg.callsign or 'SWL'}")
    add(f"Email             : {cfg.email or '(da compilare)'}")
    add(f"General location  : {cfg.continent}")
    add(f"Detailed location : {grid}")
    add(f"SSTV campaign     : {cfg.campaign}")
    if t_start:
        add(f"Date captured     : {t_start:%Y} / {t_start.month} / {t_start.day}   (anno / mese / giorno)")
        add(f"UTC time captured : {t_start:%H} : {t_start:%M}")
    add(f"Image file        : {os.path.basename(png_path)}")
    add("Comments (da incollare):")
    parts = []
    if s_med:
        parts.append(f"Signal {s_med} (peak {s_max}, estimated from SNR)")
    if pas:
        parts.append(f"AOS {hm(pas['aos'])}Z, LOS {hm(pas['los'])}Z, max el {pas['max_el']:.0f} deg")
    ant = cfg.antenna or "antenna n/d"
    parts.append(f"Antenna: {ant}, {cfg.antenna_gain_dbi:g} dBi")
    parts.append(f"Preamp: {cfg.preamp + ', ' + format(cfg.preamp_gain_db, 'g') + ' dB' if cfg.preamp else 'none'}")
    parts.append(f"Cable loss: {cfg.cable_loss_db:g} dB" + (f" ({cfg.cable})" if cfg.cable else ""))
    parts.append(f"RX: {cfg.receiver}, FM sensitivity {cfg.rx_sensitivity}")
    parts.append(f"Grid {grid}")
    if cfg.station_notes:
        parts.append(cfg.station_notes)
    add("  " + ". ".join(parts) + ".")
    add("")
    add("--- Ricezione ---")
    if t_start:
        add(f"Inizio immagine   : {t_start:%d/%m/%Y %H:%M:%S} UTC  ({datetime.fromtimestamp(start):%H:%M:%S} ora locale)")
    if end:
        add(f"Fine immagine     : {utc(end):%H:%M:%S} UTC")
    add(f"Modo              : Robot36, avvio {'da VIS' if info.get('mode') == 'vis' else 'da treno di sync (VIS perso)'}")
    add(f"Righe decodificate: {info.get('lines', '?')}/240{'  (immagine parziale)' if info.get('partial') else ''}")
    if info.get("sync_quality") is not None:
        add(f"Righe con sync    : {info['sync_quality'] * 100:.0f}%")
    if info.get("slant_ppm") is not None:
        add(f"Errore di clock   : {info['slant_ppm']:+.0f} ppm (correzione slant)")
    add(f"Frequenza         : {cfg.freq_hz / 1e6:.4f} MHz")
    if snr_stats is not None:
        add(f"SNR in canale     : mediana {snr_med:.1f} dB, massimo {snr_max:.1f} dB")
        add(f"Livello stimato   : {dbm_med:.0f} dBm (picco {dbm_max:.0f} dBm) all'ingresso del ricevitore")
        add(f"S-meter stimato   : {s_med} (picco {s_max})  [rumore di fondo {noise_floor_dbm(cfg.rx_nf_db):.0f} dBm "
            f"con NF {cfg.rx_nf_db:g} dB; stima, non misura tarata]")
    else:
        add("Segnale           : non disponibile (decodifica da file)")
    if look:
        add(f"ISS all'inizio    : az {look[0]:.0f} deg, el {look[1]:.0f} deg, distanza {look[2]:.0f} km, "
            f"Doppler {dop:+.0f} Hz")
    if pas:
        add(f"Passaggio         : AOS {pas['aos']:%H:%M:%S}Z, culmine {pas['tca']:%H:%M:%S}Z, "
            f"LOS {pas['los']:%H:%M:%S}Z, elevazione max {pas['max_el']:.0f} deg")
    add("")
    add("--- Stazione ---")
    add(f"Nominativo        : {cfg.callsign or 'SWL'}")
    add(f"Posizione         : {cfg.lat:.5f}, {cfg.lon:.5f}, {cfg.alt_m:.0f} m s.l.m.  ({grid})")
    add(f"Ricevitore        : {cfg.receiver}")
    add(f"Antenna           : {ant} ({cfg.antenna_gain_dbi:g} dBi)")
    add(f"Preamplificatore  : {cfg.preamp or 'nessuno'}" + (f" ({cfg.preamp_gain_db:g} dB)" if cfg.preamp else ""))
    add(f"Cavo              : {cfg.cable or 'n/d'} (perdita {cfg.cable_loss_db:g} dB)")
    gain = "auto" if cfg.gain_db < 0 else f"{cfg.gain_db:g} dB"
    add(f"Guadagno RTL-SDR  : {gain}, PPM {cfg.ppm}")
    if cfg.station_notes:
        add(f"Note              : {cfg.station_notes}")
    add("")
    add("Nota: l'immagine è quella decodificata, senza testo aggiunto, come richiesto da ARISS.")
    txt = os.path.splitext(png_path)[0] + ".txt"
    with open(txt, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return txt
