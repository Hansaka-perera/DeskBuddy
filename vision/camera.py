from __future__ import annotations

import threading
import time

try:
    import cv2
except Exception:
    cv2 = None


class VisionManager:
    def __init__(self) -> None:
        self.enabled = False
        self.running = False
        self.face_count = 0
        self.face_position = "none"
        self.face_detected = False
        self.face_x = self.face_y = self.face_center_x = self.face_center_y = self.face_distance = 0.0
        self._thread = None
        self._cap = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        if cv2 is None:
            return False
        if self.running:
            self.enabled = True
            return True
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap.release()
            return False
        self._cap = cap
        self.running = True
        self.enabled = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self.enabled = False
        self.running = False
        cap = self._cap
        self._cap = None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        with self._lock:
            self.face_count = 0
            self.face_position = "none"
            self.face_detected = False

    def _loop(self) -> None:
        cascade = None
        if cv2 is not None:
            path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(path)
        while self.running and self._cap is not None:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.2)
                continue
            count = 0
            position = "none"
            values = (0.0, 0.0, 0.0, 0.0, 0.0)
            if cascade is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
                count = len(faces)
                if count:
                    x, y, w, h = faces[0]
                    center = x + w / 2; center_y = y + h / 2
                    if center < frame.shape[1] * 0.33:
                        position = "left"
                    elif center > frame.shape[1] * 0.66:
                        position = "right"
                    elif center_y < frame.shape[0] * 0.33:
                        position = "up"
                    elif center_y > frame.shape[0] * 0.66:
                        position = "down"
                    else:
                        position = "center"
                    values = (float(x), float(y), float(center), float(center_y), float(w * h))
            with self._lock:
                self.face_count = count
                self.face_position = position
                self.face_detected = bool(count)
                self.face_x, self.face_y, self.face_center_x, self.face_center_y, self.face_distance = values
            time.sleep(0.12)

    def status(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "running": self.running,
                "face_count": self.face_count,
                "face_position": self.face_position,
                "face_detected": self.face_detected,
                "face_x": self.face_x, "face_y": self.face_y,
                "face_center_x": self.face_center_x, "face_center_y": self.face_center_y,
                "face_distance": self.face_distance,
            }
