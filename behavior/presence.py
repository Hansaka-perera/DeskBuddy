from __future__ import annotations

import time
from PySide6.QtCore import QObject, Signal, QTimer


class PresenceController(QObject):
    """Face presence: watching → waiting → curious → confused → annoyed."""

    state_changed = Signal(str)
    returned = Signal()

    def __init__(self, vision, parent=None):
        super().__init__(parent)
        self.vision = vision
        self.state = "PRESENT"
        self.lost_at = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _set(self, state: str) -> None:
        if self.state != state:
            self.state = state
            self.state_changed.emit(state)

    def _tick(self) -> None:
        status = self.vision.status()
        if not status["enabled"]:
            return
        if status["face_detected"]:
            if self.state != "PRESENT":
                self.returned.emit()
            self.lost_at = None
            self._set("PRESENT")
            return
        if self.lost_at is None:
            self.lost_at = time.monotonic()
            self._set("WATCHING")
            return
        elapsed = time.monotonic() - self.lost_at
        if elapsed < 4:
            self._set("WATCHING")
        elif elapsed < 10:
            self._set("WAITING")
        elif elapsed < 20:
            self._set("CURIOUS")
        elif elapsed < 35:
            self._set("CONFUSED")
        else:
            self._set("ANNOYED")
