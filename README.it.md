# AssicutaISS

*an ISS SSTV Receiver for Robot36*, versione 1.3 · [Read in English](README.md)

Programma per Windows che riceve le immagini SSTV **Robot36** trasmesse dalla Stazione Spaziale durante gli
eventi ARISS (437,550 MHz FM) con un dongle **RTL-SDR**. Niente SDR#/SDR++ + MMSSTV + cavo audio virtuale:
il programma pilota direttamente il dongle, demodula l'FM, decodifica l'immagine e la salva in PNG.

Interfaccia e schede delle immagini sono disponibili in **italiano e inglese**.

> **Funziona SOLO con dongle RTL-SDR** (chip RTL2832U, per esempio RTL-SDR Blog V3/V4 e chiavette generiche
> R820T/R820T2). Altri ricevitori come Airspy, SDRplay, HackRF o FUNcube **non sono supportati**. Con uno di
> questi puoi comunque registrare l'audio demodulato con SDR#/SDR++ e decodificarlo con
> **Decodifica file WAV...**.

## Funzioni
- Ricezione diretta da RTL-SDR, demodulazione FM e decodifica Robot36 in un unico programma.
- **Correzione Doppler** calcolata dal TLE dell'ISS (Celestrak) e applicata in tempo reale, più **AFC** che
  insegue l'errore residuo sul segnale ricevuto.
- Decoder robusto: parte dall'intestazione VIS o, se il VIS va perso per un fading, dal treno di impulsi di
  sync; correzione automatica dello slant; protezione dai falsi avvii sul rumore.
- **Previsione dei passaggi** per la tua stazione e **avvio/arresto automatico** facoltativo a ogni passaggio,
  saltando quelli con elevazione massima sotto una soglia a scelta (predefinita 10°).
- **Attesa del dongle**: se manca, è occupato o viene scollegato, il ricevitore aspetta e riparte da solo.
- **Ascolto** facoltativo su qualsiasi uscita audio (casse, cuffie o cavo virtuale verso un altro decoder).
- Ogni immagine è salvata come `AAAAMMGG_HHMMSSZ.png` (UTC) con una scheda `.txt` che contiene tutti i campi
  del modulo [ARISS SSTV Gallery](https://ariss-usa.org/ARISS_SSTV/submit.php), i commenti pronti da incollare
  (S-meter stimato, AOS/LOS, attrezzatura) e i dettagli della ricezione.
- Registrazione WAV dell'audio demodulato e decodifica di file WAV (anche registrati con SDR#/SDR++).
  Accanto a ogni registrazione un `.csv` con la telemetria al secondo (SNR, Doppler, AFC, elevazione ISS,
  stato del decoder).
- Registro di sessione in `logs/`, con le impostazioni complete a ogni avvio della ricezione e ogni modifica.

## Requisiti
- Windows 10/11 e Python 3.11 o successivo.
- Un dongle RTL-SDR (RTL2832U), **l'unico ricevitore supportato**, con il **driver WinUSB installato con
  Zadig**, come per SDR#/SDR++.
- Un'antenna per i 70 cm. Una verticale basta per i passaggi alti; una Yagi puntata a mano va meglio.

## Avvio
1. Doppio clic su **`AssicutaISS.bat`**. La prima volta crea l'ambiente Python in `.venv` dentro la cartella
   del programma e installa le dipendenze; le volte successive controlla solo se ce ne sono di nuove.
   Se la cartella è dentro Dropbox, `.venv` viene esclusa dalla sincronizzazione, che altrimenti ne blocca i file.
2. Al primo avvio si apre la maschera **Stazione**: scegli la lingua e inserisci nominativo, nome, email,
   coordinate e attrezzatura. Puoi riaprirla quando vuoi con **Stazione e nominativo...**.
   Se cambi lingua, il programma propone di riavviarsi.
3. Il TLE dell'ISS viene scaricato da Celestrak e aggiornato ogni 24 ore (resta in cache in `data/`).
4. Controlla la tabella dei **prossimi passaggi**: quelli più alti (in verde, oltre 40°) danno le immagini migliori.
5. Premi **Avvia ricezione** qualche minuto prima dell'AOS, oppure attiva **Avvio automatico ai passaggi** e
   lascia il programma aperto.

Chiudi SDR#/SDR++ prima di ricevere: il dongle può essere usato da un solo programma alla volta.
Se è occupato, AssicutaISS aspetta che si liberi.

## File di configurazione
- `stazione.json`: dati della stazione (lingua, nominativo, nome, email, campagna ARISS, coordinate, continente,
  elevazione minima dei passaggi, ricevitore, antenna, preamplificatore, cavo). Si modifica dalla maschera
  Stazione. Non è nel repository perché contiene dati personali: `stazione.example.json` mostra il formato.
- `config.json`: impostazioni del ricevitore (frequenza, guadagno, PPM, Doppler/AFC, ascolto...), salvate da sole.

## Come funziona
- Il dongle è sintonizzato 250 kHz sotto la frequenza (così si evita lo spike DC) e **non viene mai risintonizzato**.
- Lo spostamento **Doppler** (±10 kHz) è calcolato dal TLE e applicato con un oscillatore software a fase
  continua, quindi senza salti di frequenza.
- L'**AFC** misura l'errore residuo dal segnale FM ricevuto e lo corregge (limite ±5 kHz). È attivo solo quando
  l'SNR supera la soglia «Squelch AFC» e compensa gli errori del TLE e del quarzo del dongle.
  Se l'AFC si assesta sempre su un valore simile, imposta il PPM del dongle a circa AFC / 437,55.
- L'avvio senza VIS richiede 8 sync regolari a 1200 Hz con i separatori di riga corretti e un minimo di
  segnale; le immagini con troppe righe prive di sync vengono scartate.
- L'S-meter della scheda è una **stima**: rumore di fondo ricavato dalla cifra di rumore del ricevitore più
  l'SNR misurato. Non è una misura tarata.

## Consigli
- Guadagno: un valore fisso intorno a 40 dB rende SNR e S-meter confrontabili tra un passaggio e l'altro.
  Se il waterfall si riempie di righe orizzontali, abbassalo (30-36 dB).
- La banda gialla sul waterfall è il canale. Con Doppler e AFC attivi il segnale deve restare centrato sulla
  linea tratteggiata.
- Attiva **Registra WAV**: con la registrazione puoi decodificare di nuovo un'immagine con
  **Decodifica file WAV...**.
- Una guida illustrata in italiano è in `guida.html`.

## Test
```
.venv\Scripts\python.exe -m pytest tests -s
```
I test codificano un'immagine Robot36, la modulano in FM a 960 kS/s con rampa Doppler, errore di sintonia e
rumore, e verificano che AFC e decoder ricostruiscano l'immagine. Coprono anche i falsi avvii sul rumore, il
ciclo di scollegamento del dongle e la completezza della traduzione inglese.

## Versioni
Vedi [CHANGELOG.md](CHANGELOG.md). La minor version si incrementa a ogni modifica.

## Licenza
Distribuito con [licenza MIT](LICENSE).
