import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DISCOVERY_PORT = 45833
HTTP_PORT = 45834
DISCOVERY_MAGIC = b"DRUM_METRONOME_DISCOVER"


def _coerce_bpm(value):
    try:
        bpm = int(value)
    except (TypeError, ValueError):
        return None
    return max(20, min(400, bpm))


class ControlState:
    def __init__(self, name: str, bpm: int = 100, running: bool = False, http_port: int = HTTP_PORT):
        self._lock = threading.Lock()
        self._name = str(name)
        self._bpm = _coerce_bpm(bpm) or 100
        self._running = bool(running)
        self._http_port = int(http_port)

    def set_name(self, name: str):
        with self._lock:
            self._name = str(name)

    def set_bpm(self, bpm: int):
        bpm = _coerce_bpm(bpm)
        if bpm is None:
            return
        with self._lock:
            self._bpm = bpm

    def set_running(self, running: bool):
        with self._lock:
            self._running = bool(running)

    def set_http_port(self, port: int):
        with self._lock:
            self._http_port = int(port)

    def snapshot(self):
        with self._lock:
            return {
                "name": self._name,
                "bpm": int(self._bpm),
                "running": bool(self._running),
                "http_port": int(self._http_port),
            }


class _ControlHandler(BaseHTTPRequestHandler):
    server_version = "DrumMetronomeControl/1.0"

    def log_message(self, *_args):
        return

    def _send_json(self, code: int, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _handle_command(self, action: str, bpm=None):
        state = self.server.control_state
        if action == "start":
            if self.server.on_start:
                self.server.on_start()
            state.set_running(True)
        elif action == "stop":
            if self.server.on_stop:
                self.server.on_stop()
            state.set_running(False)
        elif action == "tempo":
            if bpm is None:
                return self._send_json(400, {"error": "Missing bpm"})
            clamped = _coerce_bpm(bpm)
            if clamped is None:
                return self._send_json(400, {"error": "Invalid bpm"})
            if self.server.on_set_bpm:
                self.server.on_set_bpm(clamped)
            state.set_bpm(clamped)
        return self._send_json(200, state.snapshot())

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/status":
            return self._send_json(200, self.server.control_state.snapshot())
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/start":
            return self._handle_command("start")
        if path == "/stop":
            return self._handle_command("stop")
        if path == "/tempo":
            body = self._read_json()
            if body is None:
                return self._send_json(400, {"error": "Invalid JSON"})
            return self._handle_command("tempo", bpm=body.get("bpm"))
        self._send_json(404, {"error": "Not found"})


class _ControlHttpServer(ThreadingHTTPServer):
    def __init__(self, server_address, control_state, on_start=None, on_stop=None, on_set_bpm=None):
        super().__init__(server_address, _ControlHandler)
        self.control_state = control_state
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_set_bpm = on_set_bpm


class ControlServer:
    def __init__(self, control_state: ControlState, on_start=None, on_stop=None, on_set_bpm=None):
        self._control_state = control_state
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_set_bpm = on_set_bpm
        self._http_server = None
        self._http_thread = None
        self._udp_thread = None
        self._stop_event = threading.Event()

    def start(self, host="0.0.0.0", http_port=HTTP_PORT, discovery_port=DISCOVERY_PORT):
        if self._http_thread and self._http_thread.is_alive():
            return
        self._stop_event.clear()
        self._control_state.set_http_port(http_port)
        self._http_server = _ControlHttpServer(
            (host, http_port),
            self._control_state,
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_set_bpm=self._on_set_bpm,
        )
        self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
        self._http_thread.start()
        self._udp_thread = threading.Thread(
            target=self._discovery_loop, args=(discovery_port, http_port), daemon=True
        )
        self._udp_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._http_server:
            try:
                self._http_server.shutdown()
                self._http_server.server_close()
            except Exception:
                pass
        if self._http_thread and self._http_thread.is_alive():
            self._http_thread.join(timeout=1.0)
        if self._udp_thread and self._udp_thread.is_alive():
            self._udp_thread.join(timeout=1.0)

    def _discovery_loop(self, discovery_port: int, http_port: int):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("", discovery_port))
            sock.settimeout(0.5)
            while not self._stop_event.is_set():
                try:
                    data, addr = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not data:
                    continue
                if data.strip() != DISCOVERY_MAGIC:
                    continue
                payload = self._control_state.snapshot()
                payload["http_port"] = int(http_port)
                try:
                    sock.sendto(json.dumps(payload).encode("utf-8"), addr)
                except OSError:
                    continue
        finally:
            try:
                sock.close()
            except Exception:
                pass
