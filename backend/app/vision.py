import os, time, threading
from collections import deque
from datetime import datetime
import cv2
import numpy as np

# MediaPipe's legacy FaceMesh API is used for broad version compatibility.
try:
    import mediapipe as mp
except Exception:
    mp = None

# FaceMesh landmark indices: standard eye contours and mouth landmarks.
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [13, 14, 78, 308]

def _dist(a, b):
    return float(np.linalg.norm(np.array(a, dtype=float) - np.array(b, dtype=float)))

def _ear(points, idx):
    p = [points[i] for i in idx]
    denom = 2.0 * _dist(p[0], p[3])
    if denom < 1e-6: return None
    return (_dist(p[1], p[5]) + _dist(p[2], p[4])) / denom

def _mar(points):
    # A simplified mouth-opening ratio, intended only as a heuristic.
    vertical = _dist(points[MOUTH[0]], points[MOUTH[1]])
    horizontal = _dist(points[MOUTH[2]], points[MOUTH[3]])
    return vertical / horizontal if horizontal > 1e-6 else None

class VisionEngine:
    def __init__(self, camera_index=0, ear_threshold=0.21, mar_threshold=0.65, perclos_window=60):
        self.camera_index = camera_index
        self.ear_threshold = ear_threshold
        self.mar_threshold = mar_threshold
        self.window_seconds = perclos_window
        self.lock = threading.RLock()
        self.cap = None
        self.mesh = None
        self.active = False
        self.last_jpeg = None
        self.samples = deque()
        self.closed_since = None
        self.blink_count = 0
        self.blink_events = deque()
        self.yawn_count = 0
        self.yawn_since = None
        self.last_sample_time = 0
        self.status = {
            "monitoring": False, "camera_connected": False, "face_detected": False,
            "ear": None, "mar": None, "blink_rate": None, "perclos": None,
            "possible_yawns": 0, "experimental_score": None, "eye_closed": False,
            "status": "Camera is off", "fps": 0.0, "updated_at": None,
            "note": "Metrics are heuristic research indicators, not validated drowsiness detection."
        }
        self._prev_time = None
        self._fps = 0.0

    def start(self):
        with self.lock:
            if self.active: return {"ok": True, "message": "Monitoring already active"}
            if mp is None:
                raise RuntimeError("MediaPipe could not be imported. Check installation and Python version.")
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
            if not cap.isOpened():
                cap.release()
                raise RuntimeError(f"Could not open camera index {self.camera_index}. Check permissions or try CAMERA_INDEX=1.")
            self.cap = cap
            self.mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False, max_num_faces=1, refine_landmarks=True,
                min_detection_confidence=0.5, min_tracking_confidence=0.5
            )
            self.active = True
            self.samples.clear(); self.blink_events.clear()
            self.blink_count = 0; self.yawn_count = 0
            self.closed_since = None; self.yawn_since = None
            self.status.update({"monitoring": True, "camera_connected": True, "status": "Monitoring", "note": "Camera is processed locally; raw frames are not stored."})
        return {"ok": True, "message": "Monitoring started"}

    def stop(self):
        with self.lock:
            self.active = False
            if self.cap is not None:
                self.cap.release(); self.cap = None
            if self.mesh is not None:
                self.mesh.close(); self.mesh = None
            self.status.update({"monitoring": False, "camera_connected": False, "status": "Camera is off"})
        return {"ok": True, "message": "Monitoring stopped"}

    def read_frame(self):
        with self.lock:
            if not self.active or self.cap is None:
                return None
            cap = self.cap
        ok, frame = cap.read()
        if not ok: return None
        frame = cv2.flip(frame, 1)
        now = time.time()
        if self._prev_time:
            instant = 1.0 / max(now - self._prev_time, 1e-6)
            self._fps = instant if not self._fps else 0.85 * self._fps + 0.15 * instant
        self._prev_time = now
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.mesh.process(rgb)
        face = bool(result.multi_face_landmarks)
        ear = mar = None
        eye_closed = False
        if face:
            lm = result.multi_face_landmarks[0].landmark
            h, w = frame.shape[:2]
            pts = [(p.x * w, p.y * h) for p in lm]
            left, right = _ear(pts, LEFT_EYE), _ear(pts, RIGHT_EYE)
            vals = [x for x in (left, right) if x is not None]
            ear = float(sum(vals) / len(vals)) if vals else None
            mar = _mar(pts)
            eye_closed = ear is not None and ear < self.ear_threshold
            # Draw landmarks and contours for visible debugging feedback.
            for group in (LEFT_EYE, RIGHT_EYE, MOUTH):
                for i in group:
                    x, y = map(int, pts[i])
                    cv2.circle(frame, (x, y), 2, (70, 220, 235), -1)
            cv2.putText(frame, f"EAR: {ear:.3f}" if ear is not None else "EAR: --", (18, 32), cv2.FONT_HERSHEY_SIMPLEX, .7, (70,220,235), 2)
            cv2.putText(frame, "EYES CLOSED" if eye_closed else "EYES OPEN", (18, 62), cv2.FONT_HERSHEY_SIMPLEX, .65, (60,210,120) if not eye_closed else (40,70,255), 2)
        self._update_metrics(now, face, ear, mar, eye_closed)
        ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        with self.lock:
            if ok: self.last_jpeg = jpg.tobytes()
        return frame

    def _update_metrics(self, now, face, ear, mar, eye_closed):
        with self.lock:
            self.samples.append((now, bool(eye_closed), bool(face)))
            while self.samples and now - self.samples[0][0] > self.window_seconds:
                self.samples.popleft()
            if eye_closed:
                if self.closed_since is None: self.closed_since = now
            elif self.closed_since is not None:
                closed_duration = now - self.closed_since
                if 0.08 <= closed_duration <= 1.5:
                    self.blink_events.append(now)
                    self.blink_count += 1
                self.closed_since = None
            while self.blink_events and now - self.blink_events[0] > 60:
                self.blink_events.popleft()
            # A possible yawn is counted only after a sustained high MAR heuristic.
            if mar is not None and mar > self.mar_threshold:
                if self.yawn_since is None: self.yawn_since = now
                elif now - self.yawn_since > 1.2:
                    if not getattr(self, "_yawn_latched", False):
                        self.yawn_count += 1; self._yawn_latched = True
            else:
                self.yawn_since = None
                self._yawn_latched = False
            perclos = (100.0 * sum(1 for _, closed, f in self.samples if f and closed) /
                       max(1, sum(1 for _, _, f in self.samples if f))) if any(f for _,_,f in self.samples) else None
            blink_rate = float(len(self.blink_events))
            # A transparent, heuristic indicator; not trained or clinically validated.
            score = None
            if face and perclos is not None:
                score = max(0.0, min(100.0, 0.7 * perclos + (15 if self.closed_since and now-self.closed_since > 1 else 0) + min(15, self.yawn_count*2)))
            self.status.update({
                "monitoring": self.active, "camera_connected": self.active, "face_detected": face,
                "ear": round(ear, 4) if ear is not None else None,
                "mar": round(mar, 4) if mar is not None else None,
                "blink_rate": round(blink_rate, 1), "perclos": round(perclos, 2) if perclos is not None else None,
                "possible_yawns": self.yawn_count, "experimental_score": round(score, 1) if score is not None else None,
                "eye_closed": bool(eye_closed), "status": "Face detected" if face else "No face detected",
                "fps": round(self._fps, 1), "updated_at": datetime.utcnow().isoformat() + "Z",
                "note": "Heuristic research indicators only; not validated for driving or clinical use."
            })

    def get_status(self):
        with self.lock:
            return dict(self.status)

    def get_jpeg(self):
        with self.lock:
            return self.last_jpeg
