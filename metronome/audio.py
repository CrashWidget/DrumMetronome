from PyQt5.QtCore import QObject, QBuffer, pyqtSlot, pyqtSignal
from PyQt5.QtMultimedia import QAudioFormat, QAudioOutput, QAudioDeviceInfo, QAudio
from collections import OrderedDict
import math
import struct
import random


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
        self._normal_sound = "Woodblock"
        self._accent_sound = "Woodblock"
        self._volume = 1.0
        # Defer initialization to initialize() slot to ensure it runs in the worker thread

    @pyqtSlot(str, str)
    def set_sounds(self, normal: str, accent: str):
        """Updates the sound types used for normal and accent clicks."""
        self._normal_sound = normal
        self._accent_sound = accent
        if self.format:
            self._rebuild_clicks()

    @pyqtSlot(float)
    def set_volume(self, volume: float):
        """Set output volume from 0.0 to 1.0."""
        try:
            vol = float(volume)
        except (TypeError, ValueError):
            return
        vol = max(0.0, min(1.0, vol))
        self._volume = vol
        if self.output is not None:
            try:
                self.output.setVolume(self._volume)
            except Exception:
                pass

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
            self.output.setVolume(self._volume)
        except Exception:
            pass
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


class GrooveMidiAudio(QObject):
    """Synthesizes simple MIDI-style drum sounds for groove playback."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device_info = QAudioDeviceInfo.defaultOutputDevice()
        self.format = None
        self.output = None
        self.sink = None
        self._enabled = False
        self._voice_samples = {}
        self._packed_voice_samples = {}
        self._accent_gain = 1.25
        self._simplified = False
        self._mix_cache = OrderedDict()
        self._mix_cache_limit = 64

    @pyqtSlot(bool)
    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)

    @pyqtSlot(bool)
    def set_simplified(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._simplified:
            return
        self._simplified = enabled
        self._mix_cache.clear()
        if self.format:
            self._rebuild_samples()

    @pyqtSlot()
    def initialize(self):
        self._init_output(self._device_info)

    def list_output_devices(self):
        return QAudioDeviceInfo.availableDevices(QAudio.AudioOutput)

    @pyqtSlot(str)
    def set_output_device_by_name(self, name: str) -> bool:
        for info in self.list_output_devices():
            if info.deviceName() == name:
                self._init_output(info)
                return True
        return False

    def _init_output(self, device_info: QAudioDeviceInfo):
        try:
            if self.output is not None:
                self.output.stop()
                self.output.deleteLater()
        except Exception:
            pass
        self.output = None
        self.sink = None
        self._device_info = device_info

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

        self.output = QAudioOutput(device_info, self.format, self)
        try:
            self.output.setBufferSize(4096)
        except Exception:
            pass

        self._rebuild_samples()
        self.sink = self.output.start()

    def _rebuild_samples(self):
        self._voice_samples = {}
        for voice, params in self._voice_params().items():
            params = dict(params)
            variants = int(params.pop("variants", 1))
            if variants > 1:
                self._voice_samples[voice] = [
                    self._make_voice_sample(**params) for _ in range(variants)
                ]
            else:
                self._voice_samples[voice] = self._make_voice_sample(**params)
        if "hihat_closed" in self._voice_samples and "hihat" not in self._voice_samples:
            self._voice_samples["hihat"] = self._voice_samples["hihat_closed"]
        self._rebuild_packed_samples()
        self._mix_cache.clear()

    def _apply_gain(self, samples, gain: float):
        if gain == 1.0:
            return samples
        return [val * gain for val in samples]

    def _rebuild_packed_samples(self):
        self._packed_voice_samples = {}
        if not self.format:
            return
        for voice, sample in self._voice_samples.items():
            if isinstance(sample, list) and sample and isinstance(sample[0], list):
                normal = [self._pack_samples(variant) for variant in sample]
                accent = [
                    self._pack_samples(self._apply_gain(variant, self._accent_gain))
                    for variant in sample
                ]
                self._packed_voice_samples[voice] = {
                    "variants": True,
                    "normal": normal,
                    "accent": accent,
                }
            else:
                self._packed_voice_samples[voice] = {
                    "variants": False,
                    "normal": self._pack_samples(sample),
                    "accent": self._pack_samples(self._apply_gain(sample, self._accent_gain)),
                }

    def _voice_params(self):
        if self._simplified:
            return {
                "kick": {
                    "freq": 120.0,
                    "freq_end": 70.0,
                    "ms": 60,
                    "volume": 0.85,
                    "decay_ms": 80,
                    "wave": "sine",
                    "attack_ms": 1,
                    "variants": 1,
                },
                "snare": {
                    "freq": 0.0,
                    "freq_end": None,
                    "ms": 60,
                    "volume": 0.6,
                    "decay_ms": 70,
                    "wave": "noise",
                    "noise_hp": 0.18,
                    "noise_lp": 0.35,
                    "attack_ms": 1,
                    "variants": 1,
                },
                "hihat_closed": {
                    "freq": 0.0,
                    "freq_end": None,
                    "ms": 25,
                    "volume": 0.22,
                    "decay_ms": 30,
                    "wave": "noise",
                    "noise_hp": 0.3,
                    "noise_lp": 0.55,
                    "attack_ms": 1,
                    "variants": 1,
                },
                "hihat_open": {
                    "freq": 0.0,
                    "freq_end": None,
                    "ms": 80,
                    "volume": 0.24,
                    "decay_ms": 110,
                    "wave": "noise",
                    "noise_hp": 0.2,
                    "noise_lp": 0.5,
                    "attack_ms": 2,
                    "variants": 1,
                },
                "ride": {
                    "freq": 0.0,
                    "freq_end": None,
                    "ms": 120,
                    "volume": 0.2,
                    "decay_ms": 140,
                    "wave": "noise",
                    "noise_hp": 0.2,
                    "noise_lp": 0.4,
                    "attack_ms": 2,
                    "variants": 1,
                },
                "crash": {
                    "freq": 0.0,
                    "freq_end": None,
                    "ms": 160,
                    "volume": 0.26,
                    "decay_ms": 190,
                    "wave": "noise",
                    "noise_hp": 0.15,
                    "noise_lp": 0.4,
                    "attack_ms": 2,
                    "variants": 1,
                },
                "tom1": {
                    "freq": 240.0,
                    "freq_end": 160.0,
                    "ms": 80,
                    "volume": 0.6,
                    "decay_ms": 100,
                    "wave": "sine",
                    "attack_ms": 1,
                    "variants": 1,
                },
                "tom2": {
                    "freq": 180.0,
                    "freq_end": 120.0,
                    "ms": 90,
                    "volume": 0.6,
                    "decay_ms": 110,
                    "wave": "sine",
                    "attack_ms": 1,
                    "variants": 1,
                },
                "tom3": {
                    "freq": 140.0,
                    "freq_end": 100.0,
                    "ms": 100,
                    "volume": 0.6,
                    "decay_ms": 120,
                    "wave": "sine",
                    "attack_ms": 1,
                    "variants": 1,
                },
            }
        hihat_tone_freqs = [4200.0, 5600.0, 7200.0, 8800.0, 10400.0]
        ride_tone_freqs = [2800.0, 3600.0, 4500.0, 5600.0, 6800.0, 8100.0, 9600.0, 11400.0]
        crash_tone_freqs = [3200.0, 4100.0, 5200.0, 6400.0, 7800.0, 9300.0, 11100.0, 12900.0, 14600.0]
        hihat_closed = {
            "freq": 0.0,
            "freq_end": None,
            "ms": 35,
            "volume": 0.28,
            "decay_ms": 40,
            "wave": "hihat",
            "attack_ms": 2,
            "noise_hp": 0.22,
            "noise_lp": 0.45,
            "tone_mix": 0.52,
            "tone_freqs": hihat_tone_freqs,
            "variants": 4,
        }
        hihat_open = {
            "freq": 0.0,
            "freq_end": None,
            "ms": 220,
            "volume": 0.3,
            "decay_ms": 260,
            "wave": "hihat",
            "attack_ms": 5,
            "noise_hp": 0.12,
            "noise_lp": 0.4,
            "tone_mix": 0.6,
            "tone_freqs": hihat_tone_freqs,
            "variants": 4,
        }
        return {
            "kick": {
                "freq": 150.0,
                "freq_end": 55.0,
                "ms": 120,
                "volume": 0.9,
                "decay_ms": 170,
                "wave": "mix",
                "noise_mix": 0.08,
                "noise_hp": 0.25,
                "attack_ms": 2,
                "variants": 2,
            },
            "snare": {
                "freq": 200.0,
                "freq_end": 170.0,
                "ms": 120,
                "volume": 0.72,
                "decay_ms": 160,
                "wave": "mix",
                "noise_mix": 0.7,
                "noise_hp": 0.14,
                "noise_lp": 0.32,
                "attack_ms": 2,
                "variants": 3,
            },
            "hihat_closed": hihat_closed,
            "hihat_open": hihat_open,
            "ride": {
                "freq": 0.0,
                "freq_end": None,
                "ms": 260,
                "volume": 0.3,
                "decay_ms": 420,
                "wave": "cymbal",
                "noise_hp": 0.1,
                "noise_lp": 0.28,
                "tone_mix": 0.5,
                "tone_freqs": ride_tone_freqs,
                "attack_ms": 3,
                "variants": 3,
            },
            "crash": {
                "freq": 0.0,
                "freq_end": None,
                "ms": 520,
                "volume": 0.4,
                "decay_ms": 900,
                "wave": "cymbal",
                "noise_hp": 0.18,
                "noise_lp": 0.28,
                "tone_mix": 0.62,
                "tone_freqs": crash_tone_freqs,
                "attack_ms": 2,
                "variants": 3,
            },
            "tom1": {
                "freq": 240.0,
                "freq_end": 170.0,
                "ms": 140,
                "volume": 0.7,
                "decay_ms": 200,
                "wave": "mix",
                "noise_mix": 0.12,
                "noise_hp": 0.08,
                "noise_lp": 0.25,
                "attack_ms": 2,
                "variants": 2,
            },
            "tom2": {
                "freq": 180.0,
                "freq_end": 130.0,
                "ms": 150,
                "volume": 0.7,
                "decay_ms": 210,
                "wave": "mix",
                "noise_mix": 0.1,
                "noise_hp": 0.08,
                "noise_lp": 0.25,
                "attack_ms": 2,
                "variants": 2,
            },
            "tom3": {
                "freq": 140.0,
                "freq_end": 95.0,
                "ms": 170,
                "volume": 0.75,
                "decay_ms": 230,
                "wave": "mix",
                "noise_mix": 0.1,
                "noise_hp": 0.07,
                "noise_lp": 0.25,
                "attack_ms": 2,
                "variants": 2,
            },
        }

    def _mix_cache_key(self, notes):
        if not self._simplified:
            return None
        key = []
        for note in notes:
            voice = getattr(note, "voice", None)
            if not voice or voice not in self._voice_samples:
                continue
            key.append((voice, bool(getattr(note, "accent", False))))
        if not key:
            return None
        key.sort()
        return tuple(key)

    def _make_voice_sample(
        self,
        freq: float,
        freq_end: float,
        ms: int,
        volume: float,
        decay_ms: int,
        wave: str,
        noise_mix: float = 0.0,
        tone_mix: float = 0.0,
        tone_freqs=None,
        noise_hp: float = 0.0,
        noise_lp: float = 0.0,
        attack_ms: int = 0,
    ):
        sr = int(self.format.sampleRate())
        n_samples = int(sr * (ms / 1000.0))
        n_samples = max(1, n_samples)
        tau = max(1.0, sr * (decay_ms / 1000.0))
        duration = max(0.001, ms / 1000.0)
        attack_samples = int(sr * (attack_ms / 1000.0)) if attack_ms > 0 else 0
        if noise_hp < 0.0:
            noise_hp = 0.0
        elif noise_hp > 0.99:
            noise_hp = 0.99
        if noise_lp < 0.0:
            noise_lp = 0.0
        elif noise_lp > 0.99:
            noise_lp = 0.99
        if noise_mix < 0.0:
            noise_mix = 0.0
        elif noise_mix > 1.0:
            noise_mix = 1.0
        if tone_mix < 0.0:
            tone_mix = 0.0
        elif tone_mix > 1.0:
            tone_mix = 1.0

        hihat_freqs = None
        hihat_phases = None
        hihat_lp = 0.0
        hihat_noise_lp = 0.0
        cymbal_freqs = None
        cymbal_phases = None
        cymbal_lp = 0.0
        cymbal_noise_lp = 0.0
        noise_hp_state = 0.0
        noise_lp_state = 0.0
        if wave == "hihat":
            base_freqs = tone_freqs or [4600.0, 6000.0, 7600.0, 9200.0, 11200.0]
            hihat_freqs = []
            for f in base_freqs:
                jitter = random.uniform(-0.03, 0.03)
                hihat_freqs.append(f * (1.0 + jitter))
            hihat_phases = [random.uniform(0.0, 2.0 * math.pi) for _ in hihat_freqs]
        if wave == "cymbal":
            base_freqs = tone_freqs or [3200.0, 4100.0, 5200.0, 6400.0, 7800.0, 9300.0, 11100.0, 12900.0]
            cymbal_freqs = []
            for f in base_freqs:
                jitter = random.uniform(-0.04, 0.04)
                cymbal_freqs.append(f * (1.0 + jitter))
            cymbal_phases = [random.uniform(0.0, 2.0 * math.pi) for _ in cymbal_freqs]

        samples = []
        for i in range(n_samples):
            t = i / float(sr)
            env = math.exp(-i / tau)
            if attack_samples > 0:
                env *= min(1.0, i / attack_samples)

            if freq_end and freq > 0.0:
                ratio = freq_end / freq
                f = freq * (ratio ** (t / duration))
            else:
                f = freq

            phase = 2 * math.pi * f * t if f > 0.0 else 0.0
            if wave == "hihat":
                noise = random.uniform(-1.0, 1.0)
                if noise_hp > 0.0:
                    hihat_lp += (noise - hihat_lp) * noise_hp
                    noise = noise - hihat_lp
                if noise_lp > 0.0:
                    hihat_noise_lp += (noise - hihat_noise_lp) * noise_lp
                    noise = hihat_noise_lp
                metal = 0.0
                if hihat_freqs:
                    for f, phase_offset in zip(hihat_freqs, hihat_phases):
                        metal += math.sin(2 * math.pi * f * t + phase_offset)
                    metal /= len(hihat_freqs)
                base = (1.0 - tone_mix) * noise + tone_mix * metal
            elif wave == "cymbal":
                noise = random.uniform(-1.0, 1.0)
                if noise_hp > 0.0:
                    cymbal_lp += (noise - cymbal_lp) * noise_hp
                    noise = noise - cymbal_lp
                if noise_lp > 0.0:
                    cymbal_noise_lp += (noise - cymbal_noise_lp) * noise_lp
                    noise = cymbal_noise_lp
                metal = 0.0
                if cymbal_freqs:
                    for f, phase_offset in zip(cymbal_freqs, cymbal_phases):
                        metal += math.sin(2 * math.pi * f * t + phase_offset)
                    metal /= len(cymbal_freqs)
                base = (1.0 - tone_mix) * noise + tone_mix * metal
            elif wave == "noise":
                noise = random.uniform(-1.0, 1.0)
                if noise_hp > 0.0:
                    noise_hp_state += (noise - noise_hp_state) * noise_hp
                    noise = noise - noise_hp_state
                if noise_lp > 0.0:
                    noise_lp_state += (noise - noise_lp_state) * noise_lp
                    noise = noise_lp_state
                base = noise
            elif wave == "square":
                base = 1.0 if math.sin(phase) >= 0 else -1.0
            elif wave == "triangle":
                s_val = math.sin(phase)
                if s_val > 1.0:
                    s_val = 1.0
                elif s_val < -1.0:
                    s_val = -1.0
                base = (2.0 / math.pi) * math.asin(s_val)
            elif wave == "mix":
                tone = math.sin(phase)
                noise = random.uniform(-1.0, 1.0)
                if noise_hp > 0.0:
                    noise_hp_state += (noise - noise_hp_state) * noise_hp
                    noise = noise - noise_hp_state
                if noise_lp > 0.0:
                    noise_lp_state += (noise - noise_lp_state) * noise_lp
                    noise = noise_lp_state
                base = (1.0 - noise_mix) * tone + noise_mix * noise
            else:
                base = math.sin(phase)

            samples.append(base * env * volume)

        return samples

    def _mix_notes(self, notes):
        sources = []
        max_len = 0
        for note in notes:
            voice = getattr(note, "voice", None)
            sample = self._voice_samples.get(voice)
            if not sample:
                continue
            if isinstance(sample, list) and sample and isinstance(sample[0], list):
                sample = random.choice(sample)
            gain = self._accent_gain if getattr(note, "accent", False) else 1.0
            sources.append((sample, gain))
            if len(sample) > max_len:
                max_len = len(sample)

        if not sources or max_len == 0:
            return None

        mix = [0.0] * max_len
        for sample, gain in sources:
            for i, val in enumerate(sample):
                mix[i] += val * gain

        mix_gain = 1.0 / max(1.0, len(sources) * 0.75)
        for i, val in enumerate(mix):
            v = val * mix_gain
            if v > 1.0:
                v = 1.0
            elif v < -1.0:
                v = -1.0
            mix[i] = v

        return mix

    def _pack_samples(self, samples):
        channels = int(self.format.channelCount())
        samp_size = int(self.format.sampleSize())
        samp_type = self.format.sampleType()
        little = self.format.byteOrder() == QAudioFormat.LittleEndian

        def write_sample(raw: bytearray, frame_index: int, value_float: float):
            vf = max(-1.0, min(1.0, value_float))
            for ch in range(channels):
                if samp_type == QAudioFormat.Float and samp_size == 32:
                    b = struct.pack('<f' if little else '>f', float(vf))
                    stride = 4
                else:
                    if samp_size == 8:
                        if samp_type == QAudioFormat.UnSignedInt:
                            ival = int((vf * 0.5 + 0.5) * 255)
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
                        ival = int(vf * 32767)
                        lo = ival & 0xFF
                        hi = (ival >> 8) & 0xFF
                        b = bytes((lo, hi)) if little else bytes((hi, lo))
                        stride = 2
                base = frame_index * channels * stride + ch * stride
                raw[base:base + stride] = b

        if samp_type == QAudioFormat.Float and samp_size == 32:
            bytes_per_sample = 4
        elif samp_size in (8, 16, 32):
            bytes_per_sample = samp_size // 8
        else:
            bytes_per_sample = 2
        bytes_per_frame = channels * bytes_per_sample

        raw = bytearray(len(samples) * bytes_per_frame)
        for i, val in enumerate(samples):
            write_sample(raw, i, val)
        return bytes(raw)

    @pyqtSlot(list)
    def play_notes(self, notes):
        if not self._enabled or not notes or not self.sink:
            return

        if self.output.state() == QAudio.StoppedState:
            self.sink = self.output.start()

        if len(notes) == 1:
            note = notes[0]
            voice = getattr(note, "voice", None)
            packed = self._packed_voice_samples.get(voice)
            if packed:
                accent = getattr(note, "accent", False)
                if packed.get("variants"):
                    variants = packed["accent"] if accent else packed["normal"]
                    if variants:
                        data = random.choice(variants)
                        self.sink.write(data)
                        return
                else:
                    data = packed["accent"] if accent else packed["normal"]
                    if data:
                        self.sink.write(data)
                        return

        cache_key = self._mix_cache_key(notes)
        if cache_key is not None:
            cached = self._mix_cache.get(cache_key)
            if cached:
                self.sink.write(cached)
                return

        mixed = self._mix_notes(notes)
        if not mixed:
            return

        data = self._pack_samples(mixed)
        if cache_key is not None:
            self._mix_cache[cache_key] = data
            if len(self._mix_cache) > self._mix_cache_limit:
                self._mix_cache.popitem(last=False)
        self.sink.write(data)
