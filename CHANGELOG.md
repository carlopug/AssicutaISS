# AssicutaISS - registro delle versioni

Numerazione MAJOR.MINOR: la minor version si incrementa a ogni modifica al programma.
Il numero sta in `sstv_iss/__init__.py` (`__version__`) e compare nel titolo della finestra.

## 1.7 - 13/11/2026
- Decoder più tollerante sui segnali deboli (dai passaggi della notte del 12-13/11, in cui tre trasmissioni
  vere erano state scartate come «falso avvio» dopo 83, 97 e 153 righe):
  - l'immagine si chiude dopo 20 righe senza sync invece di 12, così regge brevi affievolimenti;
  - avvio senza VIS con 6 sync consecutivi invece di 8;
  - riconoscimento dei sync meno severo (mediana entro ±150 Hz, almeno il 45% dei campioni vicino a 1200 Hz);
  - qualità minima dei sync per salvare: 0,15 con VIS e 0,30 senza VIS (prima 0,25 e 0,50).
  Rianalizzando le 7 registrazioni del 12-13/11 escono 11 immagini (parziali comprese); per i due passaggi
  della notte 6 invece di 2. Nessuna immagine dal solo rumore: restano il minimo di 30 righe e il controllo
  dei separatori.

## 1.6 - 12/11/2026
- AFC più robusto (dal passaggio delle 19:19 del 12/11, in cui una portante su un canale vicino aveva portato
  l'AFC al limite di +5 kHz per quasi tutto il passaggio):
  - l'AFC si muove solo quando l'audio contiene toni SSTV (quota di energia nella banda 1050-2400 Hz
    almeno 0,70) o mentre il decoder sta ricevendo un'immagine; voce e portanti non modulate lo ignorano;
  - escursione massima ridotta a ±1500 Hz e regolabile accanto alla casella AFC (nuovo campo `afc_range_hz`);
  - senza segnale SSTV l'AFC torna verso zero (costante di tempo circa 20 s);
  - riga nel registro quando l'AFC supera 1 kHz.
- Nel CSV della telemetria la nuova colonna `sstv_ratio`.
- Nuovo test che riproduce l'aggancio dell'AFC a una portante vicina.

## 1.5 - 12/11/2026
- Icona del programma (`assets/icona.ico`, `assets/icona.png`) sulla finestra e nella barra delle applicazioni
  di Windows, al posto di quella di Python.
- Schermata di avvio (`assets/splash.png`) mostrata durante il caricamento, per almeno 2 secondi, con
  versione e stato del caricamento nella fascia in basso.
- `AssicutaISS.bat` crea il collegamento `AssicutaISS.lnk` con l'icona, da copiare su desktop o barra.
- `tools/make_assets.py` rigenera icona e splash (prima versione grafica, sostituibile con immagini proprie).

## 1.4 - 12/11/2026
- Una sola soglia di elevazione massima per tabella dei passaggi e avvio automatico (campo «con el. max ≥»
  accanto ad «Avvio automatico ai passaggi»); tolta l'elevazione minima dalla maschera Stazione.
- La tabella calcola i passaggi dall'orizzonte: inizio e fine coincidono con avvio e arresto automatici,
  e il titolo mostra la soglia in uso.
- Il vecchio valore `min_el` di `stazione.json` viene usato come soglia iniziale se `config.json` non ne ha una.

## 1.3 - 12/11/2026
- Elevazione minima per l'avvio automatico (campo «se el. max ≥», predefinito 10°): i passaggi con
  elevazione massima inferiore vengono saltati, con una riga nel registro. Per quelli validi la ricezione
  parte comunque all'orizzonte, così non si perde l'inizio.
- Nella tabella dei passaggi quelli sotto la soglia sono in grigio.
- Nuovo test dell'avvio automatico.

## 1.2 - 12/11/2026
- Registro di sessione su file: `logs/AAAAMMGG_HHMMSSZ.log` (UTC), con tutto quello che compare nella finestra.
- Impostazioni complete del ricevitore e della stazione registrate all'avvio del programma e a ogni avvio
  della ricezione (con posizione dell'ISS ed epoca del TLE); ogni modifica registrata come «vecchio → nuovo».
- Durante la ricezione, una riga di stato ogni 30 s: SNR medio e massimo, Doppler, AFC, elevazione ISS.
- Accanto a ogni WAV un file `.csv` con una riga al secondo: SNR, presenza di segnale, Doppler, AFC,
  frequenza effettiva, guadagno, PPM, azimut/elevazione/distanza ISS, stato del decoder, overflow IQ.

## 1.1 - 12/11/2026
- Interfaccia, messaggi del registro e schede .txt disponibili in italiano e inglese; la lingua si sceglie
  nella maschera Stazione (campo `language` di `stazione.json`) e il programma propone di riavviarsi.
- Anche i pulsanti standard di Qt (Salva/Annulla, Sì/No) e i giorni della tabella passaggi seguono la lingua.
- File di avvio rinominato da `avvia.bat` a `AssicutaISS.bat`.
- README in inglese (`README.md`) con versione italiana in `README.it.md`.
- Nuovo test che verifica la presenza della traduzione inglese per ogni testo dell'interfaccia.

## 1.0 - 12/11/2026
Prima versione con il nome AssicutaISS.
- Ricezione diretta da RTL-SDR su 437,550 MHz, demodulazione FM e decodifica Robot36 in PNG.
- Correzione Doppler da TLE (Celestrak) e AFC sul segnale ricevuto.
- Decoder con avvio da VIS o da treno di sync, correzione slant, protezione dai falsi avvii sul rumore.
- Attesa automatica del dongle: se manca o si scollega, il ricevitore riprova ogni 3 s e riparte da solo.
- Ascolto opzionale dell'audio demodulato su un'uscita a scelta.
- Previsione dei passaggi e avvio automatico della ricezione.
- File immagine `AAAAMMGG_HHMMSSZ.png` (UTC) con scheda `.txt` per il modulo ARISS SSTV Gallery.
- Maschera «Stazione e nominativo» (dati in `stazione.json`).
- Registrazione WAV e decodifica da file WAV.
