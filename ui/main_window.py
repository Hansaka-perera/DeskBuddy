from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QAction, QColor, QPainter, QBrush, QPen, QIcon
from PySide6.QtWidgets import QMainWindow, QMenu, QSystemTrayIcon, QApplication

from .eyes_host import EyeHost


class BuddyWindow(QMainWindow):
    open_chat = Signal()
    open_settings = Signal()
    toggle_camera = Signal()
    listen = Signal()
    buddy_clicked = Signal()
    closed = Signal()

    WIDTH = 184
    HEIGHT = 120

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._drag_offset = QPoint()
        self._dragging = False
        self.WIDTH = int(settings.get("window_width", 184))
        self.HEIGHT = int(settings.get("window_height", 120))
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.eye_host = EyeHost(self)
        self.setCentralWidget(self.eye_host)
        self.eye_host.installEventFilter(self)
        self._create_tray()

    def _create_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        self.tray.setIcon(icon)
        menu = QMenu()
        chat = QAction("Chat", self)
        chat.triggered.connect(self.open_chat)
        settings = QAction("Settings", self)
        settings.triggered.connect(self.open_settings)
        camera = QAction("Toggle Camera", self)
        camera.triggered.connect(self.toggle_camera)
        listen = QAction("Listen", self)
        listen.triggered.connect(self.listen)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        for a in (chat, settings, camera, listen):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def set_emotion(self, emotion: str) -> None:
        self.eye_host.set_emotion(emotion)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QBrush(QColor(10, 12, 18, 232)))
        painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
        painter.drawRoundedRect(rect, 18, 18)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def eventFilter(self, watched, event):
        """Proxy events from the full-size face widget so borderless dragging works."""
        if watched is self.eye_host:
            if event.type() == event.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._dragging = True
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self._drag_start = event.globalPosition().toPoint()
                return True
            if event.type() == event.Type.MouseMove and self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                return True
            if event.type() == event.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                was_click = (event.globalPosition().toPoint() - getattr(self, "_drag_start", event.globalPosition().toPoint())).manhattanLength() < 5
                self._dragging = False
                if was_click:
                    self.buddy_clicked.emit()
                return True
        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_chat.emit()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        chat = menu.addAction("Chat")
        listen = menu.addAction("Listen")
        camera = menu.addAction("Toggle Camera")
        settings = menu.addAction("Settings")
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        action = menu.exec(pos)
        if action == chat:
            self.open_chat.emit()
        elif action == listen:
            self.listen.emit()
        elif action == camera:
            self.toggle_camera.emit()
        elif action == settings:
            self.open_settings.emit()
        elif action == quit_action:
            QApplication.quit()

    def closeEvent(self, event):
        self.tray.hide()
        self.closed.emit()
        super().closeEvent(event)
