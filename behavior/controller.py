from __future__ import annotations

import random
from datetime import datetime, timedelta
from enum import IntEnum

from PySide6.QtCore import QObject, QTimer


class BuddyMode(IntEnum):
    IDLE = 0
    CAMERA = 1
    IDLE_BEHAVIOR = 2
    LISTENING = 10
    THINKING = 11
    RESPONDING = 12
    PRESENCE = 13
    CLICK = 14
    ALARM = 15
    PROACTIVE = 16


class BuddyController(QObject):
    """Single reaction hub so eye animations, sounds, and messages never fight."""

    def __init__(self, eye_host, sound, movement, behavior, vision, buddy_window, parent=None):
        super().__init__(parent)
        self.eye_host = eye_host
        self.sound = sound
        self.movement = movement
        self.buddy_window = buddy_window
        self.behavior = behavior
        self.vision = vision
        self.mode = BuddyMode.IDLE
        self._mode_until = 0.0
        self._click_count = 0
        self._last_click = datetime.min
        self._message_timer = QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self._clear_message)
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._idle_tick)
        self._idle_timer.start(3200)
        self._return_step = 0
        self._last_frame_size = (640.0, 480.0)

    # ------------------------------------------------------------------ helpers
    def _now(self) -> float:
        import time
        return time.monotonic()

    def _set_mode(self, mode: BuddyMode, hold_seconds: float = 0.0) -> None:
        self.mode = mode
        if hold_seconds > 0:
            self._mode_until = self._now() + hold_seconds
        else:
            self._mode_until = 0.0

    def _mode_active(self, *modes: BuddyMode) -> bool:
        if self._mode_until and self._now() >= self._mode_until:
            self._set_mode(BuddyMode.IDLE)
        return self.mode in modes

    def _can_idle(self) -> bool:
        if self._mode_until and self._now() >= self._mode_until:
            self._set_mode(BuddyMode.IDLE)
        return self.mode <= BuddyMode.IDLE_BEHAVIOR

    def _show_message(self, text: str, seconds: float = 4.5) -> None:
        text = (text or "").strip()
        self.eye_host.show_message(text)
        if text and seconds > 0:
            self._message_timer.start(int(seconds * 1000))

    def _clear_message(self) -> None:
        if self._can_idle():
            self.eye_host.show_message("")

    def _apply_eyes(self, emotion: str, effect: str = "none") -> None:
        self.eye_host.set_state(emotion, effect)

    # ------------------------------------------------------------------ camera
    def update_camera_gaze(self) -> None:
        """Smooth pupil tracking from face_center_x/y — never touches LM Studio."""
        status = self.vision.status()
        if not status.get("enabled"):
            return
        if status.get("face_detected"):
            cx = float(status.get("face_center_x", 0.0))
            cy = float(status.get("face_center_y", 0.0))
            # Estimate frame size from face bbox when available.
            fx = float(status.get("face_x", 0.0))
            fy = float(status.get("face_y", 0.0))
            dist = float(status.get("face_distance", 0.0))
            if dist > 0:
                side = max(40.0, dist ** 0.5)
                fw = max(cx * 2.0, fx + side * 2.5, 640.0)
                fh = max(cy * 2.0, fy + side * 2.5, 480.0)
                self._last_frame_size = (fw, fh)
            self.eye_host.set_gaze(cx, cy, self._last_frame_size[0], self._last_frame_size[1])
            if self._can_idle():
                self.eye_host.roboeyes.set_activity("watching")
        elif self._can_idle():
            self.eye_host.roboeyes.set_activity("idle")

    # ------------------------------------------------------------------ voice / chat
    def on_listen_started(self) -> None:
        self.behavior.mark_interaction()
        self._set_mode(BuddyMode.LISTENING, 12.0)
        self._apply_eyes("listening", "none")
        self._show_message("I'm listening.", 3.0)
        self.sound.play("listening")

    def on_thinking_started(self) -> None:
        self.behavior.mark_interaction()
        self._set_mode(BuddyMode.THINKING, 90.0)
        self._apply_eyes("thinking", "none")
        self._show_message("Hmm... give me a second.", 6.0)
        self.sound.play("thinking")

    def on_ai_response(self, text: str, emotion: str, effect: str, sound: str, action: str) -> None:
        self.behavior.mark_interaction()
        self._set_mode(BuddyMode.RESPONDING, 5.0)
        self._apply_eyes(emotion or "neutral", effect or "none")
        self._show_message(text, 6.0)
        if sound and sound != "none":
            self.sound.play(sound)
        self._apply_action(action)
        QTimer.singleShot(5000, self._release_to_idle)

    def _release_to_idle(self) -> None:
        if self.mode == BuddyMode.RESPONDING and self._now() >= self._mode_until:
            self._set_mode(BuddyMode.IDLE)
            self._apply_eyes("idle", "none")

    def _apply_action(self, action: str) -> None:
        if action in {"stay", "stop"}:
            self.movement.stay()
        elif action == "move_left":
            from PySide6.QtCore import QPoint
            self.movement.move_to(self.buddy_window.pos() + QPoint(-220, 0))
        elif action == "move_right":
            from PySide6.QtCore import QPoint
            self.movement.move_to(self.buddy_window.pos() + QPoint(220, 0))
        elif action == "wander":
            self.movement.wander()
        elif action == "sleep":
            self.movement.sleep()
            self._apply_eyes("sleepy", "close")
        elif action == "wake":
            self.movement.wake()
            self._apply_eyes("happy", "open")

    # ------------------------------------------------------------------ clicks
    def on_body_click(self) -> None:
        now = datetime.now()
        if now - self._last_click < timedelta(seconds=10):
            self._click_count += 1
        else:
            self._click_count = 1
        self._last_click = now
        self.behavior.mark_interaction()
        self._set_mode(BuddyMode.CLICK, 4.0)

        if self._click_count >= 3:
            text, emotion, effect, sound = "Stop poking me.", "angry", "none", "error"
            self._click_count = 0
        elif self._click_count == 2:
            text, emotion, effect, sound = "Stop poking me.", "annoyed", "none", "click"
        else:
            text, emotion, effect, sound = "Hey 👀", "curious", "none", "click"

        self._apply_eyes(emotion, effect)
        self._show_message(text, 3.5)
        self.sound.play(sound)

    # ------------------------------------------------------------------ presence
    def on_presence_state(self, state: str) -> None:
        if state == "PRESENT":
            return
        self._set_mode(BuddyMode.PRESENCE, 8.0)
        mapping = {
            "WATCHING": ("idle", "none", "", None),
            "WAITING": ("idle", "none", "...", None),
            "CURIOUS": ("curious", "none", "Where did you go?", "confused"),
            "CONFUSED": ("confused", "confused", "Hey... where are you?", "confused"),
            "ANNOYED": ("annoyed", "none", "Seriously? Where are you going? 😑", "reaction"),
        }
        entry = mapping.get(state)
        if not entry:
            return
        emotion, effect, message, sound = entry
        self._apply_eyes(emotion, effect)
        self._show_message(message, 5.0)
        if sound:
            self.sound.play(sound)

    def on_presence_returned(self) -> None:
        self._set_mode(BuddyMode.PRESENCE, 4.0)
        self._return_step = 0
        self._apply_eyes("surprised", "none")
        self._show_message("Oh!", 1.2)
        self.sound.play("surprised")
        QTimer.singleShot(900, self._return_happy)
        QTimer.singleShot(2600, self._return_watching)

    def _return_happy(self) -> None:
        self._apply_eyes("happy", "none")
        self._show_message("You're back!", 2.0)
        self.sound.play("happy")

    def _return_watching(self) -> None:
        self._set_mode(BuddyMode.IDLE)
        self._apply_eyes("idle", "none")
        self._clear_message()

    # ------------------------------------------------------------------ alarms / proactive
    def on_alarm(self, alarm: dict) -> None:
        self._set_mode(BuddyMode.ALARM, 6.0)
        kind = alarm.get("type", "reminder")
        if kind == "sleep":
            self.movement.sleep()
            self._apply_eyes("sleepy", "close")
            self._show_message("Time to sleep 😴", 5.0)
            self.sound.play("sleep")
        elif kind == "wake":
            self.movement.wake()
            self._apply_eyes("happy", "open")
            self._show_message("Wake up! ☀️", 5.0)
            self.sound.play("wake")
        else:
            self._apply_eyes("curious", "none")
            self._show_message("Reminder time!", 5.0)
            self.sound.play("notification")

    def on_proactive(self, message: str) -> None:
        self._set_mode(BuddyMode.PROACTIVE, 5.0)
        self._apply_eyes("curious", "none")
        self._show_message(message, 5.0)
        self.sound.play("reaction")

    def on_command_side_effect(self, emotion: str, effect: str, sound: str, message: str) -> None:
        self.behavior.mark_interaction()
        self._set_mode(BuddyMode.RESPONDING, 4.0)
        self._apply_eyes(emotion, effect)
        self._show_message(message, 4.0)
        if sound:
            self.sound.play(sound)

    def on_time_emotion(self, emotion: str) -> None:
        if self._can_idle():
            self._apply_eyes(emotion, "close" if emotion == "sleepy" else "none")

    # ------------------------------------------------------------------ idle behaviors
    def _idle_tick(self) -> None:
        if not self._can_idle():
            return
        status = self.vision.status()
        face = status.get("face_detected", False)
        roll = random.random()
        engine = self.eye_host.roboeyes

        if face and roll < 0.22:
            # Silently look at the user — no message, no sound.
            engine.trigger_idle_behavior("look_at_user")
            return
        if roll < 0.30:
            engine.trigger_idle_behavior("blink")
        elif roll < 0.38:
            engine.trigger_idle_behavior("glance")
        elif roll < 0.44:
            engine.trigger_idle_behavior("look_away")
        elif roll < 0.48:
            engine.trigger_idle_behavior("sleepy")
        elif roll < 0.52:
            engine.trigger_idle_behavior("curious")
        elif roll < 0.55 and face:
            engine.trigger_idle_behavior("playful")
