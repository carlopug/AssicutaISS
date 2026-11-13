# AssicutaISS

*an ISS SSTV Receiver for Robot36*, version 1.9 · [Leggi in italiano](README.it.md)

A Windows desktop program that receives the **Robot36** SSTV images transmitted by the International Space
Station during ARISS events (437.550 MHz FM) with an **RTL-SDR** dongle. No SDR#/SDR++ + MMSSTV + virtual
audio cable: the program drives the dongle directly, demodulates FM, decodes the image and saves it as PNG.

The interface and the image reports are available in **Italian and English**.

> **Works ONLY with RTL-SDR dongles** (RTL2832U chipset, e.g. RTL-SDR Blog V3/V4 and generic R820T/R820T2
> sticks). Other receivers such as Airspy, SDRplay, HackRF or FUNcube are **not supported**. With one of
> those you can still record the demodulated audio with SDR#/SDR++ and decode it with **Decode WAV file...**.

## Features
- Direct RTL-SDR reception, FM demodulation and Robot36 decoding, all in one program.
- **Doppler correction** computed from the ISS TLE (Celestrak) and applied in real time, plus **AFC** that
  tracks the residual error on the received signal.
- Robust decoder: starts on the VIS header or, if VIS is lost to fading, on the train of sync pulses;
  automatic slant correction; protection against false starts on noise.
- **Pass prediction** for your station and optional **automatic start/stop** at each pass. A single threshold
  ("with max el. ≥", 10° by default) filters both the passes table and auto-start. Passes are computed above
  the station's **radio horizon**, derived from its altitude (586 m: -0.8°) or set by hand in the Station dialog,
  so grazing passes that are still receivable from a high site are not missed.
- **Live ISS map**: position, ground track, night zone and the visibility circle of your station, computed from
  the same TLE used for Doppler. Click it to open isstracker.pl in the browser.
- **Dongle hot-plug**: if the dongle is missing, busy or gets unplugged, the receiver waits and resumes on its own.
- Optional **audio monitor** on any output device (speakers, headphones, or a virtual cable to another decoder).
- Each image is saved as `YYYYMMDD_HHMMSSZ.png` (UTC) with a `.txt` report holding every field of the
  [ARISS SSTV Gallery](https://ariss-usa.org/ARISS_SSTV/submit.php) form, ready-to-paste comments
  (estimated S-meter, AOS/LOS, equipment) and the reception details.
- WAV recording of the demodulated audio and decoding of WAV files (also recordings made with SDR#/SDR++).
  Each recording gets a `.csv` with per-second telemetry (SNR, Doppler, AFC, ISS elevation, decoder state).
- Session log in `logs/`, with the full settings at every start of reception and every setting change.

## Requirements
- Windows 10/11 and Python 3.11 or later.
- An RTL-SDR dongle (RTL2832U), **the only supported receiver**, with the **WinUSB driver installed with
  Zadig**, as for SDR#/SDR++.
- A 70 cm antenna. A vertical is enough for high passes; a hand-pointed Yagi is better.

## Getting started
1. Double-click **`AssicutaISS.bat`**. The first time it creates a Python environment in `.venv` inside the
   program folder and installs the dependencies; later runs only check for new ones.
   If the folder is inside Dropbox, `.venv` is marked as ignored so Dropbox does not lock its files.
2. On first launch the **Station** dialog opens: choose the language and enter callsign, name, email,
   coordinates and equipment. You can reopen it at any time with **Station and callsign...**.
   Changing the language asks to restart the program.
3. The ISS TLE is downloaded from Celestrak and refreshed every 24 hours (cached in `data/`), also while the
   program stays open (never during a reception).
4. Check the **upcoming passes** table (bottom right): the highest passes (in green, above 40°) give the best images.
5. Press **Start receiving** a few minutes before AOS, or enable **Auto-start on passes** and leave the
   program open.

Close SDR#/SDR++ before receiving: the dongle can be used by only one program at a time.
If it is busy, AssicutaISS waits until it is free.

## Icon and splash screen
- `assets/icona.ico` / `assets/icona.png`: program icon (window and Windows taskbar).
- `assets/splash.png`: splash screen shown while loading (the bottom 40 px band shows version and status).
- Replace them with your own images (icon 256x256 PNG with transparency, splash about 640x400) or rebuild
  the default ones with `.venv\Scripts\python.exe tools\make_assets.py`.
- `AssicutaISS.bat` creates an `AssicutaISS.lnk` shortcut with the icon: copy it to the desktop or pin it.

## Configuration files
- `stazione.json`: station data (language, callsign, name, email, ARISS campaign, coordinates, continent,
  receiver, antenna, preamp, cable). Edited from the Station dialog.
  The pass elevation threshold is in `config.json`.
  It is not in the repository because it holds personal data; `stazione.example.json` shows the format.
- `config.json`: receiver settings (frequency, gain, PPM, Doppler/AFC, audio monitor...), saved automatically.

## How it works
- The dongle is tuned 250 kHz below the frequency (avoiding the DC spike) and is **never retuned**.
- The **Doppler** shift (±10 kHz) is computed from the TLE and applied with a phase-continuous software
  oscillator, so there are no frequency jumps.
- The **AFC** measures the residual error from the received FM signal and corrects it (±1500 Hz by default,
  adjustable). It moves only when the SNR is above the "Squelch AFC" threshold **and** the audio contains SSTV
  tones (or an image is being decoded), so voice or carriers on nearby channels cannot pull the tuning away;
  without SSTV signal it slowly returns to zero. It compensates TLE and dongle crystal errors.
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
