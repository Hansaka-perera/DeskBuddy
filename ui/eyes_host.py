from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPen
from PySide6.QtWidgets import QWidget

from .roboeyes_engine import RoboEyesEngine


class EyeHost(QWidget):
    """184x120 vector robot face with compact pixel-style status text."""

    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._emotion = "idle"
        self._effect = "none"
        self._message = ""
        self.roboeyes = RoboEyesEngine(self)

    def set_emotion(self, emotion: str) -> None:
        self._emotion = (emotion or "idle").lower()
        self.roboeyes.set_state(self._emotion, self._effect)
        self.update()

    def set_effect(self, effect: str) -> None:
        self._effect = (effect or "none").lower()
        self.roboeyes.apply_effect(self._effect)
        self.update()

    def set_state(self, emotion: str, effect: str = "none") -> None:
        self._emotion = (emotion or "idle").lower()
        self._effect = (effect or "none").lower()
        self.roboeyes.set_state(self._emotion, self._effect)
        self.update()

    def set_direction(self, direction: str) -> None:
        """Legacy coarse camera hook."""
        mapping = {"left": "w", "right": "e", "up": "n", "down": "s", "center": "center"}
        self.roboeyes.setPosition(mapping.get((direction or "").lower(), "center"))

    def set_gaze(self, face_cx: float, face_cy: float, frame_w: float, frame_h: float) -> None:
        """Map camera face center to smooth normalized gaze."""
        if frame_w <= 0 or frame_h <= 0:
            return
        nx = (face_cx / frame_w - 0.5) * 2.2
        ny = (face_cy / frame_h - 0.5) * 2.0
        self.roboeyes.set_gaze_target(nx, ny)

    def show_message(self, text: str) -> None:
        self._message = (text or "").strip()
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.roboeyes.paint(painter, self.rect())

        if self._message:
            text_rect = QRectF(6, self.height() * 0.70, self.width() - 12, self.height() * 0.28)
            font = QFont("Consolas")
            if not font.exactMatch():
                font = QFont("Courier New")
            font.setPixelSize(9)
            font.setStyleHint(QFont.StyleHint.Monospace)
            painter.setFont(font)
            fm = QFontMetrics(font)
            display = fm.elidedText(" ".join(self._message.split()), Qt.TextElideMode.ElideRight, int(text_rect.width()))
            painter.setPen(QPen(QColor(160, 210, 255, 210), 1))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, display)
        painter.end()
