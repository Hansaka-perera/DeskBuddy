from __future__ import annotations

from PySide6.QtWidgets import QWidget, QFormLayout, QCheckBox, QSpinBox, QLineEdit, QPushButton, QComboBox, QVBoxLayout


class SettingsWindow(QWidget):
    def __init__(self, settings, on_camera_changed, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.on_camera_changed = on_camera_changed
        self.setWindowTitle("Desk Buddy — Settings")
        self.setMinimumWidth(360)
        form = QFormLayout()
        self.name = QLineEdit(str(settings.get("buddy_name", "Buddy")))
        self.top = QCheckBox(); self.top.setChecked(bool(settings.get("always_on_top", True)))
        self.cam = QCheckBox(); self.cam.setChecked(bool(settings.get("camera_enabled", False)))
        self.mic = QCheckBox(); self.mic.setChecked(bool(settings.get("microphone_enabled", True)))
        self.mem = QCheckBox(); self.mem.setChecked(bool(settings.get("memory_enabled", True)))
        self.proactive = QCheckBox(); self.proactive.setChecked(bool(settings.get("proactive_mode", True)))
        self.idle = QSpinBox(); self.idle.setRange(1, 120); self.idle.setValue(int(settings.get("minimum_idle_minutes", 10)))
        self.maxp = QSpinBox(); self.maxp.setRange(0, 30); self.maxp.setValue(int(settings.get("max_proactive_per_hour", 3)))
        self.provider = QComboBox(); self.provider.addItems(["lmstudio", "ollama", "openai", "none"]); self.provider.setCurrentText(settings.get("ai_provider", "openai"))
        self.hotkey = QLineEdit(str(settings.get("hotkey", "F8")))
        for label, widget in [
            ("Buddy name", self.name), ("Always on top", self.top), ("Camera", self.cam),
            ("Microphone", self.mic), ("Memory", self.mem), ("Proactive mode", self.proactive),
            ("Idle minutes", self.idle), ("Max proactive/hour", self.maxp), ("AI provider", self.provider),
            ("Hotkey", self.hotkey)
        ]:
            form.addRow(label, widget)
        save = QPushButton("Save")
        save.clicked.connect(self.save)
        layout = QVBoxLayout(self); layout.addLayout(form); layout.addWidget(save)

    def save(self):
        self.settings.set("buddy_name", self.name.text().strip() or "Buddy")
        self.settings.set("always_on_top", self.top.isChecked())
        camera = self.cam.isChecked()
        self.settings.set("camera_enabled", camera)
        self.settings.set("microphone_enabled", self.mic.isChecked())
        self.settings.set("memory_enabled", self.mem.isChecked())
        self.settings.set("proactive_mode", self.proactive.isChecked())
        self.settings.set("minimum_idle_minutes", self.idle.value())
        self.settings.set("max_proactive_per_hour", self.maxp.value())
        self.settings.set("ai_provider", self.provider.currentText())
        self.settings.set("hotkey", self.hotkey.text().strip() or "F8")
        self.on_camera_changed(camera)
        self.close()
