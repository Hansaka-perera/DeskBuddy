from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class SoundManager(QObject):
    """Short non-verbal effects only. No text-to-speech."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.root = Path(__file__).resolve().parents[1]
        self.output = QAudioOutput(self)
        self.players: dict[str, QMediaPlayer] = {}
        self.paths: dict[str, Path] = {}
        self.aliases = {
            "startup": "ai interface sound", "click": "robot click", "listening": "tiny beep",
            "thinking": "thinking beep", "happy": "happy notification", "surprised": "wow sound",
            "confused": "digital bubble", "angry": "error beep", "annoyed": "robot click",
            "error": "error beep", "notification": "soft notification",
            "wake": "wake up sound", "sleep": "sleep sound", "reaction": "cute UI pop",
        }
        self._last_played: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        sound_dir = self.root / "assets" / "sounds"
        if not sound_dir.exists():
            return
        # Keep paths only. QMediaPlayer probes a file as soon as setSource is
        # called, which made startup emit an FFmpeg block for every MP3.
        self.paths = {path.stem.lower(): path for path in sound_dir.glob("*.mp3")}

    def _player_for(self, key: str) -> QMediaPlayer | None:
        if key in self.players:
            return self.players[key]
        path = self.paths.get(key)
        if path is None or not path.is_file():
            return None
        player = QMediaPlayer(self)
        player.setAudioOutput(self.output)
        player.setSource(QUrl.fromLocalFile(str(path)))
        self.players[key] = player
        return player

    def play(self, name: str | None) -> None:
        if not self.settings.get("sound_enabled", True):
            return
        import time
        key = self.aliases.get((name or "").lower(), (name or "").lower())
        player = self._player_for(key)
        if player is None or time.monotonic() - self._last_played.get(key, 0) < 0.15:
            return
        self.output.setVolume(max(0.0, min(1.0, float(self.settings.get("sound_volume", 0.8)))))
        for other in self.players.values():
            if other is not player and other.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                other.stop()
        self._last_played[key] = time.monotonic()
        player.setPosition(0)
        player.play()

    def stop_all(self) -> None:
        for player in self.players.values():
            player.stop()
