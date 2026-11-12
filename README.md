# AssicutaISS

*an ISS SSTV Receiver for Robot36*, versione 1.0 (la minor version si incrementa a ogni
modifica, vedi `CHANGELOG.md`)

Utility dedicata alla ricezione delle immagini SSTV **Robot36** dell'ISS (eventi ARISS, 437.550 MHz FM)
con un dongle **RTL-SDR**: niente SDR#/SDR++ + MMSSTV + cavo audio virtuale, il programma pilota
direttamente il dongle, demodula l'FM, decodifica l'immagine e salva il PNG.

## Avvio
Doppio clic su **`avvia.bat`**.
Al primo avvio crea l'ambiente Python in `.venv` dentro la cartella del programma e installa le dipendenze
(serve Python 3.11+). La cartella `.venv` è marcata come ignorata da Dropbox, che altrimenti la sincronizzerebbe
bloccandone i file.

## File di configurazione
- `stazione.json` - dati fissi della stazione: nominativo, nome, email, campagna ARISS, coordinate, continente,
  elevazione minima dei passaggi, ricevitore, antenna, preamplificatore, cavo. Si modifica dal pulsante
  «Stazione e nominativo...» (o a mano); se manca, viene chiesto al primo avvio.
  Non è nel repository perché contiene dati personali: `stazione.example.json` mostra il formato.
- `config.json` - impostazioni operative (frequenza, guadagno, PPM, Doppler/AFC...), salvate automaticamente.

Il driver WinUSB (Zadig) deve essere già installato, come per SDR#/SDR++.
**Chiudi SDR#/SDR++ prima di avviare la ricezione**: il dongle può essere usato da un solo programma.

## Primo utilizzo
1. All'avvio inserisci **latitudine/longitudine/altitudine** della tua stazione (servono per Doppler e passaggi).
2. Il TLE dell'ISS viene scaricato da Celestrak e aggiornato ogni 24 ore (resta in cache in `data/`).
3. Controlla la tabella dei **prossimi passaggi**. I passaggi più alti (in verde, oltre 40°) danno le immagini migliori.
4. Premi **Avvia ricezione** qualche minuto prima dell'AOS, oppure attiva **Avvio automatico ai passaggi**.
   In quel caso il programma deve restare aperto.

## Come funziona
- Il dongle è sintonizzato 250 kHz sotto la frequenza (così si evita lo spike DC) e **non viene mai risintonizzato**.
- La correzione **Doppler** (±10 kHz) è calcolata dal TLE e applicata con un oscillatore software a fase continua,
  senza salti di frequenza.
- L'**AFC** misura l'errore residuo dal segnale FM ricevuto e lo corregge (limite ±5 kHz). È attivo solo quando
  l'SNR supera la soglia "Squelch AFC". Così compensa errori del TLE e del quarzo del dongle.
  Se l'AFC si assesta sempre su un valore simile, imposta il PPM del dongle (≈ AFC / 437,55).
- Il decoder riconosce l'intestazione **VIS** Robot36. Se il VIS va perso per un fading, l'immagine parte
  comunque riconoscendo la sequenza degli impulsi di sync. La pendenza (slant) viene corretta da sola.
- Le immagini sono salvate in `images/` come `AAAAMMGG_HHMMSSZ.png` (data e ora UTC di inizio immagine).
  Accanto c'è `AAAAMMGG_HHMMSSZ.txt`, la scheda con tutti i campi del modulo ARISS SSTV Gallery, i commenti
  già pronti (S-meter stimato, AOS/LOS, attrezzatura) e i dettagli della ricezione. Se l'immagine è
  incompleta lo indica la scheda.
- **Ascolto**: riproduce l'audio demodulato sull'uscita scelta (casse, cuffie o anche il cavo virtuale
  VB-Audio verso MMSSTV). Il volume parte basso perché il fruscio FM senza segnale è forte. «Silenzia senza
  segnale» tace quando l'SNR è sotto la soglia «Squelch AFC». L'ascolto non influisce sulla decodifica.
- Per evitare immagini fasulle sul rumore, l'avvio senza VIS richiede 8 sync regolari a 1200 Hz con i
  separatori di riga corretti e un minimo di segnale. Le immagini con troppe righe prive di sync vengono scartate.
- **Registra WAV** salva l'audio demodulato (48 kHz). Con **Decodifica file WAV...** puoi decodificarlo di nuovo,
  e la stessa funzione legge anche le registrazioni fatte con SDR#/SDR++.

## Consigli
- Antenna: con una verticale/ground-plane per i 70 cm si ricevono già i passaggi alti. Una Yagi puntata
  a mano va meglio.
- Guadagno: parti da "Auto". Se il waterfall è tutto acceso, abbassalo (es. 30-40 dB).
- La banda gialla sul waterfall è il canale. Con Doppler e AFC attivi il segnale deve restare centrato
  sulla linea tratteggiata.

## Test
```
.venv\Scripts\python.exe -m pytest tests -s
```
I test codificano un'immagine Robot36, la modulano in FM a 960 kS/s con rampa Doppler, errore di sintonia e
rumore, e verificano che AFC e decoder ricostruiscano l'immagine.
