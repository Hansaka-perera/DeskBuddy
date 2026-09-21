from __future__ import annotations

import random
from enum import Enum

from PySide6.QtCore import QObject, QPoint, QPropertyAnimation, Signal
from PySide6.QtWidgets import QApplication, QWidget


class MovementState(str, Enum):
    WANDER = "WANDER"
    MOVING = "MOVING"
    STAY = "STAY"
    FOLLOW = "FOLLOW"
    SLEEP = "SLEEP"


class MovementController(QObject):
    """Moves the buddy inside a screen's available (taskbar-safe) geometry."""

    state_changed = Signal(str)

    def __init__(self, window: QWidget, settings, parent=None):
        super().__init__(parent or window)
        self.window, self.settings = window, settings
        self.state = MovementState.STAY
        self._animation: QPropertyAnimation | None = None

    def _screen(self):
        return QApplication.screenAt(self.window.frameGeometry().center()) or QApplication.primaryScreen()

    def _safe_point(self, point: QPoint) -> QPoint:
        screen = self._screen()
        if not screen:
            return point
        area = screen.availableGeometry()
        return QPoint(
            max(area.left(), min(point.x(), area.right() - self.window.width() + 1)),
            max(area.top(), min(point.y(), area.bottom() - self.window.height() + 1)),
        )

    def move_to(self, point: QPoint, state: MovementState = MovementState.MOVING) -> None:
        if self.state == MovementState.SLEEP:
            return
        target = self._safe_point(point)
        self.stop_animation()
        distance = (target - self.window.pos()).manhattanLength()
        speed = max(40, int(self.settings.get("movement_speed", 180)))
        animation = QPropertyAnimation(self.window, b"pos", self)
        animation.setStartValue(self.window.pos())
        animation.setEndValue(target)
        animation.setDuration(max(180, min(3500, int(distance / speed * 1000))))
        animation.finished.connect(self._remember_position)
        self._animation = animation
        self._set_state(state)
        animation.start()

    def wander(self) -> None:
        if not self.settings.get("movement_enabled", True) or self.state == MovementState.SLEEP:
            return
        screen = self._screen()
        if not screen:
            return
        area = screen.availableGeometry()
        self.move_to(QPoint(
            random.randint(area.left(), max(area.left(), area.right() - self.window.width() + 1)),
            random.randint(area.top(), max(area.top(), area.bottom() - self.window.height() + 1)),
        ), MovementState.WANDER)

    def stop_animation(self) -> None:
        if self._animation and self._animation.state():
            self._animation.stop()
        self._animation = None

    def stay(self) -> None:
        self.stop_animation()
        self._set_state(MovementState.STAY)
        self._remember_position()

    def sleep(self) -> None:
        self.stop_animation()
        self._set_state(MovementState.SLEEP)
        self._remember_position()

    def wake(self) -> None:
        if self.state == MovementState.SLEEP:
            self._set_state(MovementState.STAY)

    def _set_state(self, state: MovementState) -> None:
        self.state = state
        self.settings.set("movement_state", state.value)
        self.state_changed.emit(state.value)

    def _remember_position(self) -> None:
        screen = self._screen()
        self.settings.data["position"] = {
            "x": self.window.x(), "y": self.window.y(),
            "screen": screen.name() if screen else "primary", "movement_state": self.state.value,
        }
        self.settings.save()
