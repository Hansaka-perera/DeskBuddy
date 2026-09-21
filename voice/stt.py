from __future__ import annotations

import threading
from PySide6.QtCore import QObject, Signal

try:
    import speech_recognition as sr
except Exception:
    sr = None


class STT(QObject):
    result = Signal(str)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.recognizer = sr.Recognizer() if sr else None

    def listen_once(self, on_result, on_error, phrase_time_limit=8) -> None:
        # A repeated microphone click must not leave old GUI callbacks subscribed.
        try:
            self.result.disconnect()
            self.error.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.result.connect(on_result)
        self.error.connect(on_error)
        if self.recognizer is None:
            self.error.emit("SpeechRecognition is not installed.")
            return

        def worker():
            try:
                with sr.Microphone() as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    audio = self.recognizer.listen(source, phrase_time_limit=phrase_time_limit)
                text = self.recognizer.recognize_google(audio)
                self.result.emit(text)
            except Exception as exc:
                self.error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()
