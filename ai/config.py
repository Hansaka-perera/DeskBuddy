from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    file = ROOT / path
    if not file.exists():
        return default
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except Exception:
        return default


class Settings:
    def __init__(self) -> None:
        self.path = ROOT / "config/settings.json"
        self.data = load_json("config/settings.json", {})

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def reload(self) -> None:
        self.data = load_json("config/settings.json", {})


class Personality:
    def __init__(self) -> None:
        self.data = load_json("config/personality.json", {})

    @property
    def name(self) -> str:
        return self.data.get("name", "Buddy")
