# DREAM — Drowsiness Recognition and Estimation through Automated Monitoring
Research prototype v0.2

This project is a **working prototype scaffold** with webcam capture, MediaPipe facial landmarks, experimental EAR/blink/PERCLOS/yawn indicators, a FastAPI API, a browser dashboard, and persistent session/measurement records.

## Important limitations
- This is a research prototype, **not a validated driver-safety system** and must not be used to make driving decisions.
- EAR/MAR thresholds are configurable heuristics and will need calibration and evaluation.
- A face/eye indicator is not ground truth for drowsiness. Validate against independently annotated observations.
- Video is processed locally and is not stored. Session measurements and event summaries are stored.
- Camera access depends on OS permissions, a working webcam, and compatible dependencies.

## Requirements
- Windows 10/11 (instructions below), Python 3.10 or 3.11 recommended
- Node.js 18+ only if you want to run the frontend with Vite. Alternatively serve `frontend` with any static server; camera API calls need the backend.
- Webcam

## 1. Start the backend (Windows PowerShell)
```powershell
cd DREAM_Complete_Prototype\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```
If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.

Backend: http://127.0.0.1:8000
API docs: http://127.0.0.1:8000/docs
Health check: http://127.0.0.1:8000/api/health

## 2. Start the frontend
Open a second terminal:
```powershell
cd DREAM_Complete_Prototype\frontend
npm install
npm run dev
```
Open the local URL Vite prints (usually http://localhost:5173). Allow camera permission if prompted by the browser. The webcam is opened by the Python backend, not by the browser page.

## Database
By default, SQLite creates `backend/dream_research.db` automatically, so the prototype runs without MySQL configuration.
To use MySQL, edit `backend/.env` and set `DATABASE_URL` to a SQLAlchemy URL, for example:
`mysql+pymysql://USERNAME:PASSWORD@127.0.0.1:3306/dream_research`
Install `pymysql` (included in requirements). Create the database first in MySQL. Avoid putting a real password into shared source control.

## What is implemented
- Start/stop camera monitoring through API
- Face mesh landmark processing (MediaPipe)
- Eye Aspect Ratio (EAR) and heuristic blink/eye-closure events
- Rolling PERCLOS estimate (default 60-second window)
- Mouth Aspect Ratio (MAR) heuristic for possible yawns
- Experimental composite indicator (heuristic, not clinically validated)
- Live dashboard polling metrics and MJPEG camera stream
- Research sessions and sampled metrics persisted to SQLite/MySQL
- CSV export from the dashboard
- API health and camera status

## Research work still required
1. Calibrate thresholds and define the observation protocol.
2. Collect ethically approved, consented, coded observations.
3. Add independent ground-truth annotations.
4. Report precision, recall, F1, confusion matrix, false alerts/hour, FPS and latency.
5. Test lighting, glasses, camera angle, face occlusion, and varied participants.
6. Review privacy/consent and institutional requirements before collecting participant data.

## Troubleshooting
- **Camera unavailable:** close apps using the webcam, verify Windows Camera permissions, try `CAMERA_INDEX=1` in `.env`, restart backend.
- **No face detected:** improve lighting, face the camera, and move into frame.
- **Frontend can't connect:** ensure backend is running at port 8000 and frontend origin is listed in `CORS_ORIGINS`.
- **Dependency install errors:** use Python 3.10/3.11 in a fresh virtual environment; don't install into a shared/global Python environment.
- **MySQL error:** leave the default SQLite URL until the prototype is running, then configure MySQL separately.
