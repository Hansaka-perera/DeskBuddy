from __future__ import annotations

from datetime import datetime
from typing import Dict
import psutil


class ContextSystem:
    def __init__(self, vision=None, behavior=None) -> None:
        self.vision = vision
        self.behavior = behavior

    def snapshot(self) -> Dict:
        now = datetime.now()
        processes = []
        try:
            for p in psutil.process_iter(["name"]):
                name = p.info.get("name")
                if name and name.lower() not in {"system idle process", "system"}:
                    processes.append(name)
        except Exception:
            pass
        unique = []
        for name in processes:
            if name not in unique:
                unique.append(name)
            if len(unique) >= 12:
                break
        vision = self.vision.status() if self.vision else {"enabled": False}
        return {
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "hour": now.hour,
            "period": self._period(now.hour),
            "computer": {"top_processes": unique},
            "camera": vision,
        }

    @staticmethod
    def _period(hour: int) -> str:
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 22:
            return "evening"
        return "late night"
