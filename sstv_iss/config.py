"""Impostazioni persistenti (config.json nella cartella del programma)."""
import json
import os
from dataclasses import asdict, dataclass, fields

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")


@dataclass
class Config:
    # ---- stazione (stazione.json) ----
    language: str = "it"            # lingua dell'interfaccia e delle schede: "it" o "en"
    callsign: str = ""
    operator_name: str = ""
    email: str = ""
    category: str = ""              # categoria educatore/studente del modulo ARISS ("" = nessuna)
    lat: float = 0.0
    lon: float = 0.0
    alt_m: float = 0.0
    continent: str = "Europe"
    min_el: float = 10.0
    campaign: str = "Expedition 75 - ARISS Series 35 Space Memories"
    receiver: str = "RTL-SDR (RTL2832U + R820T2)"
    rx_sensitivity: str = "approx. 0.5 uV (-113 dBm), typical"
    rx_nf_db: float = 6.0           # cifra di rumore usata per stimare dBm e S-meter
    antenna: str = ""
    antenna_gain_dbi: float = 0.0
    preamp: str = ""
    preamp_gain_db: float = 0.0
    cable: str = ""
    cable_loss_db: float = 0.0
    station_notes: str = ""
    # ---- ricevitore (config.json) ----
    freq_hz: int = 437_550_000
    gain_db: float = -1.0           # -1 = automatico
    ppm: int = 0
    bias_tee: bool = False
    doppler: bool = True
    afc: bool = True
    afc_limit_hz: float = 5000.0
    manual_offset_hz: float = 0.0
    squelch_db: float = 4.0
    deemph_us: float = 750.0
    record_wav: bool = False
    monitor: bool = False           # ascolto audio
    monitor_device: str = ""        # "" = uscita predefinita di Windows
    monitor_volume: int = 30        # 0..100
    monitor_mute: bool = False      # silenzia quando lo squelch è chiuso
    auto_pass: bool = False
    images_dir: str = os.path.join(APP_DIR, "images")
    if_offset_hz: int = 250_000

    @property
    def station_set(self):
        return not (self.lat == 0.0 and self.lon == 0.0)

    @classmethod
    def load(cls):
        cfg = cls()
        names = {f.name for f in fields(cls)}
        for path, keys in ((CONFIG_PATH, names - set(STATION_KEYS)), (STATION_PATH, set(STATION_KEYS))):
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if k in keys:
                        setattr(cfg, k, v)
            except Exception:
                pass
        return cfg

    def save(self):
        """Salva le impostazioni operative. Le coordinate stanno in stazione.json (vedi save_station)."""
        data = {k: v for k, v in asdict(self).items() if k not in STATION_KEYS}
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_station(self):
        data = {k: getattr(self, k) for k in STATION_KEYS}
        with open(STATION_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


STATION_PATH = os.path.join(APP_DIR, "stazione.json")
STATION_KEYS = ("language", "callsign", "operator_name", "email", "category", "lat", "lon", "alt_m", "continent", "min_el",
                "campaign", "receiver", "rx_sensitivity", "rx_nf_db", "antenna", "antenna_gain_dbi", "preamp",
                "preamp_gain_db", "cable", "cable_loss_db", "station_notes")
