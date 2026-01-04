from PyQt5.QtCore import QObject, QBuffer, pyqtSlot, pyqtSignal
from PyQt5.QtMultimedia import QAudioFormat, QAudioOutput, QAudioDeviceInfo, QAudio
import math
import struct


class ClickAudio(QObject):
    """Generates short click sounds for metronome using QtMultimedia.

    Two tones: normal and accent. Uses in-memory PCM buffers played via QAudioOutput.
    """
    deviceChanged = pyqtSignal(str, str)  # name, format_summary

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device_info = QAudioDeviceInfo.defaultOutputDevice()
        self.format = None
        self.output = None
        self.sink = None
        self._normal_data = None
        self._accent_data = None
        self._normal_sound = "Sine (High)"
        self._accent_sound = "Sine (High)"
        # Defer initialization to initialize() slot to ensure it runs in the worker thread

    @pyqtSlot(str, str)
    def set_sounds(self, normal: str, accent: str):
        """Updates the sound types used for normal and accent clicks."""
        self._normal_sound = normal
        self._accent_sound = accent
        if self.format:
            self._rebuild_clicks()

    def get_available_sounds(self):
        return ["Sine (High)", "Sine (Low)", "Triangle", "Woodblock"]

    def _get_sound_params(self, name: str, is_accent: bool):
        # Base parameters
        params = {"freq": 2200.0, "ms": 12, "vol": 0.6, "wave": "sine"}
        if is_accent:
            params["freq"] = 2800.0
            params["ms"] = 16
            params["vol"] = 0.9

        if name == "Sine (Low)":
            params["freq"] = 880.0 if not is_accent else 1100.0
            params["ms"] = 20
        elif name == "Triangle":
            params["freq"] = 1200.0 if not is_accent else 1600.0
            params["wave"] = "triangle"
            params["ms"] = 15
        elif name == "Woodblock":
            params["freq"] = 500.0 if not is_accent else 750.0
            params["ms"] = 40
            params["vol"] = 0.8 if not is_accent else 1.0
        
        return params

    def _rebuild_clicks(self):
        p_norm = self._get_sound_params(self._normal_sound, False)
        p_acc = self._get_sound_params(self._accent_sound, True)
        
        self._normal_data = self._make_click(
            freq=p_norm["freq"], ms=p_norm["ms"], volume=p_norm["vol"], waveform=p_norm["wave"]
        )
        self._accent_data = self._make_click(
            freq=p_acc["freq"], ms=p_acc["ms"], volume=p_acc["vol"], waveform=p_acc["wave"]
        )

    @pyqtSlot()
    def initialize(self):
        """Initializes the audio output in the correct thread."""
        self._init_output(self._device_info)
        # Report initial state
        self.deviceChanged.emit(self.current_device_name(), self.negotiated_format_summary())

    # Public API: device management
    def list_output_devices(self):
        return QAudioDeviceInfo.availableDevices(QAudio.AudioOutput)

    def current_device_name(self) -> str:
        try:
            return self._device_info.deviceName()
        except Exception:
            return "(unknown)"

    @pyqtSlot(str)
    def set_output_device_by_name(self, name: str) -> bool:
        for info in self.list_output_devices():
            if info.deviceName() == name:
                self._init_output(info)
                self.deviceChanged.emit(self.current_device_name(), self.negotiated_format_summary())
                return True
        return False

    def negotiated_format_summary(self) -> str:
        if not self.format:
            return ""
        st_map = {
            QAudioFormat.Unknown: "Unknown",
            QAudioFormat.SignedInt: "SInt",
            QAudioFormat.UnSignedInt: "UInt",
            QAudioFormat.Float: "Float",
        }
        return f"{self.format.sampleRate()} Hz, {self.format.channelCount()} ch, {self.format.sampleSize()}‑bit {st_map.get(self.format.sampleType(), '')}"

    # Internal: (re)initialize output with device
    def _init_output(self, device_info: QAudioDeviceInfo):
        # Stop and delete previous output if present
        try:
            if self.output is not None:
                self.output.stop()
                self.output.deleteLater()
        except Exception:
            pass
        self.output = None
        self.sink = None
        self._device_info = device_info

        # Desired baseline format
        desired = QAudioFormat()
        desired.setSampleRate(44100)
        desired.setChannelCount(1)
        desired.setSampleSize(16)
        desired.setCodec("audio/pcm")
        desired.setByteOrder(QAudioFormat.LittleEndian)
        desired.setSampleType(QAudioFormat.SignedInt)

        if not device_info.isFormatSupported(desired):
            self.format = device_info.nearestFormat(desired)
        else:
            self.format = desired

        # Create device-specific QAudioOutput
        self.output = QAudioOutput(device_info, self.format, self)
        try:
            # Low latency buffer for Push mode
            self.output.setBufferSize(4096)
        except Exception:
            pass

        # Rebuild click data
        self._rebuild_clicks()

        # Start in Push mode (streaming)
        self.sink = self.output.start()

    def _make_click(self, freq: float, ms: int, volume: float, waveform: str = 'sine') -> bytes:
        sr = int(self.format.sampleRate())
        channels = int(self.format.channelCount())
        n_samples = int(sr * (ms / 1000.0))
        samp_size = int(self.format.sampleSize())
        samp_type = self.format.sampleType()
        little = self.format.byteOrder() == QAudioFormat.LittleEndian

        # helper: write a one-sample value to raw at index for each channel
        def write_sample(raw: bytearray, frame_index: int, value_float: float):
            # clamp
            vf = max(-1.0, min(1.0, value_float))
            for ch in range(channels):
                if samp_type == QAudioFormat.Float and samp_size == 32:
                    b = struct.pack('<f' if little else '>f', float(vf))
                    stride = 4
                else:
                    # integer PCM
                    if samp_size == 8:
                        # 8-bit PCM in Qt is typically UnsignedInt
                        if samp_type == QAudioFormat.UnSignedInt:
                            ival = int((vf * 0.5 + 0.5) * 255)  # map -1..1 to 0..255
                        else:
                            ival = int(vf * 127)
                        b = bytes([ival & 0xFF])
                        stride = 1
                    elif samp_size == 16:
                        if samp_type == QAudioFormat.UnSignedInt:
                            ival = int((vf * 0.5 + 0.5) * 65535)
                        else:
                            ival = int(vf * 32767)
                        lo = ival & 0xFF
                        hi = (ival >> 8) & 0xFF
                        b = bytes((lo, hi)) if little else bytes((hi, lo))
                        stride = 2
                    elif samp_size == 32:
                        if samp_type == QAudioFormat.UnSignedInt:
                            ival = int((vf * 0.5 + 0.5) * 0xFFFFFFFF)
                        else:
                            ival = int(vf * 0x7FFFFFFF)
                        b0 = ival & 0xFF
                        b1 = (ival >> 8) & 0xFF
                        b2 = (ival >> 16) & 0xFF
                        b3 = (ival >> 24) & 0xFF
                        b = bytes((b0, b1, b2, b3)) if little else bytes((b3, b2, b1, b0))
                        stride = 4
                    else:
                        # Fallback: treat as 16-bit signed
                        ival = int(vf * 32767)
                        lo = ival & 0xFF
                        hi = (ival >> 8) & 0xFF
                        b = bytes((lo, hi)) if little else bytes((hi, lo))
                        stride = 2
                base = frame_index * channels * stride + ch * stride
                raw[base:base + stride] = b

        # total bytes per frame
        if samp_type == QAudioFormat.Float and samp_size == 32:
            bytes_per_sample = 4
        elif samp_size in (8, 16, 32):
            bytes_per_sample = samp_size // 8
        else:
            bytes_per_sample = 2
        bytes_per_frame = channels * bytes_per_sample

        raw = bytearray(n_samples * bytes_per_frame)
        tau = max(1.0, n_samples / 6.0)
        for i in range(n_samples):
            t = i / float(sr)
            env = math.exp(-i / tau)
            
            phase = 2 * math.pi * freq * t
            if waveform == 'sine':
                sample = math.sin(phase)
            elif waveform == 'triangle':
                # Triangle: (2/pi) * arcsin(sin(2*pi*f*t))
                # Clamp sin output to avoid domain errors in asin due to float precision
                s_val = math.sin(phase)
                if s_val > 1.0: s_val = 1.0
                elif s_val < -1.0: s_val = -1.0
                sample = (2.0 / math.pi) * math.asin(s_val)
            elif waveform == 'square':
                sample = 1.0 if math.sin(phase) > 0 else -1.0
            else:
                sample = math.sin(phase)

            sample *= env * volume
            write_sample(raw, i, sample)

        return bytes(raw)

    @pyqtSlot(bool)
    def play(self, accent: bool = False):
        if not self.sink:
            return

        # If output stopped unexpectedly (underrun recovery or device hiccup), restart it
        if self.output.state() == QAudio.StoppedState:
            self.sink = self.output.start()

        data = self._accent_data if accent else self._normal_data
        if self.sink:
            self.sink.write(data)
