DrumMetronome — A practice‑focused metronome for drum pad work (PyQt5)

Features
- Solid metronome with accent on 1, time signature, and subdivisions
- Visual beat indicator with accent highlight
- Tap tempo
- Tempo Ladder routine: automatically climbs from a start BPM to an end BPM by a step after N bars

Quick start
1. Create a virtual environment (optional) and install requirements:
   ```
   pip install -r requirements.txt
   ```
2. Run the app:
   ```
   python main.py
   ```

Notes
- Audio uses QtMultimedia `QAudioOutput` and generates click tones on the fly (no external audio files).
- Tested with Python 3.10+ and PyQt5.
