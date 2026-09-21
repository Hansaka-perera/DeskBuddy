from __future__ import annotations

from datetime import datetime, time as dtime
from pathlib import Path
import random

from PySide6.QtCore import QObject, Signal, QTimer


class BehaviorEngine(QObject):
    proactive_message = Signal(str)
    emotion_changed = Signal(str)

    def __init__(self, settings, context, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.context = context
        self.last_interaction = datetime.now()
        self.proactive_count = 0
        self.hour_key = datetime.now().strftime("%Y%m%d%H")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(15000)

    def mark_interaction(self) -> None:
        self.last_interaction = datetime.now()

    def _tick(self) -> None:
        now = datetime.now()
        key = now.strftime("%Y%m%d%H")
        if key != self.hour_key:
            self.hour_key = key
            self.proactive_count = 0
        self._update_time_emotion(now)
        if not self.settings.get("proactive_mode", True):
            return
        if self._quiet_hours(now.time()):
            return
        idle_minutes = (now - self.last_interaction).total_seconds() / 60
        limit = int(self.settings.get("minimum_idle_minutes", 10))
        max_per_hour = int(self.settings.get("max_proactive_per_hour", 3))
        if idle_minutes < limit or self.proactive_count >= max_per_hour:
            return
        # Only occasionally trigger, so the desktop buddy doesn't become a notification machine.
        if random.random() > 0.05:
            return
        self.proactive_count += 1
        self.last_interaction = now
        choices = [
            "Hey... you still there?",
            "I was beginning to think you forgot about me.",
            "Tiny break? Your keyboard deserves one too.",
            "Just checking in. What are we doing next?",
        ]
        self.proactive_message.emit(random.choice(choices))

    def _update_time_emotion(self, now: datetime) -> None:
        h = now.hour
        if h >= 0 and h < 5:
            self.emotion_changed.emit("sleepy")
        elif h >= 23:
            self.emotion_changed.emit("sleepy")

    def _quiet_hours(self, current: dtime) -> bool:
        q = self.settings.get("quiet_hours", {"start": "23:00", "end": "07:00"})
        try:
            start = datetime.strptime(q["start"], "%H:%M").time()
            end = datetime.strptime(q["end"], "%H:%M").time()
            if start <= end:
                return start <= current < end
            return current >= start or current < end
        except Exception:
            return False
