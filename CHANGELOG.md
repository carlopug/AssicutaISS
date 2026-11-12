# AssicutaISS - registro delle versioni

Numerazione MAJOR.MINOR: la minor version si incrementa a ogni modifica al programma.
Il numero sta in `sstv_iss/__init__.py` (`__version__`) e compare nel titolo della finestra.

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
