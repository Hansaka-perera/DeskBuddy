from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QApplication

from ai.config import Settings, Personality
from ai.context import ContextSystem
from ai.brain import Brain
from behavior.engine import BehaviorEngine
from behavior.controller import BuddyController
from behavior.movement import MovementController, MovementState
from behavior.alarm import AlarmManager
from behavior.presence import PresenceController
from database.database import Database
from voice.stt import STT
from vision.camera import VisionManager
from ui.main_window import BuddyWindow
from ui.chat_window import ChatWindow
from ui.settings_window import SettingsWindow
from sound.sound_manager import SoundManager

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
load_dotenv(ROOT / ".env")


class DeskBuddyApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.settings = Settings()
        self.personality = Personality()
        self.db = Database()
        self.vision = VisionManager()
        self.behavior = None
        self.context = ContextSystem(self.vision)
        self.brain = Brain(self.db, self.settings, self.personality, self.context.snapshot)
        self.sound = SoundManager(self.settings)
        self.stt = STT()
        self.behavior = BehaviorEngine(self.settings, self.context)
        self.chat = None
        self.settings_window = None
        self.window = BuddyWindow(self.settings)
        self.movement = MovementController(self.window, self.settings)
        self.alarms = AlarmManager(self.db)
        self.controller = BuddyController(
            self.window.eye_host, self.sound, self.movement, self.behavior, self.vision,
            self.window, self.window,
        )
        self.presence = PresenceController(self.vision, self.window)
        self.window.open_chat.connect(self.show_chat)
        self.window.buddy_clicked.connect(self.controller.on_body_click)
        self.window.open_settings.connect(self.show_settings)
        self.window.toggle_camera.connect(self.toggle_camera)
        self.window.listen.connect(self.listen)
        self.behavior.proactive_message.connect(self.controller.on_proactive)
        self.behavior.emotion_changed.connect(self.controller.on_time_emotion)
        self.alarms.alarm_triggered.connect(self.controller.on_alarm)
        self.presence.state_changed.connect(self.controller.on_presence_state)
        self.presence.returned.connect(self.controller.on_presence_returned)
        self.wander_timer = QTimer(self.window)
        self.wander_timer.timeout.connect(self._wander_if_idle)
        self.wander_timer.start(45000)
        self.gaze_timer = QTimer(self.window)
        self.gaze_timer.timeout.connect(self.controller.update_camera_gaze)
        self.gaze_timer.start(50)
        self._apply_camera_setting()
        self._setup_hotkey()
        self._position_window()
        self.window.show()
        self.sound.play("startup")

    def _position_window(self):
        saved = self.settings.get("position", {})
        if isinstance(saved, dict) and "x" in saved and "y" in saved:
            self.window.move(int(saved["x"]), int(saved["y"]))
            return
        screen = self.app.primaryScreen()
        if screen:
            g = screen.availableGeometry()
            self.window.move(g.right() - self.window.width() - 18, g.bottom() - self.window.height() - 18)

    def _setup_hotkey(self):
        key = self.settings.get("hotkey", "F8")
        try:
            self.shortcut = QShortcut(QKeySequence(key), self.window)
            self.shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            self.shortcut.activated.connect(self.listen)
        except Exception:
            self.shortcut = None

    def _apply_camera_setting(self):
        if self.settings.get("camera_enabled", False):
            self.toggle_camera(True)

    def toggle_camera(self, force=None):
        enable = (not self.vision.enabled) if force is None else bool(force)
        if enable:
            ok = self.vision.start()
            self.settings.set("camera_enabled", bool(ok))
        else:
            self.vision.stop()
            self.settings.set("camera_enabled", False)

    def show_chat(self):
        self.movement.wake()
        if self.chat is None:
            self.chat = ChatWindow(self.brain, self.behavior, self.stt, self.controller, self.handle_command)
            self.chat.message_ready.connect(self._chat_message)
        self.chat.show()
        self.chat.raise_()
        self.chat.activateWindow()

    def _chat_message(self, role: str, text: str):
        """Legacy signal hook — controller already applied the reaction."""
        self.behavior.mark_interaction()

    def show_settings(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.settings, self.toggle_camera)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def listen(self):
        if not self.settings.get("microphone_enabled", True):
            self.controller.on_command_side_effect("neutral", "none", None, "Microphone is disabled in Settings.")
            return
        self.show_chat()
        if self.chat:
            QTimer.singleShot(100, self.chat.listen)

    def handle_command(self, text: str):
        """Deterministic commands always win over an AI response."""
        t = text.lower().strip()
        if any(x in t for x in ("set an alarm", "set a reminder", "remind me", "sleep at", "wake me")):
            alarm_id = self.alarms.add_from_text(t)
            return f"Alarm #{alarm_id} saved." if alarm_id else "Please say a time such as 10 PM."
        if any(x in t for x in ("wake up", "wake buddy", "buddy wake")):
            self.controller.on_command_side_effect("happy", "open", "wake", "I'm awake!")
            self.movement.wake()
            return "I'm awake!"
        if any(x in t for x in ("stay here", "don't move", "do not move", "stop here", "buddy stop")):
            self.movement.stay()
            return "Staying right here."
        if "go to the left" in t or "move left" in t:
            self.movement.move_to(self.window.pos() + self.window.pos().__class__(-220, 0))
            return "Heading left."
        if "go to the right" in t or "move right" in t:
            self.movement.move_to(self.window.pos() + self.window.pos().__class__(220, 0))
            return "Heading right."
        if any(x in t for x in ("start moving", "move over there", "come here", "follow me")):
            self.movement.wander()
            return "On the move."
        return None

    def _wander_if_idle(self):
        from datetime import datetime
        idle_seconds = (datetime.now() - self.behavior.last_interaction).total_seconds()
        if (self.settings.get("movement_enabled", True) and self.settings.get("movement_wander", True)
                and idle_seconds >= 45 and self.movement.state == MovementState.STAY):
            self.movement.wander()

    def shutdown(self):
        self.vision.stop()
        self.movement.stop_animation()
        self.sound.stop_all()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = DeskBuddyApp(app)
    app.aboutToQuit.connect(controller.shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
