
import os
import secrets
import threading
import time
from datetime import datetime

import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .database import Base, engine, SessionLocal
from .models import ResearchSession, Measurement
from .vision import VisionEngine

load_dotenv()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DREAM Research Prototype API",
    version="0.3.0",
)

# CORS: allow the deployed frontend and local development.
default_origins = (
    "https://dream-drowsiness-monitoring.vercel.app,"
    "http://localhost:5173,"
    "http://127.0.0.1:5173"
)

origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", default_origins
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine_cv = VisionEngine(
    camera_index=int(os.getenv("CAMERA_INDEX", "0")),
    ear_threshold=float(os.getenv("EAR_THRESHOLD", "0.21")),
    mar_threshold=float(os.getenv("MAR_THRESHOLD", "0.65")),
    perclos_window=int(
        os.getenv("PERCLOS_WINDOW_SECONDS", "60")
    ),
)

active_session_id = None
last_save = 0.0

sample_interval = float(
    os.getenv("SAMPLE_INTERVAL_SECONDS", "1.0")
)

state_lock = threading.RLock()


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_measurement(session_id, status):
    """Persist one sampled set of numeric research measurements."""
    db = SessionLocal()

    try:
        measurement = Measurement(
            session_id=session_id,
            face_detected=int(
                bool(status["face_detected"])
            ),
            ear=status["ear"],
            mar=status["mar"],
            blink_rate=status["blink_rate"],
            perclos=status["perclos"],
            possible_yawns=status["possible_yawns"],
            experimental_score=status[
                "experimental_score"
            ],
            status=status["status"],
        )

        db.add(measurement)
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


@app.get("/")
def root():
    return {
        "service": "DREAM Research Prototype API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "DREAM Research Prototype API",
        "camera_available": engine_cv.active,
        "camera_mode": "browser",
    }


@app.get("/api/status")
def status():
    return engine_cv.get_status()


@app.post("/api/monitoring/start")
def start_monitoring(
    db: Session = Depends(db_session),
):
    global active_session_id, last_save

    with state_lock:
        if (
            engine_cv.active
            and active_session_id is not None
        ):
            return {
                "ok": True,
                "message": "Monitoring already active",
                "session_id": active_session_id,
            }

        try:
            # Initializes MediaPipe only.
            # It must NOT open cv2.VideoCapture on Render.
            engine_cv.start_browser()

        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
            ) from exc

        code = (
            "DREAM-" + secrets.token_hex(3).upper()
        )

        record = ResearchSession(
            session_code=code,
            status="running",
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        active_session_id = record.id
        last_save = 0.0

        return {
            "ok": True,
            "message": (
                "Monitoring started; waiting for browser frames"
            ),
            "session_id": record.id,
            "session_code": code,
        }


@app.post("/api/monitoring/frame")
async def monitoring_frame(request: Request):
    """
    Receive a JPEG captured by the user's browser webcam,
    process it with MediaPipe, and save sampled metrics.
    Raw frames are not persisted.
    """
    global last_save

    if not engine_cv.active:
        raise HTTPException(
            status_code=409,
            detail="Start a monitoring session first.",
        )

    content_type = request.headers.get(
        "content-type", ""
    ).lower()

    if (
        "image/jpeg" not in content_type
        and "application/octet-stream" not in content_type
    ):
        raise HTTPException(
            status_code=415,
            detail=(
                "Send a JPEG frame with "
                "Content-Type image/jpeg."
            ),
        )

    raw = await request.body()

    if not raw:
        raise HTTPException(
            status_code=400,
            detail="Empty frame received.",
        )

    if len(raw) > 2_000_000:
        raise HTTPException(
            status_code=413,
            detail=(
                "Frame too large. Reduce browser capture resolution."
            ),
        )

    encoded = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(
        encoded,
        cv2.IMREAD_COLOR,
    )

    if frame is None:
        raise HTTPException(
            status_code=400,
            detail="Could not decode JPEG frame.",
        )

    try:
        current_status = engine_cv.process_frame(frame)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Frame processing failed: "
                + str(exc)[:180]
            ),
        ) from exc

    now = time.time()
    session_id = active_session_id

    # Save numeric measurements at the configured interval,
    # rather than storing every camera frame.
    if (
        session_id is not None
        and now - last_save >= sample_interval
    ):
        try:
            save_measurement(
                session_id,
                current_status,
            )
            last_save = now

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Could not save measurement: "
                    + str(exc)[:120]
                ),
            ) from exc

    return current_status


