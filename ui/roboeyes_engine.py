from __future__ import annotations

from dataclasses import dataclass
import math
import random
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPainterPath


MOODS = {
    "default": "idle", "idle": "idle", "neutral": "idle", "watching": "idle",
    "listening": "listening", "thinking": "thinking",
    "happy": "happy", "playful": "playful", "excited": "happy",
    "sad": "sad", "concerned": "sad", "bored": "sad",
    "angry": "angry", "annoyed": "annoyed", "frustrated": "angry",
    "surprised": "surprised", "confused": "confused", "curious": "curious",
    "sleepy": "sleepy", "tired": "sleepy",
}


@dataclass
class EyeState:
    mood: str = "idle"
    activity: str = "idle"
    effect: str = "none"
    curiosity: bool = False
    sweat: bool = False
    cyclops: bool = False
    blink_until: float = 0.0
    effect_until: float = 0.0
    effect_started: float = 0.0
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    target_gaze_x: float = 0.0
    target_gaze_y: float = 0.0
    idle_gaze_x: float = 0.0
    idle_gaze_y: float = 0.0
    idle_until: float = 0.0
    idle_behavior: str = ""


class RoboEyesEngine:
    """Vector-style robot eyes with smooth gaze tracking and mood animations."""

    def __init__(self, host):
        self.host = host
        self.state = EyeState()
        self.autoblinker = True
        self.blink_interval = 3.2
        self.blink_variation = 2.0
        self.idle_mode = True
        self._effect_amplitude = 2
        self._locked_mood: str | None = None
        self._lock_until = 0.0
        self.last_blink = time.monotonic()
        self.next_blink = self.last_blink + 2.0
        self.frame = 0
        self._pulse = 0.0
        self._smooth = 0.14
        self._jitter_threshold = 0.025
        self.timer = QTimer(host)
        self.timer.timeout.connect(self.update)
        self.timer.start(20)
        self.set_mood("idle")

    # ------------------------------------------------------------------ public API
    def setMood(self, mood: str) -> None:
        self.set_mood(mood)

    def set_mood(self, mood: str) -> None:
        key = str(mood).lower()
        self.state.mood = MOODS.get(key, "idle")
        self.host.update()

    def set_activity(self, activity: str) -> None:
        self.state.activity = str(activity).lower()
        self.host.update()

    def setPosition(self, position: str) -> None:
        """Legacy coarse direction — converted to gaze offset."""
        offsets = {
            "center": (0.0, 0.0), "n": (0.0, -0.55), "ne": (0.45, -0.45),
            "e": (0.65, 0.0), "se": (0.45, 0.45), "s": (0.0, 0.55),
            "sw": (-0.45, 0.45), "w": (-0.65, 0.0), "nw": (-0.45, -0.45),
        }
        gx, gy = offsets.get(str(position).lower(), (0.0, 0.0))
        self.state.target_gaze_x = gx
        self.state.target_gaze_y = gy
        self.host.update()

    def set_gaze_target(self, nx: float, ny: float) -> None:
        """Normalized gaze target in roughly -1..1."""
        dx = nx - self.state.target_gaze_x
        dy = ny - self.state.target_gaze_y
        if abs(dx) < self._jitter_threshold and abs(dy) < self._jitter_threshold:
            return
        self.state.target_gaze_x = max(-1.0, min(1.0, nx))
        self.state.target_gaze_y = max(-1.0, min(1.0, ny))
        self.host.update()

    def setAutoblinker(self, active: bool, interval: float | None = None, variation: float | None = None) -> None:
        self.autoblinker = bool(active)
        if interval is not None:
            self.blink_interval = max(0.2, float(interval))
        if variation is not None:
            self.blink_variation = max(0.0, float(variation))

    def setIdleMode(self, active: bool, interval: float | None = None, variation: float | None = None) -> None:
        self.idle_mode = bool(active)

    def setCuriosity(self, active: bool) -> None:
        self.state.curiosity = bool(active)
        self.host.update()

    def setCyclops(self, active: bool) -> None:
        self.state.cyclops = bool(active)
        self.host.update()

    def setSweat(self, active: bool) -> None:
        self.state.sweat = bool(active)
        self.host.update()

    def blink(self) -> None:
        self.state.blink_until = time.monotonic() + 0.14
        self.host.update()

    def close(self) -> None:
        self.state.blink_until = time.monotonic() + 60.0
        self.host.update()

    def open(self) -> None:
        self.state.blink_until = 0.0
        self.host.update()

    def anim_confused(self) -> None:
        self._start_effect("confused", 0.75)

    def anim_laugh(self) -> None:
        self._start_effect("laugh", 0.7)

    def flicker(self, horizontal: bool = True, amplitude: int = 2) -> None:
        self._start_effect("h_flicker" if horizontal else "v_flicker", 0.5, amplitude=max(1, int(amplitude)))

    def trigger_idle_behavior(self, name: str) -> None:
        now = time.monotonic()
        behaviors = {
            "blink": lambda: self.blink(),
            "glance": lambda: self._idle_look(random.uniform(-0.5, 0.5), random.uniform(-0.3, 0.3), 1.2),
            "look_away": lambda: self._idle_look(random.choice([-0.75, 0.75]), random.uniform(-0.1, 0.2), 1.8),
            "look_at_user": lambda: self._idle_look(0.0, 0.0, 2.5),
            "sleepy": lambda: (self.set_mood("sleepy"), self._start_effect("slow_blink", 2.0)),
            "curious": lambda: (self.set_mood("curious"), self.setCuriosity(True)),
            "playful": lambda: (self.set_mood("playful"), self._start_effect("playful", 1.4)),
        }
        fn = behaviors.get(name)
        if fn:
            self.state.idle_behavior = name
            self.state.idle_until = now + 2.0
            fn()
            self.host.update()

    def apply_effect(self, effect: str | None) -> None:
        e = (effect or "none").lower().replace("-", "_").strip()
        if e in {"none", "neutral", ""}:
            return
        mapping = {
            "blink": lambda: self.blink(),
            "laugh": lambda: self.anim_laugh(),
            "confused": lambda: self.anim_confused(),
            "flicker": lambda: self.flicker(True, 2),
            "h_flicker": lambda: self.flicker(True, 2),
            "v_flicker": lambda: self.flicker(False, 3),
            "sweat": lambda: (self.setSweat(True), self._start_effect("sweat", 1.6)),
            "close": lambda: self.close(),
            "open": lambda: self.open(),
            "curious": lambda: self.setCuriosity(True),
        }
        if e in mapping:
            mapping[e]()
        if e == "curious":
            self.setCuriosity(True)

    def set_state(self, emotion: str | None, effect: str | None) -> None:
        emotion = (emotion or "idle").lower().strip()
        self.set_mood(emotion)
        if emotion == "curious":
            self.setCuriosity(True)
        elif emotion not in {"curious"}:
            self.setCuriosity(False)
        if emotion == "confused" and (not effect or effect == "none"):
            self.anim_confused()
        elif emotion == "surprised" and (not effect or effect in {"none", "blink"}):
            self._start_effect("surprised_pop", 0.55)
        elif emotion == "sleepy" and (not effect or effect in {"none", "close"}):
            self._start_effect("slow_blink", 2.5)
        elif emotion == "thinking" and (not effect or effect == "none"):
            self._start_effect("thinking", 30.0)
        elif emotion == "listening" and (not effect or effect == "none"):
            self._start_effect("listening", 30.0)
        elif emotion == "playful" and (not effect or effect in {"none", "laugh"}):
            self._start_effect("playful", 2.0)
        elif emotion == "angry" and (not effect or effect == "none"):
            self._start_effect("angry_pulse", 3.0)
        elif emotion == "annoyed" and (not effect or effect == "none"):
            self._start_effect("annoyed", 2.5)
        if effect and effect not in {"none", "blink"}:
            self.apply_effect(effect)

    # ------------------------------------------------------------------ internals
    def _idle_look(self, gx: float, gy: float, duration: float) -> None:
        self.state.idle_gaze_x = gx
        self.state.idle_gaze_y = gy
        self.state.idle_until = time.monotonic() + duration

    def _start_effect(self, effect: str, duration: float, amplitude: int = 2) -> None:
        now = time.monotonic()
        self.state.effect = effect
        self.state.effect_started = now
        self.state.effect_until = now + duration
        self._effect_amplitude = amplitude
        self.host.update()

    def _schedule_blink(self, now: float) -> None:
        extra = random.uniform(-self.blink_variation, self.blink_variation)
        self.next_blink = now + max(0.55, self.blink_interval + extra)

    def _smooth_gaze(self) -> None:
        now = time.monotonic()
        tx, ty = self.state.target_gaze_x, self.state.target_gaze_y
        if now < self.state.idle_until and self.state.idle_behavior:
            tx = self.state.idle_gaze_x
            ty = self.state.idle_gaze_y
        if self.state.mood == "thinking":
            tx = min(tx, -0.15)
            ty = min(ty, -0.25)
        elif self.state.mood == "annoyed":
            tx += 0.35
        self.state.gaze_x += (tx - self.state.gaze_x) * self._smooth
        self.state.gaze_y += (ty - self.state.gaze_y) * self._smooth

    def update(self) -> None:
        now = time.monotonic()
        self.frame += 1
        self._pulse = (math.sin(now * 2.4) + 1.0) / 2.0
        self._smooth_gaze()

        if self.autoblinker and now >= self.next_blink and self.state.mood not in {"sleepy"}:
            if random.random() < 0.85:
                self.blink()
            self._schedule_blink(now)

        if self.state.effect and now >= self.state.effect_until:
            if self.state.effect == "sweat":
                self.state.sweat = False
            if self.state.effect in {"listening", "thinking", "angry_pulse"}:
                pass  # mood-driven; refresh handled by set_state
            else:
                self.state.effect = ""
            if self.state.idle_behavior and now >= self.state.idle_until:
                self.state.idle_behavior = ""
                self.setCuriosity(False)
                if self.state.mood in {"curious", "playful", "sleepy"} and self.state.activity == "idle":
                    self.set_mood("idle")

        if self.state.blink_until and self.state.blink_until <= now:
            self.state.blink_until = 0.0

        self.host.update()

    def paint(self, painter: QPainter, rect) -> None:
        w, h = rect.width(), rect.height()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        eye_area_h = max(65, int(h * 0.68))
        cx = w / 2.0
        cy = eye_area_h / 2.0
        mood = self.state.mood
        now = time.monotonic()

        base_r = min(22.0, w * 0.12)
        gap = min(28.0, w * 0.13)
        gx = self.state.gaze_x
        gy = self.state.gaze_y

        shake_x = shake_y = 0.0
        eff = self.state.effect
        t = now - self.state.effect_started
        if eff == "confused":
            shake_x = math.sin(t * 38.0) * 3.5
            if int(t * 6) % 2:
                gx += 0.12
        elif eff == "laugh" or eff == "playful":
            shake_y = math.sin(t * 28.0) * 2.5
        elif eff == "h_flicker":
            shake_x = math.sin(t * 65.0) * float(self._effect_amplitude)
        elif eff == "v_flicker":
            shake_y = math.sin(t * 65.0) * float(self._effect_amplitude)

        scale = 1.0
        if mood == "surprised" or eff == "surprised_pop":
            scale = 1.18 + 0.06 * math.sin(t * 18.0)
        elif mood == "listening" or eff == "listening":
            scale = 1.06 + 0.03 * self._pulse
        elif mood == "sleepy" or eff == "slow_blink":
            scale = 0.92
        elif mood == "angry" or eff == "angry_pulse":
            scale = 0.94 + 0.02 * math.sin(t * 12.0)

        blink_t = 0.0
        if self.state.blink_until > now:
            blink_t = min(1.0, (self.state.blink_until - now) / 0.14)
        if eff == "slow_blink":
            blink_t = max(blink_t, 0.45 + 0.4 * math.sin(t * 3.2))
        if mood == "annoyed" or eff == "annoyed":
            blink_t = max(blink_t, 0.35)
        if mood == "sleepy":
            blink_t = max(blink_t, 0.25 + 0.15 * self._pulse)

        left_cx = cx - gap / 2.0 - base_r + shake_x
        right_cx = cx + gap / 2.0 + base_r + shake_x
        eye_cy = cy + shake_y

        if self.state.cyclops:
            self._draw_vector_eye(painter, cx + shake_x, eye_cy, base_r * scale, gx, gy, mood, blink_t, left=True)
        else:
            self._draw_vector_eye(painter, left_cx, eye_cy, base_r * scale, gx, gy, mood, blink_t, left=True)
            self._draw_vector_eye(painter, right_cx, eye_cy, base_r * scale, gx, gy, mood, blink_t, left=False)

        if self.state.sweat:
            self._draw_sweat(painter, w, eye_area_h)

    def _draw_vector_eye(self, painter, cx, cy, radius, gx, gy, mood, blink_t, left=True):
        r = max(8.0, radius)
        pupil_off = r * 0.28
        px = cx + gx * pupil_off
        py = cy + gy * pupil_off

        # Outer shell — dark ring like a small robot visor
        shell = QColor(18, 22, 32, 240)
        sclera = QColor(235, 240, 252, 250)
        pupil = QColor(20, 28, 42, 255)
        accent = QColor(70, 180, 255, 200)

        if mood == "angry":
            sclera = QColor(255, 220, 220, 250)
            accent = QColor(255, 90, 100, 220)
            pupil = QColor(60, 10, 15, 255)
        elif mood == "annoyed":
            sclera = QColor(220, 225, 235, 245)
            accent = QColor(180, 140, 90, 180)
        elif mood == "happy" or mood == "playful":
            sclera = QColor(245, 252, 255, 250)
            accent = QColor(100, 210, 255, 220)
        elif mood == "sad" or mood == "concerned":
            sclera = QColor(200, 210, 225, 230)
            accent = QColor(120, 150, 190, 160)
        elif mood == "sleepy":
            sclera = QColor(190, 200, 215, 220)
            accent = QColor(130, 160, 190, 140)

        # Mood-specific lid tilt before drawing sclera
        lid_slant = 0.0
        if mood == "angry":
            lid_slant = -7.0 if left else 7.0
        elif mood == "sad":
            lid_slant = 5.0 if left else -5.0

        painter.save()
        painter.translate(cx, cy)
        if lid_slant:
            painter.rotate(lid_slant)
        painter.translate(-cx, -cy)

        # Shell ring
        painter.setPen(QPen(shell, 2.5))
        painter.setBrush(QBrush(shell))
        painter.drawEllipse(int(cx - r - 2), int(cy - r - 2), int((r + 2) * 2), int((r + 2) * 2))

        if mood == "happy" and blink_t < 0.2:
            # Happy arc eyes
            painter.setPen(QPen(accent, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(int(cx - r), int(cy - r * 0.2), int(r * 2), int(r * 1.5), 30 * 16, 120 * 16)
            painter.restore()
            return

        # Sclera
        open_h = max(2.0, (1.0 - blink_t) * r * 2.0)
        if mood == "sleepy":
            open_h *= 0.72
        if mood == "listening":
            open_h *= 1.08

        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.setBrush(QBrush(sclera))
        if blink_t > 0.05:
            # Draw as clipped ellipse for blink
            path = QPainterPath()
            path.addEllipse(cx - r, cy - open_h / 2.0, r * 2, open_h)
            painter.drawPath(path)
        else:
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        if blink_t < 0.85 and open_h > r * 0.35:
            pr = r * (0.38 if mood != "surprised" else 0.28)
            if mood == "angry":
                pr *= 0.75
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(pupil))
            painter.drawEllipse(int(px - pr), int(py - pr), int(pr * 2), int(pr * 2))
            # Catch light
            painter.setBrush(QBrush(QColor(255, 255, 255, 150)))
            painter.drawEllipse(int(px - pr * 0.5), int(py - pr * 0.6), int(pr * 0.45), int(pr * 0.45))
            # Iris ring
            painter.setPen(QPen(accent, 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(int(px - pr * 1.15), int(py - pr * 1.15), int(pr * 2.3), int(pr * 2.3))

        # Upper lid for blink / annoyed / sleepy
        if blink_t > 0.08 or mood in {"annoyed", "sleepy"}:
            lid_cover = blink_t
            if mood == "annoyed":
                lid_cover = max(lid_cover, 0.42)
            if mood == "sleepy":
                lid_cover = max(lid_cover, 0.38)
            lid_h = lid_cover * r * 1.6
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(18, 22, 32, 230)))
            painter.drawRect(int(cx - r - 3), int(cy - r - 3), int(r * 2 + 6), int(lid_h))

        # Angry brow
        if mood == "angry":
            painter.setPen(QPen(QColor(255, 80, 90, 230), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            bx1, by1 = cx - r * 0.7, cy - r * 0.95
            bx2, by2 = cx + r * 0.5, cy - r * 0.55
            if not left:
                bx1, bx2 = cx - r * 0.5, cx + r * 0.7
                by1, by2 = cy - r * 0.55, cy - r * 0.95
            painter.drawLine(int(bx1), int(by1), int(bx2), int(by2))

        painter.restore()

    def _draw_sweat(self, painter, w, eye_area_h):
        painter.setPen(QPen(QColor(110, 200, 255, 220), 1))
        painter.setBrush(QBrush(QColor(90, 190, 255, 120)))
        x = w * 0.82
        y = eye_area_h * 0.17
        painter.drawEllipse(int(x), int(y), 6, 10)
        painter.drawEllipse(int(x + 10), int(y + 12), 4, 7)
