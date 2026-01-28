DrumMetronome — A practice‑focused metronome for drum pad work (PyQt5)

Features
- Solid metronome with accent on 1, time signature, and subdivisions
- Visual beat indicator with accent highlight
- Tap tempo
- Tempo Ladder routine: automatically climbs from a start BPM to an end BPM by a step after N bars
- MIDI output for groove notes with per-drum note and velocity mapping

Quick start
1. Create a virtual environment (optional) and install requirements:
   ```
   pip install -r requirements.txt
   ```
2. Run the app:
   ```
   python main.py
   ```

MIDI output
- Enable "MIDI Output" and choose an output port in the app.
- macOS: enable the IAC Driver in Audio MIDI Setup (or use a virtual MIDI tool) and select the IAC port.
- Windows: install loopMIDI or loopBE1, create a virtual port, then select it in the app.
- Use the Drum Mapping table to set MIDI note and velocity per drum voice.

Notes
- Audio uses QtMultimedia `QAudioOutput` and generates click tones on the fly (no external audio files).
- Tested with Python 3.10+ and PyQt5.

Remote control (LAN)
- The app starts a local HTTP server on port 45834 and listens for UDP discovery on 45833.
- UDP discovery: broadcast `DRUM_METRONOME_DISCOVER` to port 45833; the app replies with JSON metadata.
- HTTP API: `GET /status`, `POST /start`, `POST /stop`, `POST /tempo` with `{"bpm": 120}`.
- Ensure firewall rules allow inbound UDP/45833 and TCP/45834 on the desktop.
- To change ports, edit `drum_metronome.ini` and set `remote/http_port` and `remote/discovery_port`.

Android remote
- Flutter app lives under `android/`. See `android/README.md` for setup/build steps.
