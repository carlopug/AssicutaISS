"""Scheda di ricezione (.txt accanto al PNG) con i dati per il modulo ARISS SSTV Gallery."""
import math
import os
from datetime import datetime, timezone

from . import APP_NAME, __version__
from .i18n import tr

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


def write_report(png_path, info, cfg, tracker=None, snr_stats=None, source=None):
    """Scrive <png>.txt. info: evento 'image' del decoder; snr_stats: (mediana dB, massimo dB) o None."""
    start = info.get("start_time")
    end = info.get("end_time")
    t_start = utc(start) if start else None
    grid = maidenhead(cfg.lat, cfg.lon) if cfg.station_set else tr("(non impostato)")

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
    rows = []           # (etichetta, valore) di una sezione: allineati quando la sezione si chiude

    def kv(label, value):
        rows.append((tr(label), value))

    def flush():
        w = max((len(k) for k, _ in rows), default=0)
        for k, v in rows:
            add(f"{k:<{w}} : {v}")
        rows.clear()

    na = tr("(da compilare)")
    add(tr("SCHEDA DI RICEZIONE SSTV - ISS"))
    add("=" * 60)
    kv("Immagine", os.path.basename(png_path))
    kv("Origine", source or tr("ricezione diretta"))
    kv("Software", f"{APP_NAME} v. {__version__}")
    flush()
    add("")
    add(tr("--- Modulo ARISS SSTV Gallery ({u}) ---", u=ARISS_URL))
    # le etichette di questa sezione restano quelle (inglesi) del modulo ARISS
    rows.append(("Name", cfg.operator_name or na))
    if cfg.category:
        rows.append(("Category", cfg.category))
    rows.append(("Callsign", cfg.callsign or "SWL"))
    rows.append(("Email", cfg.email or na))
    rows.append(("General location", cfg.continent))
    rows.append(("Detailed location", grid))
    rows.append(("SSTV campaign", cfg.campaign))
    if t_start:
        rows.append(("Date captured", f"{t_start:%Y} / {t_start.month} / {t_start.day}   " + tr("(anno / mese / giorno)")))
        rows.append(("UTC time captured", f"{t_start:%H} : {t_start:%M}"))
    rows.append(("Image file", os.path.basename(png_path)))
    flush()
    add(tr("Comments (da incollare):"))
    parts = []
    if s_med:
        parts.append(f"Signal {s_med} (peak {s_max}, estimated from SNR)")
    if pas:
        parts.append(f"AOS {hm(pas['aos'])}Z, LOS {hm(pas['los'])}Z, max el {pas['max_el']:.0f} deg")
    ant = cfg.antenna or "n/a"
    parts.append(f"Antenna: {ant}, {cfg.antenna_gain_dbi:g} dBi")
    parts.append(f"Preamp: {cfg.preamp + ', ' + format(cfg.preamp_gain_db, 'g') + ' dB' if cfg.preamp else 'none'}")
    parts.append(f"Cable loss: {cfg.cable_loss_db:g} dB" + (f" ({cfg.cable})" if cfg.cable else ""))
    parts.append(f"RX: {cfg.receiver}, FM sensitivity {cfg.rx_sensitivity}")
    parts.append(f"Grid {grid}")
    if cfg.station_notes:
        parts.append(cfg.station_notes)
    add("  " + ". ".join(parts) + ".")
    add("")

    add(tr("--- Ricezione ---"))
    if t_start:
        kv("Inizio immagine", tr("{d} UTC  ({l} ora locale)", d=f"{t_start:%d/%m/%Y %H:%M:%S}",
                                 l=f"{datetime.fromtimestamp(start):%H:%M:%S}"))
    if end:
        kv("Fine immagine", f"{utc(end):%H:%M:%S} UTC")
    kv("Modo", tr("Robot36, avvio da VIS") if info.get("mode") == "vis"
       else tr("Robot36, avvio da treno di sync (VIS perso)"))
    kv("Righe decodificate", f"{info.get('lines', '?')}/240" + (tr("  (immagine parziale)") if info.get("partial") else ""))
    if info.get("sync_quality") is not None:
        kv("Righe con sync", f"{info['sync_quality'] * 100:.0f}%")
    if info.get("slant_ppm") is not None:
        kv("Errore di clock", tr("{p:+.0f} ppm (correzione slant)", p=info["slant_ppm"]))
    kv("Frequenza", f"{cfg.freq_hz / 1e6:.4f} MHz")
    if snr_stats is not None:
        kv("SNR in canale", tr("mediana {a:.1f} dB, massimo {b:.1f} dB", a=snr_med, b=snr_max))
        kv("Livello stimato", tr("{a:.0f} dBm (picco {b:.0f} dBm) all'ingresso del ricevitore", a=dbm_med, b=dbm_max))
        kv("S-meter stimato", tr("{a} (picco {b})  [rumore di fondo {f:.0f} dBm con NF {nf:g} dB; stima, non misura tarata]",
                                 a=s_med, b=s_max, f=noise_floor_dbm(cfg.rx_nf_db), nf=cfg.rx_nf_db))
    else:
        kv("Segnale", tr("non disponibile (decodifica da file)"))
    if look:
        kv("ISS all'inizio", tr("az {az:.0f} deg, el {el:.0f} deg, distanza {d:.0f} km, Doppler {dop:+.0f} Hz",
                                az=look[0], el=look[1], d=look[2], dop=dop))
    if pas:
        kv("Passaggio", tr("AOS {a}Z, culmine {t}Z, LOS {l}Z, elevazione max {el:.0f} deg",
                           a=f"{pas['aos']:%H:%M:%S}", t=f"{pas['tca']:%H:%M:%S}", l=f"{pas['los']:%H:%M:%S}",
                           el=pas["max_el"]))
    flush()
    add("")

    add(tr("--- Stazione ---"))
    kv("Nominativo", cfg.callsign or "SWL")
    kv("Posizione", tr("{lat:.5f}, {lon:.5f}, {alt:.0f} m s.l.m.  ({g})", lat=cfg.lat, lon=cfg.lon, alt=cfg.alt_m, g=grid))
    kv("Ricevitore", cfg.receiver)
    kv("Antenna", f"{ant} ({cfg.antenna_gain_dbi:g} dBi)")
    kv("Preamplificatore", (cfg.preamp or tr("nessuno")) + (f" ({cfg.preamp_gain_db:g} dB)" if cfg.preamp else ""))
    kv("Cavo", tr("{c} (perdita {l:g} dB)", c=cfg.cable or "n/a", l=cfg.cable_loss_db))
    gain = "auto" if cfg.gain_db < 0 else f"{cfg.gain_db:g} dB"
    kv("Guadagno RTL-SDR", f"{gain}, PPM {cfg.ppm}")
    if cfg.station_notes:
        kv("Note", cfg.station_notes)
    flush()
    add("")
    add(tr("Nota: l'immagine è quella decodificata, senza testo aggiunto, come richiesto da ARISS."))
    txt = os.path.splitext(png_path)[0] + ".txt"
    with open(txt, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return txt
