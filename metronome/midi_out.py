from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

try:
    import mido
except Exception:  # pragma: no cover - optional dependency guard
    mido = None


DEFAULT_DRUM_MAPPING = {
    "kick": (36, 100),
    "snare": (38, 100),
    "hihat_closed": (42, 90),
    "hihat_open": (46, 90),
    "ride": (51, 90),
    "crash": (49, 100),
    "tom1": (50, 95),
    "tom2": (47, 95),
    "tom3": (45, 95),
    "hihat": (42, 90),
}


class MidiOutput(QObject):
    statusChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = False
        self._port = None
        self._port_name = None
        self._channel = 9
        self._note_length_ms = 60
        self._accent_gain = 1.25
        self._mapping = dict(DEFAULT_DRUM_MAPPING)

    def list_output_ports(self):
        if not mido:
            return []
        try:
            return mido.get_output_names()
        except Exception:
            return []

    @pyqtSlot()
    def initialize(self):
        if not mido:
            self.statusChanged.emit("MIDI unavailable (missing mido)")
            return
        ports = self.list_output_ports()
        if ports:
            self.statusChanged.emit("MIDI ready")
        else:
            self.statusChanged.emit("MIDI: no output ports")

    @pyqtSlot(bool)
    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)

    @pyqtSlot(str)
    def set_output_port_by_name(self, name: str) -> bool:
        if not mido:
            self.statusChanged.emit("MIDI unavailable (missing mido)")
            return False
        if not name:
            return False
        if name == "(no ports)":
            return False
        if name == self._port_name and self._port is not None:
            return True
        if not self._open_port(name):
            return False
        return True

    @pyqtSlot(str, int, int)
    def set_voice_mapping(self, voice: str, note: int, velocity: int):
        voice = (voice or "").strip()
        if not voice:
            return
        note = max(0, min(127, int(note)))
        velocity = max(1, min(127, int(velocity)))
        self._mapping[voice] = (note, velocity)

    def _open_port(self, name: str) -> bool:
        self._close_port()
        try:
            self._port = mido.open_output(name)
            self._port_name = name
            self.statusChanged.emit(f"MIDI port: {name}")
            return True
        except Exception as exc:
            self.statusChanged.emit(f"MIDI open failed: {exc}")
            self._port = None
            self._port_name = None
            return False

    def _close_port(self):
        if self._port is not None:
            try:
                self._port.close()
            except Exception:
                pass
        self._port = None
        self._port_name = None

    def _normalize_voice(self, voice: str) -> str:
        if voice == "hihat":
            return "hihat_closed"
        return voice

    def _get_note_and_velocity(self, voice: str, accent: bool):
        voice_key = self._normalize_voice(voice)
        note, velocity = self._mapping.get(voice_key, (None, None))
        if note is None or velocity is None:
            return None, None
        if accent:
            velocity = int(round(velocity * self._accent_gain))
        velocity = max(1, min(127, velocity))
        return note, velocity

    def _send_note_on(self, note: int, velocity: int):
        if not self._port:
            return
        msg = mido.Message("note_on", note=note, velocity=velocity, channel=self._channel)
        self._port.send(msg)

    def _send_note_off(self, note: int):
        if not self._port:
            return
        msg = mido.Message("note_off", note=note, velocity=0, channel=self._channel)
        self._port.send(msg)

    @pyqtSlot(list)
    def play_notes(self, notes):
        if not self._enabled or not notes:
            return
        if not self._port:
            return
        if not mido:
            return

        for note in notes:
            voice = getattr(note, "voice", None)
            accent = getattr(note, "accent", False)
            if not voice:
                continue
            midi_note, velocity = self._get_note_and_velocity(voice, accent)
            if midi_note is None:
                continue
            self._send_note_on(midi_note, velocity)
            QTimer.singleShot(self._note_length_ms, lambda n=midi_note: self._send_note_off(n))
