# AssicutaISS

*an ISS SSTV Receiver for Robot36*, version 1.1 · [Leggi in italiano](README.it.md)

A Windows desktop program that receives the **Robot36** SSTV images transmitted by the International Space
Station during ARISS events (437.550 MHz FM) with an **RTL-SDR** dongle. No SDR#/SDR++ + MMSSTV + virtual
audio cable: the program drives the dongle directly, demodulates FM, decodes the image and saves it as PNG.

The interface and the image reports are available in **Italian and English**.

## Features
- Direct RTL-SDR reception, FM demodulation and Robot36 decoding, all in one program.
- **Doppler correction** computed from the ISS TLE (Celestrak) and applied in real time, plus **AFC** that
  tracks the residual error on the received signal.
- Robust decoder: starts on the VIS header or, if VIS is lost to fading, on the train of sync pulses;
  automatic slant correction; protection against false starts on noise.
- **Pass prediction** for your station and optional **automatic start/stop** at each pass.
- **Dongle hot-plug**: if the dongle is missing, busy or gets unplugged, the receiver waits and resumes on its own.
- Optional **audio monitor** on any output device (speakers, headphones, or a virtual cable to another decoder).
- Each image is saved as `YYYYMMDD_HHMMSSZ.png` (UTC) with a `.txt` report holding every field of the
  [ARISS SSTV Gallery](https://ariss-usa.org/ARISS_SSTV/submit.php) form, ready-to-paste comments
  (estimated S-meter, AOS/LOS, equipment) and the reception details.
- WAV recording of the demodulated audio and decoding of WAV files (also recordings made with SDR#/SDR++).

## Requirements
- Windows 10/11 and Python 3.11 or later.
- An RTL-SDR dongle (RTL2832U) with the **WinUSB driver installed with Zadig**, as for SDR#/SDR++.
- A 70 cm antenna. A vertical is enough for high passes; a hand-pointed Yagi is better.

## Getting started
1. Double-click **`AssicutaISS.bat`**. The first time it creates a Python environment in `.venv` inside the
   program folder and installs the dependencies; later runs only check for new ones.
   If the folder is inside Dropbox, `.venv` is marked as ignored so Dropbox does not lock its files.
2. On first launch the **Station** dialog opens: choose the language and enter callsign, name, email,
   coordinates and equipment. You can reopen it at any time with **Station and callsign...**.
   Changing the language asks to restart the program.
3. The ISS TLE is downloaded from Celestrak and refreshed every 24 hours (cached in `data/`).
4. Check the **upcoming passes** table: the highest passes (in green, above 40°) give the best images.
5. Press **Start receiving** a few minutes before AOS, or enable **Auto-start on passes** and leave the
   program open.

Close SDR#/SDR++ before receiving: the dongle can be used by only one program at a time.
If it is busy, AssicutaISS waits until it is free.

## Configuration files
- `stazione.json`: station data (language, callsign, name, email, ARISS campaign, coordinates, continent,
  minimum pass elevation, receiver, antenna, preamp, cable). Edited from the Station dialog.
  It is not in the repository because it holds personal data; `stazione.example.json` shows the format.
- `config.json`: receiver settings (frequency, gain, PPM, Doppler/AFC, audio monitor...), saved automatically.

## How it works
- The dongle is tuned 250 kHz below the frequency (avoiding the DC spike) and is **never retuned**.
- The **Doppler** shift (±10 kHz) is computed from the TLE and applied with a phase-continuous software
  oscillator, so there are no frequency jumps.
- The **AFC** measures the residual error from the received FM signal and corrects it (±5 kHz limit). It is
  active only when the SNR is above the "Squelch AFC" threshold, and compensates TLE and dongle crystal errors.
  If the AFC always settles on a similar value, set the dongle PPM to about AFC / 437.55.
- A start without VIS requires 8 regular 1200 Hz sync pulses with valid line separators and some signal;
  images with too many lines lacking sync are discarded.
- The S-meter in the report is an **estimate**: noise floor from the receiver noise figure plus the
  measured SNR. It is not a calibrated measurement.

## Tips
- Gain: a fixed value around 40 dB keeps SNR and S-meter comparable between passes. If the waterfall fills
  with horizontal lines, lower it (30-36 dB).
- The yellow band on the waterfall is the channel. With Doppler and AFC on, the signal should stay centred
  on the dashed line.
- Enable **Record WAV**: a recording lets you decode an image again with **Decode WAV file...**.
- An illustrated guide (in Italian) is in `guida.html`.

## Tests
```
.venv\Scripts\python.exe -m pytest tests -s
```
The tests encode a Robot36 image, FM-modulate it at 960 kS/s with a Doppler ramp, tuning error and noise,
and check that AFC and decoder rebuild the image. They also cover false starts on noise, the dongle
hot-plug cycle and the completeness of the English translation.

## Version history
See [CHANGELOG.md](CHANGELOG.md). The minor version is increased with every change.

## License
Released under the [MIT License](LICENSE).
