from PyQt5.QtCore import QObject

try:
    from PyQt5.QtTextToSpeech import QTextToSpeech, QVoice
except Exception:  # pragma: no cover - optional dependency
    QTextToSpeech = None
    QVoice = None


class BpmVoiceAnnouncer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tts = None
        self._enabled = True
        self._rate = 0.0
        if QTextToSpeech is None:
            return
        try:
            self._tts = QTextToSpeech(self)
        except Exception:
            self._tts = None
            return
        self._configure_voice()

    def _configure_voice(self):
        self._select_female_voice()
        self.set_rate(self._rate)
        try:
            self._tts.setPitch(1.0)
            self._tts.setVolume(1.0)
        except Exception:
            pass

    def _select_female_voice(self):
        if self._tts is None:
            return
        try:
            voices = self._tts.availableVoices()
        except Exception:
            voices = []
        if not voices:
            return
        female = [v for v in voices if hasattr(v, "gender") and v.gender() == QVoice.Female]
        if not female:
            female = [v for v in voices if "female" in v.name().lower()]
        chosen = female[0] if female else voices[0]
        try:
            self._tts.setVoice(chosen)
        except Exception:
            pass

    def is_available(self) -> bool:
        return self._tts is not None

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        if not self._enabled:
            try:
                self._tts.stop()
            except Exception:
                pass

    def set_rate(self, rate: float):
        try:
            rate_value = float(rate)
        except (TypeError, ValueError):
            return
        rate_value = max(-1.0, min(1.0, rate_value))
        self._rate = rate_value
        if self._tts is None:
            return
        try:
            self._tts.setRate(rate_value)
        except Exception:
            pass

    def available_voices(self):
        if self._tts is None:
            return []
        try:
            return list(self._tts.availableVoices())
        except Exception:
            return []

    def current_voice(self):
        if self._tts is None:
            return None
        try:
            return self._tts.voice()
        except Exception:
            return None

    def set_voice(self, voice):
        if self._tts is None or voice is None:
            return
        try:
            self._tts.setVoice(voice)
        except Exception:
            pass

    def say_starting(self, bpm: int):
        self._say(f"{int(bpm)} beats per minute starting")

    def say_approaching(self, bpm: int):
        self._say(f"approaching {int(bpm)} beats per minute")

    def _say(self, text: str):
        if self._tts is None or not self._enabled:
            return
        try:
            self._tts.stop()
            self._tts.say(text)
        except Exception:
            pass