@app.post("/api/monitoring/stop")
def stop_monitoring(
    db: Session = Depends(db_session),
):
    global active_session_id

    with state_lock:
        engine_cv.stop()
        old_id = active_session_id

        if old_id is not None:
            record = (
                db.query(ResearchSession)
                .filter(
                    ResearchSession.id == old_id
                )
                .first()
            )

            if record:
                record.ended_at = datetime.utcnow()
                record.status = "completed"
                db.commit()

        active_session_id = None

    return {
        "ok": True,
        "message": "Monitoring stopped",
        "session_id": old_id,
    }


@app.get("/api/sessions")
def list_sessions(
    limit: int = 100,
    db: Session = Depends(db_session),
):
    records = (
        db.query(ResearchSession)
        .order_by(ResearchSession.id.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )

    output = []

    for record in records:
        count = (
            db.query(Measurement)
            .filter(
                Measurement.session_id == record.id
            )
            .count()
        )

        output.append({
            "id": record.id,
            "session_code": record.session_code,
            "started_at": (
                record.started_at.isoformat() + "Z"
            ),
            "ended_at": (
                record.ended_at.isoformat() + "Z"
                if record.ended_at
                else None
            ),
            "status": record.status,
            "measurement_count": count,
        })

    return output


@app.get(
    "/api/sessions/{session_id}/measurements"
)
def get_measurements(
    session_id: int,
    limit: int = 5000,
    db: Session = Depends(db_session),
):
    exists = (
        db.query(ResearchSession)
        .filter(
            ResearchSession.id == session_id
        )
        .first()
    )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    rows = (
        db.query(Measurement)
        .filter(
            Measurement.session_id == session_id
        )
        .order_by(Measurement.id.asc())
        .limit(min(max(limit, 1), 20000))
        .all()
    )

    return [
        {
            "timestamp": (
                row.timestamp.isoformat() + "Z"
            ),
            "face_detected": bool(row.face_detected),
            "ear": row.ear,
            "mar": row.mar,
            "blink_rate": row.blink_rate,
            "perclos": row.perclos,
            "possible_yawns": row.possible_yawns,
            "experimental_score": (
                row.experimental_score
            ),
            "status": row.status,
        }
        for row in rows
    ]


@app.get(
    "/api/sessions/{session_id}/export.csv"
)
def export_session_csv(
    session_id: int,
    db: Session = Depends(db_session),
):
    import csv
    import io

    exists = (
        db.query(ResearchSession)
        .filter(
            ResearchSession.id == session_id
        )
        .first()
    )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    rows = (
        db.query(Measurement)
        .filter(
            Measurement.session_id == session_id
        )
        .order_by(Measurement.id.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "timestamp_utc",
        "face_detected",
        "ear",
        "mar",
        "blink_rate_per_min",
        "perclos_percent",
        "possible_yawns",
        "experimental_score",
        "status",
    ])

    for row in rows:
        writer.writerow([
            row.timestamp.isoformat() + "Z",
            row.face_detected,
            row.ear,
            row.mar,
            row.blink_rate,
            row.perclos,
            row.possible_yawns,
            row.experimental_score,
            row.status,
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="dream_session_{session_id}.csv"'
            )
        },
    )


@app.on_event("shutdown")
def shutdown():
    engine_cv.stop()
