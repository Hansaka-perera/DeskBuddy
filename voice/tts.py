from __future__ import annotations

class TTS:
    """Compatibility no-op. Desk Buddy deliberately never synthesizes speech."""
    def __init__(self, settings) -> None:
        self.settings = settings

    def speak(self, text: str) -> None:
        return
