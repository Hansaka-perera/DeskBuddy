from __future__ import annotations

from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QLineEdit, QPushButton, QLabel


class AIWorker(QThread):
    result = Signal(str)

    def __init__(self, brain, text: str, parent=None):
        super().__init__(parent)
        self.brain = brain
        self.text = text

    def run(self):
        try:
            self.result.emit(self.brain.respond(self.text))
        except Exception as exc:
            self.result.emit(f"Something broke: {exc}")


class ChatWindow(QWidget):
    message_ready = Signal(str, str)

    def __init__(self, brain, behavior, stt, controller=None, command_handler=None, parent=None):
        super().__init__(parent)
        self.brain = brain
        self.behavior = behavior
        self.stt = stt
        self.controller = controller
        self.command_handler = command_handler
        self.worker = None
        self.setWindowTitle("Desk Buddy — Chat")
        self.resize(420, 560)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        self.status = QLabel("Ready")
        self.history = QTextBrowser()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Talk to Buddy…")
        send = QPushButton("Send")
        listen = QPushButton("🎤")
        row = QHBoxLayout()
        row.addWidget(self.input, 1)
        row.addWidget(listen)
        row.addWidget(send)
        layout.addWidget(self.status)
        layout.addWidget(self.history, 1)
        layout.addLayout(row)
        send.clicked.connect(self.send)
        self.input.returnPressed.connect(self.send)
        listen.clicked.connect(self.listen)

    def send(self):
        text = self.input.text().strip()
        if not text or (self.worker and self.worker.isRunning()):
            return
        self.input.clear()
        self.history.append(f"<b>You:</b> {text}")
        self.status.setText("Buddy is thinking…")
        self.behavior.mark_interaction()
        if self.command_handler:
            command_response = self.command_handler(text)
            if command_response:
                self._response(command_response, from_command=True)
                return
        if self.controller:
            self.controller.on_thinking_started()
        self.worker = AIWorker(self.brain, text, self)
        self.worker.result.connect(self._response)
        self.worker.start()

    def _response(self, text: str, from_command: bool = False):
        self.history.append(f"<b>Buddy:</b> {text}")
        self.status.setText("Ready")
        self.message_ready.emit("assistant", text)
        if self.controller:
            if from_command:
                self.controller.on_ai_response(text, "happy", "none", "click", "normal")
            else:
                self.controller.on_ai_response(
                    text,
                    self.brain.last_emotion,
                    self.brain.last_effect,
                    self.brain.last_sound,
                    self.brain.last_action,
                )

    def listen(self):
        if not self.brain.settings.get("microphone_enabled", True):
            self.status.setText("Microphone is disabled in Settings.")
            return
        self.status.setText("Listening…")
        if self.controller:
            self.controller.on_listen_started()
        self.stt.listen_once(self._voice_result, self._voice_error)

    def _voice_result(self, text):
        self.input.setText(text)
        self.send()

    def _voice_error(self, error):
        self.status.setText(f"Voice: {error}")
        if self.controller:
            self.controller.on_command_side_effect("confused", "none", "error", f"Voice: {error}")
