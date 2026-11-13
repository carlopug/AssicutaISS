"""Traduzioni dell'interfaccia. L'italiano è la lingua di riferimento: tr("testo italiano", **parametri).

La lingua si sceglie nella maschera «Stazione» (campo `language` di stazione.json) e vale dal prossimo avvio.
Per aggiungere una lingua: un nuovo dizionario come EN e una voce in LANGUAGES.
"""

LANGUAGES = [("it", "Italiano"), ("en", "English")]

_lang = "it"

WEEKDAYS = {
    "it": ["lun", "mar", "mer", "gio", "ven", "sab", "dom"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}


def set_language(lang):
    global _lang
    _lang = lang if lang in dict(LANGUAGES) else "it"


def language():
    return _lang


def tr(text, **kw):
    if _lang == "en":
        text = EN.get(text, text)
    return text.format(**kw) if kw else text


def weekday(dt):
    return WEEKDAYS.get(_lang, WEEKDAYS["it"])[dt.weekday()]


EN = {
    # ---- finestra principale
    "▶  Avvia ricezione": "▶  Start receiving",
    "■  Ferma ricezione": "■  Stop receiving",
    "Frequenza": "Frequency",
    "Guadagno": "Gain",
    "Registra WAV": "Record WAV",
    "Avvio automatico ai passaggi": "Auto-start on passes",
    "Ascolto": "Monitor",
    "Riproduce l'audio demodulato per sentire il segnale": "Plays the demodulated audio so you can hear the signal",
    "Uscita predefinita di Windows": "Windows default output",
    "Silenzia senza segnale": "Mute without signal",
    "Ascolto non disponibile: {e}": "Audio monitor not available: {e}",
    "Frequenze": "Frequencies",
    "Nominale": "Nominal",
    "Sintonia effettiva": "Actual tuning",
    "Azzera AFC": "Reset AFC",
    "Segnale": "Signal",
    "TLE: caricamento...": "TLE: loading...",
    "Stazione e nominativo...": "Station and callsign...",
    "Aggiorna TLE": "Update TLE",
    "Prossimi passaggi (48 h, el. max ≥ {e:.0f}°, orizzonte {h})":
        "Upcoming passes (48 h, max el. ≥ {e:.0f}°, horizon {h})",
    "Giorno": "Day",
    "Inizio": "Start",
    "Fine": "End",
    "El. max": "Max el.",
    "Immagine in ricezione": "Image being received",
    "Decodifica file WAV...": "Decode WAV file...",
    "Apri cartella immagini": "Open images folder",
    "Immagini ricevute (doppio clic per aprire)": "Received images (double-click to open)",
    "Ascolto disattivato": "Audio monitor off",
    "Ascolto su: {o}": "Monitoring on: {o}",
    "Impossibile aprire l'uscita audio: {e}": "Cannot open the audio output: {e}",
    "Errore: {e}": "Error: {e}",
    "Stazione {call}: {lat:.4f}, {lon:.4f}, {alt:.0f} m, locator {grid} - salvata in stazione.json":
        "Station {call}: {lat:.4f}, {lon:.4f}, {alt:.0f} m, locator {grid} - saved to stazione.json",
    "Errore ricevitore": "Receiver error",
    "Decodifica registrazione audio": "Decode audio recording",
    "Decodifica di {f}...": "Decoding {f}...",
    "decodifica del file {f} (orario da {when})": "decoded from file {f} (time from {when})",
    "nome del file": "file name",
    "data del file, stima": "file date, estimated",
    "Scheda .txt non scritta: {e}": ".txt report not written: {e}",
    "Decodifica file terminata: {n} immagini": "File decoding finished: {n} images",
    "VIS Robot36 rilevato: inizio immagine": "Robot36 VIS detected: image starting",
    "VIS codice {c} (non Robot36 o parità errata) ignorato": "VIS code {c} (not Robot36 or bad parity) ignored",
    "Treno di sync Robot36 rilevato (VIS perso): inizio immagine":
        "Robot36 sync train detected (VIS missed): image starting",
    " (parziale)": " (partial)",
    "Immagine salvata{tag}: {f} [{n} righe, slant {ppm:+.0f} ppm]": "Image saved{tag}: {f} [{n} lines, slant {ppm:+.0f} ppm]",
    "Falso avvio scartato ({n} righe)": "False start discarded ({n} lines)",
    "disattivato": "off",
    "In attesa del dongle… (collegalo o chiudi SDR#/SDR++)": "Waiting for the dongle… (plug it in or close SDR#/SDR++)",
    "Segnale presente (AFC attivo)": "Signal present (AFC active)",
    "Nessun segnale": "No signal",
    "Ricevitore fermo": "Receiver stopped",
    "Imposta la posizione della stazione": "Set the station location",
    "PASSAGGIO IN CORSO - fine alle {t}, el. max {el}": "PASS IN PROGRESS - ends at {t}, max el. {el}",
    "Prossimo passaggio tra {h:d}h {m:02d}m {s:02d}s (el. max {el})":
        "Next pass in {h:d}h {m:02d}m {s:02d}s (max el. {el})",
    "Nessun passaggio nelle prossime 48 h": "No passes in the next 48 h",
    "Avvio automatico disattivato: libreria RTL-SDR non utilizzabile": "Auto-start disabled: RTL-SDR library not usable",
    "Arresto automatico: ISS sotto l'orizzonte": "Auto-stop: ISS below the horizon",
    "Lingua": "Language",
    "La nuova lingua sarà usata al prossimo avvio. Riavviare ora AssicutaISS?":
        "The new language will be used at the next start. Restart AssicutaISS now?",
    "Scostamento dalla frequenza corretta": "Offset from the corrected frequency",

    # ---- engine, decoder, tracker, sorgenti
    "Libreria RTL-SDR non disponibile: {e}": "RTL-SDR library not available: {e}",
    "Ricevitore fermato": "Receiver stopped",
    "Dongle collegato: ricezione su {f:.4f} MHz": "Dongle connected: receiving on {f:.4f} MHz",
    "In attesa del dongle RTL-SDR (collegalo o chiudi SDR#/SDR++): riprovo ogni {s:.0f} s. [{e}]":
        "Waiting for the RTL-SDR dongle (plug it in or close SDR#/SDR++): retrying every {s:.0f} s. [{e}]",
    "Errore dongle: {e}": "Dongle error: {e}",
    "nessun dato dal dongle": "no data from the dongle",
    "lettura interrotta": "reading stopped",
    "Dongle scollegato ({r}): chiudo l'immagine in corso e attendo":
        "Dongle disconnected ({r}): closing the current image and waiting",
    "In attesa del dongle RTL-SDR: riprovo ogni {s:.0f} s": "Waiting for the RTL-SDR dongle: retrying every {s:.0f} s",
    "Comando al dongle non riuscito: {e}": "Dongle command failed: {e}",
    "Registrazione audio: {p}": "Audio recording: {p}",
    "Scheda ARISS: {f}": "ARISS report: {f}",
    "TLE ISS aggiornato da Celestrak": "ISS TLE updated from Celestrak",
    "Download TLE fallito ({e}); uso la copia locale": "TLE download failed ({e}); using the local copy",
    " - nessun TLE disponibile: Doppler disattivato": " - no TLE available: Doppler disabled",
    "TLE epoca {d} UTC ({age:.1f} giorni)": "TLE epoch {d} UTC ({age:.1f} days)",
    "In attesa di segnale SSTV": "Waiting for an SSTV signal",
    "Decodifica Robot36 ({m}) - riga {n}/{h}": "Decoding Robot36 ({m}) - line {n}/{h}",

    # ---- maschera stazione
    "Stazione": "Station",
    "Operatore": "Operator",
    "Dati per il modulo ARISS SSTV Gallery. Finiscono nella scheda .txt di ogni immagine.":
        "Data for the ARISS SSTV Gallery form. They go into the .txt report of every image.",
    "es. IT9XXX, oppure SWL se non hai un nominativo": "e.g. IT9XXX, or SWL if you have no callsign",
    "nome mostrato nella galleria ARISS": "name shown in the ARISS gallery",
    "serve ad ARISS per inviare il certificato": "ARISS needs it to send the certificate",
    "Nessuna": "None",
    "Educatore - università o superiore": "Educator - undergraduate level or higher",
    "Educatore - scuola superiore o inferiore": "Educator - high school level or lower",
    "Studente - università o superiore": "Student - undergraduate level or higher",
    "Studente - scuola superiore o inferiore": "Student - high school level or lower",
    "Testo esatto della campagna nel menu del modulo ARISS": "Exact campaign text in the ARISS form menu",
    "Lingua del programma e delle schede .txt (richiede un riavvio)":
        "Language of the program and of the .txt reports (restart required)",
    "Nominativo": "Callsign",
    "Nome": "Name",
    "Categoria": "Category",
    "Campagna SSTV": "SSTV campaign",
    "Posizione": "Location",
    "Coordinate del punto di ricezione: servono per Doppler, passaggi e locator.\n"
    "Su Google Maps: clic destro sul punto e copia le coordinate.":
        "Coordinates of the receiving site: used for Doppler, passes and locator.\n"
        "On Google Maps: right-click the spot and copy the coordinates.",
    "Latitudine (N +)": "Latitude (N +)",
    "Longitudine (E +)": "Longitude (E +)",
    "Altitudine s.l.m.": "Altitude a.s.l.",
    "Locator (calcolato)": "Locator (computed)",
    "Orizzonte radio": "Radio horizon",
    "Posizione ISS": "ISS position",
    "Posizione dell'ISS calcolata dal TLE. Clic per aprire isstracker.pl nel browser":
        "ISS position computed from the TLE. Click to open isstracker.pl in the browser",
    "ISS {lat} {lon} · {alt:.0f} km · {v:.2f} km/s · clic: isstracker.pl":
        "ISS {lat} {lon} · {alt:.0f} km · {v:.2f} km/s · click: isstracker.pl",
    "TLE non disponibile": "TLE not available",
    "Aggiornamento automatico del TLE (copia locale più vecchia di 24 ore)":
        "Automatic TLE update (local copy older than 24 hours)",
    "automatico dalla quota ({h})": "automatic from altitude ({h})",
    "Elevazione sotto la quale l'ISS è considerata tramontata: vale per la tabella dei passaggi, "
    "l'avvio e l'arresto automatici. In automatico è l'abbassamento dell'orizzonte dovuto alla quota "
    "(586 m: -0,8°). Inserisci un valore a mano se montagne o palazzi coprono il cielo basso.":
        "Elevation below which the ISS is considered set: used by the pass table and by automatic start and "
        "stop. In automatic mode it is the horizon dip due to the altitude (586 m: -0.8°). Enter a value by "
        "hand if mountains or buildings block the low sky.",
    "{h} (automatico dalla quota)": "{h} (automatic from altitude)",
    "{h} (impostato a mano)": "{h} (set by hand)",
    "Continente": "Continent",
    "Attrezzatura": "Equipment",
    "Dati richiesti da ARISS per caratterizzare il segnale SSTV.":
        "Data requested by ARISS to characterize the SSTV signal.",
    "es. 0.5 uV (-113 dBm)": "e.g. 0.5 uV (-113 dBm)",
    "Usata per stimare il livello in dBm e l'S-meter dall'SNR misurato":
        "Used to estimate the dBm level and S-meter from the measured SNR",
    "es. Yagi 7 elementi 70 cm, ground-plane...": "e.g. 7-element 70 cm Yagi, ground plane...",
    "vuoto se non usi un preamplificatore": "leave empty if you use no preamp",
    "es. RG-58, 10 m": "e.g. RG-58, 10 m",
    "facoltativo, finisce nei commenti ARISS": "optional, added to the ARISS comments",
    "Ricevitore": "Receiver",
    "Sensibilità FM": "FM sensitivity",
    "Cifra di rumore (stima)": "Noise figure (estimate)",
    "Guadagno antenna": "Antenna gain",
    "Preamplificatore": "Preamplifier",
    "Guadagno preamp.": "Preamp gain",
    "Cavo": "Cable",
    "Perdita cavo stimata": "Estimated cable loss",
    "Note": "Notes",

    # ---- registro di sessione e telemetria
    "{app} avviato. Registro: {p}": "{app} started. Log file: {p}",
    "Impostazioni:": "Settings:",
    "Impostazione modificata - {c}": "Setting changed - {c}",
    "ISS: az {az:.0f}°, el {el:+.1f}°, distanza {d:.0f} km": "ISS: az {az:.0f}°, el {el:+.1f}°, range {d:.0f} km",
    "ISS: posizione non disponibile": "ISS: position not available",
    "=== Avvio ricezione (AssicutaISS v. {v}) ===": "=== Reception started (AssicutaISS v. {v}) ===",
    "Programma chiuso": "Program closed",
    "Telemetria al secondo: {p}": "Per-second telemetry: {p}",
    ", ISS el {el:.1f}°": ", ISS el {el:.1f}°",
    "Stato: SNR {m:.1f} dB (max {x:.1f}), Doppler {d:+.0f} Hz, AFC {a:+.0f} Hz{el}":
        "Status: SNR {m:.1f} dB (max {x:.1f}), Doppler {d:+.0f} Hz, AFC {a:+.0f} Hz{el}",
    "attivo": "on",
    "disattivo": "off",
    "automatico": "auto",
    "uscita predefinita": "default output",
    "silenziato senza segnale": "muted without signal",
    "{s}, limite ±{l:.0f} Hz": "{s}, limit ±{l:.0f} Hz",
    "De-enfasi": "De-emphasis",
    "Offset di sintonia del dongle": "Dongle tuning offset",

    # ---- elevazione minima per l'avvio automatico
    "Elevazione massima minima dei passaggi (tabella e avvio automatico)":
        "Minimum pass maximum elevation (table and auto-start)",
    "con el. max ≥": "with max el. ≥",
    "Soglia unica: la tabella mostra e l'avvio automatico riceve solo i passaggi con elevazione massima "
    "almeno pari a questo valore":
        "Single threshold: the table shows and auto-start receives only passes whose maximum elevation "
        "is at least this value",
    "Avvio automatico: passaggio saltato, el. max {e} sotto la soglia di {s:.0f}°":
        "Auto-start: pass skipped, max el. {e} below the {s:.0f}° threshold",
    "Avvio automatico: ISS in arrivo (el. max {e})": "Auto-start: ISS approaching (max el. {e})",

    # ---- schermata di avvio
    "Caricamento delle librerie...": "Loading libraries...",
    "Preparazione dell'interfaccia...": "Preparing the interface...",
    "Pronto": "Ready",

    # ---- AFC
    "AFC spostato di {a:+.0f} Hz: verificare PPM o disturbi vicini alla frequenza":
        "AFC moved by {a:+.0f} Hz: check the PPM or interference near the frequency",
    "Escursione massima dell'AFC attorno alla frequenza prevista. Con PPM calibrato bastano 1000-1500 Hz":
        "Maximum AFC range around the predicted frequency. With a calibrated PPM 1000-1500 Hz is enough",

    # ---- scheda .txt
    "(non impostato)": "(not set)",
    "(da compilare)": "(to be filled in)",
    "SCHEDA DI RICEZIONE SSTV - ISS": "ISS SSTV RECEPTION REPORT",
    "Immagine": "Image",
    "Origine": "Source",
    "Software": "Software",
    "ricezione diretta": "live reception",
    "--- Modulo ARISS SSTV Gallery ({u}) ---": "--- ARISS SSTV Gallery form ({u}) ---",
    "(anno / mese / giorno)": "(year / month / day)",
    "Comments (da incollare):": "Comments (paste as is):",
    "--- Ricezione ---": "--- Reception ---",
    "Inizio immagine": "Image start",
    "{d} UTC  ({l} ora locale)": "{d} UTC  ({l} local time)",
    "Fine immagine": "Image end",
    "Modo": "Mode",
    "Robot36, avvio da VIS": "Robot36, started on VIS",
    "Robot36, avvio da treno di sync (VIS perso)": "Robot36, started on sync train (VIS missed)",
    "Righe decodificate": "Decoded lines",
    "  (immagine parziale)": "  (partial image)",
    "Righe con sync": "Lines with sync",
    "Errore di clock": "Clock error",
    "{p:+.0f} ppm (correzione slant)": "{p:+.0f} ppm (slant correction)",
    "SNR in canale": "In-channel SNR",
    "mediana {a:.1f} dB, massimo {b:.1f} dB": "median {a:.1f} dB, peak {b:.1f} dB",
    "Livello stimato": "Estimated level",
    "{a:.0f} dBm (picco {b:.0f} dBm) all'ingresso del ricevitore": "{a:.0f} dBm (peak {b:.0f} dBm) at the receiver input",
    "S-meter stimato": "Estimated S-meter",
    "{a} (picco {b})  [rumore di fondo {f:.0f} dBm con NF {nf:g} dB; stima, non misura tarata]":
        "{a} (peak {b})  [noise floor {f:.0f} dBm with NF {nf:g} dB; estimate, not a calibrated measurement]",
    "non disponibile (decodifica da file)": "not available (decoded from file)",
    "ISS all'inizio": "ISS at start",
    "az {az:.0f} deg, el {el:.0f} deg, distanza {d:.0f} km, Doppler {dop:+.0f} Hz":
        "az {az:.0f} deg, el {el:.0f} deg, range {d:.0f} km, Doppler {dop:+.0f} Hz",
    "Passaggio": "Pass",
    "AOS {a}Z, culmine {t}Z, LOS {l}Z, elevazione max {el:.0f} deg":
        "AOS {a}Z, culmination {t}Z, LOS {l}Z, max elevation {el:.0f} deg",
    "--- Stazione ---": "--- Station ---",
    "{lat:.5f}, {lon:.5f}, {alt:.0f} m s.l.m.  ({g})": "{lat:.5f}, {lon:.5f}, {alt:.0f} m a.s.l.  ({g})",
    "nessuno": "none",
    "{c} (perdita {l:g} dB)": "{c} (loss {l:g} dB)",
    "Guadagno RTL-SDR": "RTL-SDR gain",
    "Nota: l'immagine è quella decodificata, senza testo aggiunto, come richiesto da ARISS.":
        "Note: the image is the decoded one, with no added text, as requested by ARISS.",
}
