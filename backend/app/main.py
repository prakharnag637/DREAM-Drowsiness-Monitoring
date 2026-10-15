import os, time, threading, secrets
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from .models import ResearchSession, Measurement
from .vision import VisionEngine

load_dotenv()
Base.metadata.create_all(bind=engine)
app = FastAPI(title="DREAM Research Prototype API", version="0.2.0")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dream-drowsiness-monitoring.vercel.app",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
engine_cv = VisionEngine(
    camera_index=int(os.getenv("CAMERA_INDEX", "0")),
    ear_threshold=float(os.getenv("EAR_THRESHOLD", "0.21")),
    mar_threshold=float(os.getenv("MAR_THRESHOLD", "0.65")),
    perclos_window=int(os.getenv("PERCLOS_WINDOW_SECONDS", "60"))
)
active_session_id = None
worker = None
stop_worker = threading.Event()
sample_interval = float(os.getenv("SAMPLE_INTERVAL_SECONDS", "1.0"))

def db_session():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def measurement_worker(session_id):
    last_save = 0
    while not stop_worker.is_set() and engine_cv.active:
        try:
            engine_cv.read_frame()
            now = time.time()
            if now - last_save >= sample_interval:
                s = engine_cv.get_status()
                db = SessionLocal()
                try:
                    db.add(Measurement(session_id=session_id, face_detected=int(s["face_detected"]),
                        ear=s["ear"], mar=s["mar"], blink_rate=s["blink_rate"], perclos=s["perclos"],
                        possible_yawns=s["possible_yawns"], experimental_score=s["experimental_score"], status=s["status"]))
                    db.commit()
                except Exception:
                    db.rollback()
                finally: db.close()
                last_save = now
        except Exception as exc:
            engine_cv.status["status"] = f"Processing error: {str(exc)[:100]}"
            time.sleep(.2)

@app.get("/")
def root():
    return {"service": "DREAM Research Prototype API", "docs": "/docs", "health": "/api/health"}

@app.get("/api/health")
def health():
    return {"ok": True, "service": "DREAM Research Prototype API", "camera_available": engine_cv.active}

@app.get("/api/status")
def status():
    return engine_cv.get_status()

@app.post("/api/monitoring/start")
def start_monitoring(db: Session = Depends(db_session)):
    global active_session_id, worker
    if engine_cv.active:
        return {"ok": True, "message": "Monitoring already active", "session_id": active_session_id}
    try:
        engine_cv.start()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    code = "DREAM-" + secrets.token_hex(3).upper()
    record = ResearchSession(session_code=code, status="running")
    db.add(record); db.commit(); db.refresh(record)
    active_session_id = record.id
    stop_worker.clear()
    worker = threading.Thread(target=measurement_worker, args=(record.id,), daemon=True)
    worker.start()
    return {"ok": True, "message": "Monitoring started", "session_id": record.id, "session_code": code}

@app.post("/api/monitoring/stop")
def stop_monitoring(db: Session = Depends(db_session)):
    global active_session_id
    if engine_cv.active:
        stop_worker.set()
        engine_cv.stop()
    if active_session_id is not None:
        record = db.query(ResearchSession).filter(ResearchSession.id == active_session_id).first()
        if record:
            record.ended_at = datetime.utcnow(); record.status = "completed"; db.commit()
        old_id = active_session_id
        active_session_id = None
    else: old_id = None
    return {"ok": True, "message": "Monitoring stopped", "session_id": old_id}

@app.get("/api/camera/stream")
def camera_stream():
    def frames():
        while engine_cv.active:
            frame = engine_cv.get_jpeg()
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(.04)
    if not engine_cv.active:
        raise HTTPException(status_code=409, detail="Start monitoring before opening the stream")
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/sessions")
def list_sessions(limit: int = 100, db: Session = Depends(db_session)):
    records = db.query(ResearchSession).order_by(ResearchSession.id.desc()).limit(min(max(limit,1),500)).all()
    out=[]
    for r in records:
        count = db.query(Measurement).filter(Measurement.session_id == r.id).count()
        out.append({"id":r.id,"session_code":r.session_code,"started_at":r.started_at.isoformat()+"Z",
                    "ended_at":r.ended_at.isoformat()+"Z" if r.ended_at else None,"status":r.status,"measurement_count":count})
    return out

@app.get("/api/sessions/{session_id}/measurements")
def get_measurements(session_id: int, limit: int = 5000, db: Session = Depends(db_session)):
    exists = db.query(ResearchSession).filter(ResearchSession.id == session_id).first()
    if not exists: raise HTTPException(status_code=404, detail="Session not found")
    rows = db.query(Measurement).filter(Measurement.session_id == session_id).order_by(Measurement.id.asc()).limit(min(max(limit,1),20000)).all()
    return [{"timestamp":x.timestamp.isoformat()+"Z","face_detected":bool(x.face_detected),"ear":x.ear,"mar":x.mar,
             "blink_rate":x.blink_rate,"perclos":x.perclos,"possible_yawns":x.possible_yawns,
             "experimental_score":x.experimental_score,"status":x.status} for x in rows]

@app.get("/api/sessions/{session_id}/export.csv")
def export_session_csv(session_id: int, db: Session = Depends(db_session)):
    import csv, io
    exists = db.query(ResearchSession).filter(ResearchSession.id == session_id).first()
    if not exists: raise HTTPException(status_code=404, detail="Session not found")
    rows = db.query(Measurement).filter(Measurement.session_id == session_id).order_by(Measurement.id.asc()).all()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["timestamp_utc","face_detected","ear","mar","blink_rate_per_min","perclos_percent","possible_yawns","experimental_score","status"])
    for x in rows: writer.writerow([x.timestamp.isoformat()+"Z",x.face_detected,x.ear,x.mar,x.blink_rate,x.perclos,x.possible_yawns,x.experimental_score,x.status])
    from fastapi.responses import Response
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="dream_session_{session_id}.csv"'})

@app.on_event("shutdown")
def shutdown():
    stop_worker.set()
    if engine_cv.active: engine_cv.stop()
