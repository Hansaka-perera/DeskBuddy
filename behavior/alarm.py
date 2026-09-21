from __future__ import annotations

import re
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal


class AlarmManager(QObject):
    alarm_triggered = Signal(dict)

    def __init__(self, db, parent=None):
        super().__init__(parent)

        self.db = db

        # Check alarms every second
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_due)
        self.timer.start(1000)

    def add_from_text(self, text: str):
        """
        Parse alarm commands such as:
        - Set a sleep alarm for 10 PM
        - Wake me at 7 AM
        - Remind me at 5:30 PM
        """

        text_lower = text.lower().strip()

        match = re.search(
            r"(?:at|for)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            text_lower
        )

        if not match:
            return None

        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        suffix = match.group(3)

        # Validate basic hour before AM/PM conversion
        if hour < 1 or hour > 12:
            if suffix:
                return None

        # Convert 12-hour format to 24-hour format
        if suffix == "pm" and hour != 12:
            hour += 12

        elif suffix == "am" and hour == 12:
            hour = 0

        # Final validation
        if hour > 23 or minute > 59:
            return None

        # Determine alarm type
        if any(word in text_lower for word in ("sleep", "bed")):
            kind = "sleep"

        elif "wake" in text_lower:
            kind = "wake"

        else:
            kind = "reminder"

        return self.db.add_alarm(
            f"{hour:02d}:{minute:02d}",
            kind
        )

    def check_due(self) -> None:
        """
        Check for alarms matching the current time.
        """

        current_time = datetime.now().strftime("%H:%M")

        for alarm in self.db.due_alarms(current_time):

            # Prevent the same alarm from firing repeatedly
            self.db.mark_alarm_fired(alarm["id"])

            # Notify the application
            self.alarm_triggered.emit(alarm)