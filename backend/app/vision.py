
import threading
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np

try:
    import mediapipe as mp
except Exception:
    mp = None


# MediaPipe FaceMesh landmark indices
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [13, 14, 78, 308]


def _dist(a, b):
    return float(
        np.linalg.norm(
            np.array(a, dtype=float)
            - np.array(b, dtype=float)
        )
    )


def _ear(points, indices):
    p = [points[i] for i in indices]

    denominator = 2.0 * _dist(p[0], p[3])

    if denominator < 1e-6:
        return None

    return (
        _dist(p[1], p[5])
        + _dist(p[2], p[4])
    ) / denominator


def _mar(points):
    vertical = _dist(
        points[MOUTH[0]],
        points[MOUTH[1]],
    )

    horizontal = _dist(
        points[MOUTH[2]],
        points[MOUTH[3]],
    )

    return (
        vertical / horizontal
        if horizontal > 1e-6
        else None
    )


class VisionEngine:
    """
    Processes frames supplied by the browser webcam.

    This class deliberately does not open cv2.VideoCapture(),
    because the Render server cannot directly access the
    user's laptop webcam.
    """

    def __init__(
        self,
        camera_index=0,
        ear_threshold=0.21,
        mar_threshold=0.65,
        perclos_window=60,
    ):
        # Retained for compatibility with existing configuration.
        self.camera_index = camera_index

        self.ear_threshold = ear_threshold
        self.mar_threshold = mar_threshold
        self.window_seconds = perclos_window

        self.lock = threading.RLock()

        self.mesh = None
        self.active = False
        self.last_jpeg = None

        self.samples = deque()
        self.blink_events = deque()

        self.closed_since = None
        self.blink_count = 0

        self.yawn_count = 0
        self.yawn_since = None
        self.yawn_latched = False

        self.prev_time = None
        self.fps = 0.0

        self.status = {
            "monitoring": False,
            "camera_connected": False,
            "face_detected": False,
            "ear": None,
            "mar": None,
            "blink_rate": None,
            "perclos": None,
            "possible_yawns": 0,
            "experimental_score": None,
            "eye_closed": False,
            "status": "Camera is off",
            "fps": 0.0,
            "updated_at": None,
            "note": (
                "Metrics are heuristic research indicators, "
                "not validated drowsiness detection."
            ),
        }

    def start_browser(self):
        """
        Initialize MediaPipe without opening a server-side camera.
        Called by POST /api/monitoring/start.
        """
        with self.lock:
            if self.active:
                return {
                    "ok": True,
                    "message": "Monitoring already active",
                }

            if mp is None:
                raise RuntimeError(
                    "MediaPipe could not be imported. "
                    "Check the backend dependencies."
                )

            try:
                self.mesh = (
                    mp.solutions.face_mesh.FaceMesh(
                        static_image_mode=False,
                        max_num_faces=1,
                        refine_landmarks=True,
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                )

            except Exception as exc:
                self.mesh = None

                raise RuntimeError(
                    "Could not initialize MediaPipe FaceMesh: "
                    + str(exc)
                ) from exc

            self.active = True

            self.samples.clear()
            self.blink_events.clear()

            self.blink_count = 0
            self.yawn_count = 0

            self.closed_since = None
            self.yawn_since = None
            self.yawn_latched = False

            self.prev_time = None
            self.fps = 0.0
            self.last_jpeg = None

            self.status.update({
                "monitoring": True,
                "camera_connected": True,
                "face_detected": False,
                "ear": None,
                "mar": None,
                "blink_rate": 0.0,
                "perclos": None,
                "possible_yawns": 0,
                "experimental_score": None,
                "eye_closed": False,
                "status": "Waiting for browser frames",
                "fps": 0.0,
                "updated_at": (
                    datetime.utcnow().isoformat() + "Z"
                ),
                "note": (
                    "Browser frames are processed transiently; "
                    "raw video is not stored."
                ),
            })

        return {
            "ok": True,
            "message": "Browser-frame monitoring started",
        }

    def process_frame(self, frame):
        """
        Process one decoded OpenCV frame supplied by the browser.

        Returns the updated status dictionary used by the dashboard.
        """
        with self.lock:
            if not self.active or self.mesh is None:
                raise RuntimeError(
                    "Monitoring is not active."
                )

            mesh = self.mesh

        if frame is None or frame.size == 0:
            raise ValueError(
                "Received an empty image frame."
            )

        # Mirror the frame for a natural webcam preview.
        frame = cv2.flip(frame, 1)

        now = time.time()

        if self.prev_time is not None:
            instant_fps = 1.0 / max(
                now - self.prev_time,
                1e-6,
            )

            self.fps = (
                instant_fps
                if not self.fps
                else (
                    0.85 * self.fps
                    + 0.15 * instant_fps
                )
            )

        self.prev_time = now

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB,
        )

        result = mesh.process(rgb)

        face_detected = bool(
            result.multi_face_landmarks
        )

        ear = None
        mar = None
        eye_closed = False

        if face_detected:
            landmarks = (
                result.multi_face_landmarks[0].landmark
            )

            height, width = frame.shape[:2]

            points = [
                (point.x * width, point.y * height)
                for point in landmarks
            ]

            left_ear = _ear(
                points,
                LEFT_EYE,
            )

            right_ear = _ear(
                points,
                RIGHT_EYE,
            )

            valid_ears = [
                value
                for value in (left_ear, right_ear)
                if value is not None
            ]

            if valid_ears:
                ear = sum(valid_ears) / len(valid_ears)

            mar = _mar(points)

            eye_closed = (
                ear is not None
                and ear < self.ear_threshold
            )

            # Draw the selected facial landmarks.
            for group in (
                LEFT_EYE,
                RIGHT_EYE,
                MOUTH,
            ):
                for index in group:
                    x, y = map(
                        int,
                        points[index],
                    )

                    cv2.circle(
                        frame,
                        (x, y),
                        2,
                        (70, 220, 235),
                        -1,
                    )

            ear_text = (
                f"EAR: {ear:.3f}"
                if ear is not None
                else "EAR: --"
            )

            cv2.putText(
                frame,
                ear_text,
                (18, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (70, 220, 235),
                2,
            )

            cv2.putText(
                frame,
                (
                    "EYES CLOSED"
                    if eye_closed
                    else "EYES OPEN"
                ),
                (18, 62),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (
                    (40, 70, 255)
                    if eye_closed
                    else (60, 210, 120)
                ),
                2,
            )

        self._update_metrics(
            now,
            face_detected,
            ear,
            mar,
            eye_closed,
        )

        # Keep only the latest processed JPEG in memory.
        encoded_ok, jpeg = cv2.imencode(
            ".jpg",
            frame,
            [
                int(cv2.IMWRITE_JPEG_QUALITY),
                78,
            ],
        )

        if encoded_ok:
            with self.lock:
                self.last_jpeg = jpeg.tobytes()

        return self.get_status()

    def _update_metrics(
        self,
        now,
        face_detected,
        ear,
        mar,
        eye_closed,
    ):
        with self.lock:
            self.samples.append((
                now,
                bool(eye_closed),
                bool(face_detected),
            ))

            # Maintain the rolling PERCLOS window.
            while (
                self.samples
                and now - self.samples[0][0]
                > self.window_seconds
            ):
                self.samples.popleft()

            # Count completed eye closures in a plausible
            # blink-duration range.
            if eye_closed:
                if self.closed_since is None:
                    self.closed_since = now

            elif self.closed_since is not None:
                duration = now - self.closed_since

                if 0.08 <= duration <= 1.5:
                    self.blink_events.append(now)
                    self.blink_count += 1

                self.closed_since = None

            # Keep blink events from the previous 60 seconds.
            while (
                self.blink_events
                and now - self.blink_events[0] > 60
            ):
                self.blink_events.popleft()

            # Count a possible yawn after sustained high MAR.
            if (
                mar is not None
                and mar > self.mar_threshold
            ):
                if self.yawn_since is None:
                    self.yawn_since = now

                elif (
                    now - self.yawn_since > 1.2
                    and not self.yawn_latched
                ):
                    self.yawn_count += 1
                    self.yawn_latched = True

            else:
                self.yawn_since = None
                self.yawn_latched = False

            # Calculate PERCLOS using frames where a face
            # was detected in the rolling window.
            face_closed = [
                closed
                for _, closed, has_face in self.samples
                if has_face
            ]

            perclos = (
                100.0 * sum(face_closed) / len(face_closed)
                if face_closed
                else None
            )

            # Transparent experimental heuristic only.
            score = None

            if face_detected and perclos is not None:
                prolonged_closure = (
                    15
                    if (
                        self.closed_since is not None
                        and now - self.closed_since > 1
                    )
                    else 0
                )

                score = max(
                    0.0,
                    min(
                        100.0,
                        0.7 * perclos
                        + prolonged_closure
                        + min(
                            15,
                            self.yawn_count * 2,
                        ),
                    ),
                )

            self.status.update({
                "monitoring": self.active,
                "camera_connected": self.active,
                "face_detected": face_detected,
                "ear": (
                    round(ear, 4)
                    if ear is not None
                    else None
                ),
                "mar": (
                    round(mar, 4)
                    if mar is not None
                    else None
                ),
                "blink_rate": float(
                    len(self.blink_events)
                ),
                "perclos": (
                    round(perclos, 2)
                    if perclos is not None
                    else None
                ),
                "possible_yawns": self.yawn_count,
                "experimental_score": (
                    round(score, 1)
                    if score is not None
                    else None
                ),
                "eye_closed": bool(eye_closed),
                "status": (
                    "Face detected"
                    if face_detected
                    else "No face detected"
                ),
                "fps": round(self.fps, 1),
                "updated_at": (
                    datetime.utcnow().isoformat() + "Z"
                ),
                "note": (
                    "Heuristic research indicators only; "
                    "not validated for driving or clinical use."
                ),
            })

    def stop(self):
        """Stop monitoring and release MediaPipe resources."""
        with self.lock:
            self.active = False

            if self.mesh is not None:
                self.mesh.close()
                self.mesh = None

            self.last_jpeg = None

            self.status.update({
                "monitoring": False,
                "camera_connected": False,
                "face_detected": False,
                "status": "Camera is off",
            })

        return {
            "ok": True,
            "message": "Monitoring stopped",
        }

    def get_status(self):
        with self.lock:
            return dict(self.status)

    def get_jpeg(self):
        with self.lock:
            return self.last_jpeg
