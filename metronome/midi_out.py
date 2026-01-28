from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer
import heapq
import multiprocessing as mp
import queue as queue_mod
import time

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


def _midi_worker(cmd_queue, status_queue):
    try:
        import mido as _mido
    except Exception:
        _mido = None

    mapping = dict(DEFAULT_DRUM_MAPPING)
    enabled = False
    port = None
    port_name = None
    channel = 9
    note_length_ms = 60
    accent_gain = 1.25
    note_off_heap = []

    def send_status(text: str):
        if status_queue is None:
            return
        try:
            status_queue.put_nowait(text)
        except Exception:
            pass

    if not _mido:
        send_status("MIDI unavailable (missing mido)")
    else:
        try:
            ports = _mido.get_output_names()
            send_status("MIDI ready" if ports else "MIDI: no output ports")
        except Exception as exc:
            send_status(f"MIDI error: {exc}")

    while True:
        timeout = None
        if note_off_heap:
            timeout = max(0.0, note_off_heap[0][0] - time.monotonic())
        try:
            cmd = cmd_queue.get(timeout=timeout)
        except queue_mod.Empty:
            cmd = None

        now = time.monotonic()
        while note_off_heap and note_off_heap[0][0] <= now:
            _, midi_note = heapq.heappop(note_off_heap)
            if port and _mido:
                try:
                    port.send(_mido.Message("note_off", note=midi_note, velocity=0, channel=channel))
                except Exception:
                    pass

        if cmd is None:
            continue

        ctype = cmd.get("type")
        if ctype == "shutdown":
            break
        if ctype == "set_enabled":
            enabled = bool(cmd.get("enabled"))
            continue
        if ctype == "set_mapping":
            voice = (cmd.get("voice") or "").strip()
            note = cmd.get("note")
            velocity = cmd.get("velocity")
            if not voice or note is None or velocity is None:
                continue
            mapping[voice] = (int(note), int(velocity))
            continue
        if ctype == "set_port":
            name = cmd.get("name") or ""
            if not _mido:
                send_status("MIDI unavailable (missing mido)")
                continue
            if not name or name == "(no ports)":
                continue
            if port is not None:
                try:
                    port.close()
                except Exception:
                    pass
                port = None
                port_name = None
            try:
                port = _mido.open_output(name)
                port_name = name
                send_status(f"MIDI port: {name}")
            except Exception as exc:
                send_status(f"MIDI open failed: {exc}")
                port = None
                port_name = None
            continue
        if ctype == "play_notes":
            if not enabled or not port or not _mido:
                continue
            notes = cmd.get("notes") or []
            length_ms = cmd.get("note_length_ms", note_length_ms)
            try:
                length_ms = int(round(float(length_ms)))
            except (TypeError, ValueError):
                length_ms = note_length_ms
            length_ms = max(10, min(1000, length_ms))
            note_length_ms = length_ms
            for note in notes:
                voice = note.get("voice")
                if not voice:
                    continue
                voice_key = "hihat_closed" if voice == "hihat" else voice
                midi_note, velocity = mapping.get(voice_key, (None, None))
                if midi_note is None:
                    continue
                accent = bool(note.get("accent"))
                if accent:
                    velocity = int(round(velocity * accent_gain))
                velocity = max(1, min(127, int(velocity)))
                try:
                    port.send(_mido.Message("note_on", note=int(midi_note), velocity=velocity, channel=channel))
                except Exception:
                    continue
                off_time = time.monotonic() + (length_ms / 1000.0)
                heapq.heappush(note_off_heap, (off_time, int(midi_note)))

    if port is not None:
        try:
            port.close()
        except Exception:
            pass


class MidiOutput(QObject):
    statusChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = False
        self._port_name = None
        self._channel = 9
        self._note_length_ms = 60
        self._accent_gain = 1.25
        self._mapping = dict(DEFAULT_DRUM_MAPPING)
        self._process = None
        self._cmd_queue = None
        self._status_queue = None
        self._status_timer = None
        self._health_timer = None
        self._last_process_alive = False

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
        self._ensure_process()
        self._send_command({"type": "set_enabled", "enabled": self._enabled})
        for voice, (note, velocity) in self._mapping.items():
            self._send_command({
                "type": "set_mapping",
                "voice": voice,
                "note": note,
                "velocity": velocity,
            })
        if self._port_name:
            self._send_command({"type": "set_port", "name": self._port_name})

    @pyqtSlot(bool)
    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        self._send_command({"type": "set_enabled", "enabled": self._enabled})

    @pyqtSlot(str)
    def set_output_port_by_name(self, name: str) -> bool:
        if not mido:
            self.statusChanged.emit("MIDI unavailable (missing mido)")
            return False
        if not name:
            return False
        if name == "(no ports)":
            return False
        if name == self._port_name:
            return True
        self._port_name = name
        self._send_command({"type": "set_port", "name": name})
        return True

    @pyqtSlot(str, int, int)
    def set_voice_mapping(self, voice: str, note: int, velocity: int):
        voice = (voice or "").strip()
        if not voice:
            return
        note = max(0, min(127, int(note)))
        velocity = max(1, min(127, int(velocity)))
        self._mapping[voice] = (note, velocity)
        self._send_command({"type": "set_mapping", "voice": voice, "note": note, "velocity": velocity})

    def _ensure_process(self):
        if self._process is not None and self._process.is_alive():
            return
        ctx = mp.get_context("spawn")
        self._cmd_queue = ctx.Queue(maxsize=1024)
        self._status_queue = ctx.Queue()
        self._process = ctx.Process(
            target=_midi_worker,
            args=(self._cmd_queue, self._status_queue),
            daemon=True,
        )
        self._process.start()
        self._last_process_alive = True
        self._start_status_timer()
        self._start_health_timer()

    def _start_status_timer(self):
        if self._status_timer is None:
            self._status_timer = QTimer(self)
            self._status_timer.timeout.connect(self._drain_status_queue)
        if not self._status_timer.isActive():
            self._status_timer.start(100)

    def _start_health_timer(self):
        if self._health_timer is None:
            self._health_timer = QTimer(self)
            self._health_timer.timeout.connect(self._check_process_health)
        if not self._health_timer.isActive():
            self._health_timer.start(500)

    def _check_process_health(self):
        if not self._process:
            return
        alive = self._process.is_alive()
        if not alive and self._last_process_alive:
            exit_code = self._process.exitcode
            if exit_code is None:
                detail = "stopped"
            else:
                detail = f"exited ({exit_code})"
            self.statusChanged.emit(f"MIDI process {detail}")
            self._process = None
            self._cmd_queue = None
            self._status_queue = None
        self._last_process_alive = alive

    def _drain_status_queue(self):
        if not self._status_queue:
            return
        while True:
            try:
                text = self._status_queue.get_nowait()
            except queue_mod.Empty:
                break
            except Exception:
                break
            if text:
                self.statusChanged.emit(text)

    def _send_command(self, cmd: dict):
        if not self._cmd_queue:
            return
        try:
            self._cmd_queue.put_nowait(cmd)
        except queue_mod.Full:
            pass
        except Exception:
            pass

    @pyqtSlot()
    def shutdown_process(self):
        if self._status_timer is not None:
            self._status_timer.stop()
        if self._health_timer is not None:
            self._health_timer.stop()
        if self._cmd_queue:
            try:
                self._cmd_queue.put_nowait({"type": "shutdown"})
            except Exception:
                pass
        if self._process is not None:
            self._process.join(timeout=2.0)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=1.0)
        self._process = None
        self._cmd_queue = None
        self._status_queue = None

    @pyqtSlot(list)
    @pyqtSlot(list, int)
    def play_notes(self, notes, note_length_ms=None):
        if not self._enabled or not notes:
            return
        if not mido or not self._cmd_queue:
            return

        length_ms = self._note_length_ms
        if note_length_ms is not None:
            try:
                length_ms = int(round(float(note_length_ms)))
            except (TypeError, ValueError):
                length_ms = self._note_length_ms
            else:
                length_ms = max(10, min(1000, length_ms))
                self._note_length_ms = length_ms

        payload = []
        for note in notes:
            voice = getattr(note, "voice", None)
            if not voice:
                continue
            payload.append({
                "voice": voice,
                "accent": bool(getattr(note, "accent", False)),
            })
        if not payload:
            return
        self._send_command({
            "type": "play_notes",
            "notes": payload,
            "note_length_ms": length_ms,
        })
