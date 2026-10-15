
const API = (
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

import "./style.css";

document.querySelector("#app").innerHTML = `
<div class="shell">
  <aside class="sidebar">
    <div class="brand">
      <div class="mark">D</div>
      <div><b>DREAM</b><small>RESEARCH PROTOTYPE</small></div>
    </div>
    <div class="navlabel">WORKSPACE</div>
    <nav>
      <button class="nav active" data-page="overview">◈ &nbsp; Overview</button>
      <button class="nav" data-page="sessions">◷ &nbsp; Research sessions</button>
      <button class="nav" data-page="analytics">▥ &nbsp; Analytics & export</button>
      <button class="nav" data-page="notes">✎ &nbsp; Research notes</button>
    </nav>
    <div class="sidefoot">v0.3 · Browser webcam build</div>
  </aside>

  <main>
    <header class="top">
      <div>
        <div class="eyebrow">DRIVER MONITORING · COMPUTER VISION</div>
        <h1 id="pageTitle">Research overview</h1>
        <p id="subtitle">Live camera indicators and system status</p>
      </div>
      <span class="badge" id="overall">SYSTEM IDLE</span>
    </header>

    <section class="page active" id="overview">
      <div class="metrics">
        <div class="card">
          <label>Experimental score</label>
          <strong id="score">— <small>/ 100</small></strong>
          <span>Heuristic · not validated</span>
        </div>
        <div class="card">
          <label>Blink events in last 60s</label>
          <strong id="blink">— <small>/ min</small></strong>
          <span>EAR-based heuristic</span>
        </div>
        <div class="card">
          <label>PERCLOS estimate</label>
          <strong id="perclos">— <small>%</small></strong>
          <span>Rolling eye-closure window</span>
        </div>
        <div class="card">
          <label>Processing speed</label>
          <strong id="fps">— <small>FPS</small></strong>
          <span id="duration">No active session</span>
        </div>
      </div>

      <div class="columns">
        <div class="card">
          <div class="cardhead">
            <h2>Live camera & landmarks</h2>
            <span class="tag" id="camtag">CAMERA OFF</span>
          </div>

          <div class="camera">
            <video id="stream" autoplay muted playsinline></video>
            <canvas id="captureCanvas" hidden></canvas>
            <div id="cameraPlaceholder">
              ▣
              <b>Camera preview is off</b>
              <small>Start a session and allow webcam access.</small>
            </div>
          </div>

          <div class="actions">
            <button class="primary" id="start">▶ Start monitoring</button>
            <button class="danger" id="stop" disabled>■ Stop session</button>
          </div>

          <p class="privacy">
            Privacy: frames are sent transiently to the backend for processing
            and are not stored as video. Sampled numeric measurements and
            session metadata may be stored.
          </p>
        </div>

        <div class="card">
          <div class="cardhead">
            <h2>Detection pipeline</h2>
            <span class="tag">STATUS</span>
          </div>
          <div class="row"><b>Camera input</b><span id="cameraStatus">Offline</span></div>
          <div class="row"><b>Face detection</b><span id="faceStatus">Waiting</span></div>
          <div class="row"><b>EAR / eye state</b><span id="earStatus">—</span></div>
          <div class="row"><b>Mouth ratio / possible yawns</b><span id="marStatus">—</span></div>
          <div class="row"><b>FastAPI backend</b><span id="apiStatus">Checking…</span></div>
          <div class="row"><b>Database</b><span id="dbStatus">API persistence configured</span></div>
          <button id="refresh" class="wide">Refresh status</button>
        </div>
      </div>

      <div class="columns lower">
        <div class="card">
          <div class="cardhead">
            <h2>Recent indicator trend</h2>
            <span class="tag">LIVE SAMPLES</span>
          </div>
          <div id="trend" class="trend">
            <p>No measurements yet. Start monitoring.</p>
          </div>
          <small class="muted">
            Experimental research score only; not a validated drowsiness measure.
          </small>
        </div>

        <div class="card">
          <div class="cardhead"><h2>Research checklist</h2></div>
          <div class="row"><b>Live webcam processing</b><span id="checkCamera">Pending</span></div>
          <div class="row"><b>Landmark-based EAR/MAR</b><span id="checkFeatures">Pending</span></div>
          <div class="row"><b>Ground-truth annotation</b><span>Required</span></div>
          <div class="row"><b>Evaluation metrics</b><span>Not yet evaluated</span></div>
        </div>
      </div>
    </section>

    <section class="page" id="sessions">
      <div class="card">
        <div class="cardhead">
          <h2>Research sessions</h2>
          <button id="loadSessions">Refresh sessions</button>
        </div>
        <div class="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Code</th><th>Started (UTC)</th><th>Ended (UTC)</th>
                <th>Status</th><th>Samples</th><th>Export</th>
              </tr>
            </thead>
            <tbody id="sessionRows">
              <tr><td colspan="6">Loading…</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="page" id="analytics">
      <div class="card">
        <div class="cardhead"><h2>Measurement export</h2></div>
        <p>Select a recorded session to export its sampled numeric measurements as CSV.</p>
        <select id="sessionSelect">
          <option value="">Choose a session</option>
        </select>
        <button class="primary" id="download">Download selected CSV</button>
        <div class="row">
          <b>Metrics captured</b>
          <span>EAR, MAR, blink events/min, PERCLOS, possible yawns, score, face status</span>
        </div>
        <div class="notice">
          Research validity requires independent labels. Do not use this experimental
          score for diagnosis or driving-safety decisions.
        </div>
      </div>
    </section>

    <section class="page" id="notes">
      <div class="card">
        <h2>Research notes</h2>
        <p>Record protocol details locally in this browser. Avoid names and identifying information.</p>
        <textarea id="notesText" rows="8"
          placeholder="Lighting, camera angle, glasses/occlusion, coded participant ID, annotation notes…"></textarea>
        <button class="primary" id="saveNotes">Save notes in browser</button>
        <p class="muted">Notes are not sent to the server.</p>
      </div>
    </section>

    <footer>
      DREAM — Drowsiness Recognition and Estimation through Automated Monitoring ·
      Research prototype · Not for real-world driving decisions.
    </footer>
  </main>
</div>
<div id="toast"></div>
`;

const $ = id => document.getElementById(id);

let poll = null;
let frameLoop = null;
let startMs = null;
let history = [];
let mediaStream = null;
let busyFrame = false;
let stopping = false;
let frameErrorShown = false;

const titles = {
  overview: ["Research overview", "Live camera indicators and system status"],
  sessions: ["Research sessions", "Stored sessions and measurement counts"],
  analytics: ["Analytics & export", "Download session data for research analysis"],
  notes: ["Research notes", "Local protocol notes"]
};

document.querySelectorAll("[data-page]").forEach(button => {
  button.onclick = () => {
    document.querySelectorAll("[data-page]").forEach(item =>
      item.classList.toggle("active", item === button)
    );

    document.querySelectorAll(".page").forEach(page =>
      page.classList.toggle("active", page.id === button.dataset.page)
    );

    $("pageTitle").textContent = titles[button.dataset.page][0];
    $("subtitle").textContent = titles[button.dataset.page][1];

    if (button.dataset.page === "sessions") {
      loadSessions();
    }
  };
});

function toast(message) {
  $("toast").textContent = message;
  $("toast").style.display = "block";

  setTimeout(() => {
    $("toast").style.display = "none";
  }, 4500);
}

async function request(path, options = {}) {
  const response = await fetch(API + path, options);

  let data = {};
  try {
    data = await response.json();
  } catch {}

  if (!response.ok) {
    throw new Error(
      data.detail || `HTTP ${response.status}`
    );
  }

  return data;
}

function num(value, decimals = 1) {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(Number(value))
  ) {
    return "—";
  }

  return Number(value).toFixed(decimals);
}

function renderTrend() {
  if (!history.length) {
    $("trend").innerHTML =
      "<p>No measurements yet. Start monitoring.</p>";
    return;
  }

  $("trend").innerHTML = history.slice(-36).map(sample => {
    const value = Number(sample.experimental_score || 0);

    return `
      <div
        title="score ${sample.experimental_score ?? "n/a"}"
        class="vbar"
        style="height:${Math.max(3, value)}%"
      ></div>
    `;
  }).join("");
}

function renderStatus(status) {
  $("apiStatus").textContent = "Connected";
  $("overall").textContent =
    status.monitoring ? "MONITORING" : "SYSTEM IDLE";

  $("cameraStatus").textContent =
    status.camera_connected ? "Browser connected" : "Offline";

  $("faceStatus").textContent = status.face_detected
    ? "Face detected"
    : (status.monitoring ? "No face detected" : "Waiting");

  $("earStatus").textContent = status.ear == null
    ? "—"
    : `${num(status.ear, 3)} · ${status.eye_closed ? "Closed" : "Open"}`;

  $("marStatus").textContent = status.mar == null
    ? "—"
    : `${num(status.mar, 3)} · possible yawns: ${status.possible_yawns}`;

  $("score").innerHTML =
    `${num(status.experimental_score)} <small>/ 100</small>`;

  $("blink").innerHTML =
    `${num(status.blink_rate, 0)} <small>/ min</small>`;

  $("perclos").innerHTML =
    `${num(status.perclos)} <small>%</small>`;

  $("fps").innerHTML =
    `${num(status.fps)} <small>FPS</small>`;

  $("checkCamera").textContent =
    status.monitoring ? "Active" : "Pending";

  $("checkFeatures").textContent =
    status.face_detected ? "Features available" : "Waiting for face";

  if (status.monitoring && startMs) {
    const seconds = Math.floor(
      (Date.now() - startMs) / 1000
    );

    $("duration").textContent =
      `Session ${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  }

  history.push(status);

  if (history.length > 90) {
    history.shift();
  }

  renderTrend();
}

async function refresh() {
  try {
    const status = await request("/api/status");
    renderStatus(status);
  } catch (error) {
    $("apiStatus").textContent = "Unavailable";
    $("overall").textContent = "BACKEND OFFLINE";
  }
}

function stopFrameLoop() {
  if (frameLoop) {
    clearInterval(frameLoop);
  }

  frameLoop = null;
}

async function sendFrame() {
  if (
    stopping ||
    busyFrame ||
    !mediaStream
  ) {
    return;
  }

  const video = $("stream");

  if (!video.videoWidth || !video.videoHeight) {
    return;
  }

  busyFrame = true;

  try {
    const canvas = $("captureCanvas");

    // Limit the frame dimensions to reduce upload and processing costs.
    const maxWidth = 640;
    const scale = Math.min(
      1,
      maxWidth / video.videoWidth
    );

    canvas.width = Math.max(
      1,
      Math.round(video.videoWidth * scale)
    );

    canvas.height = Math.max(
      1,
      Math.round(video.videoHeight * scale)
    );

    const context = canvas.getContext(
      "2d",
      { alpha: false }
    );

    context.drawImage(
      video,
      0,
      0,
      canvas.width,
      canvas.height
    );

    const blob = await new Promise(resolve => {
      canvas.toBlob(
        resolve,
        "image/jpeg",
        0.72
      );
    });

    if (!blob) {
      throw new Error("Could not encode webcam frame.");
    }

    const response = await fetch(
      API + "/api/monitoring/frame",
      {
        method: "POST",
        headers: {
          "Content-Type": "image/jpeg"
        },
        body: blob
      }
    );

    let data = {};

    try {
      data = await response.json();
    } catch {}

    if (!response.ok) {
      throw new Error(
        data.detail || `Frame upload failed (${response.status})`
      );
    }

    frameErrorShown = false;
    renderStatus(data);

  } catch (error) {
    stopFrameLoop();

    if (!frameErrorShown) {
      frameErrorShown = true;
      toast("Frame processing issue: " + error.message);
    }

  } finally {
    busyFrame = false;
  }
}

async function start() {
  if ($("start").disabled) {
    return;
  }

  $("start").disabled = true;

  try {
    if (
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia
    ) {
      throw new Error(
        "Webcam access is unavailable. Open the HTTPS Vercel site."
      );
    }

    // Request access to the webcam connected to the user's device.
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
        width: { ideal: 640 },
        height: { ideal: 480 }
      },
      audio: false
    });

    $("stream").srcObject = mediaStream;
    await $("stream").play();

    // Initialize MediaPipe and create a research session on Render.
    await request(
      "/api/monitoring/start",
      { method: "POST" }
    );

    startMs = Date.now();
    stopping = false;
    frameErrorShown = false;

    $("cameraPlaceholder").style.display = "none";
    $("stream").style.display = "block";
    $("camtag").textContent = "CAMERA ON";

    $("stop").disabled = false;

    if (poll) {
      clearInterval(poll);
    }

    poll = setInterval(refresh, 1500);

    stopFrameLoop();

    // Keep frame requests sequential: sendFrame ignores overlapping calls.
    frameLoop = setInterval(sendFrame, 300);

    await sendFrame();

    toast(
      "Monitoring started. Keep your face visible in adequate lighting."
    );

    refresh();

  } catch (error) {
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
    }

    mediaStream = null;
    $("stream").srcObject = null;
    $("stream").style.display = "none";
    $("cameraPlaceholder").style.display = "grid";
    $("camtag").textContent = "CAMERA OFF";
    $("start").disabled = false;
    $("stop").disabled = true;

    toast("Could not start monitoring: " + error.message);
  }
}

async function stop() {
  stopping = true;

  stopFrameLoop();

  if (poll) {
    clearInterval(poll);
  }

  poll = null;

  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop());
  }

  mediaStream = null;
  $("stream").srcObject = null;

  try {
    await request(
      "/api/monitoring/stop",
      { method: "POST" }
    );
  } catch (error) {
    toast("Stop request: " + error.message);
  }

  $("stream").style.display = "none";
  $("cameraPlaceholder").style.display = "grid";
  $("camtag").textContent = "CAMERA OFF";
  $("start").disabled = false;
  $("stop").disabled = true;

  $("duration").textContent = "Session stopped";

  startMs = null;
  busyFrame = false;
  stopping = false;

  await refresh();
  await loadSessions();

  toast("Monitoring stopped. Available measurements have been saved.");
}

async function loadSessions() {
  try {
    const sessions = await request("/api/sessions");

    $("sessionRows").innerHTML = sessions.length
      ? sessions.map(session => `
        <tr>
          <td>${session.session_code}</td>
          <td>${session.started_at.replace("T", " ").replace("Z", "")}</td>
          <td>${session.ended_at ? session.ended_at.replace("T", " ").replace("Z", "") : "—"}</td>
          <td>${session.status}</td>
          <td>${session.measurement_count}</td>
          <td><button data-export="${session.id}">CSV</button></td>
        </tr>
      `).join("")
      : '<tr><td colspan="6">No sessions recorded yet.</td></tr>';

    $("sessionSelect").innerHTML =
      '<option value="">Choose a session</option>' +
      sessions.map(session => `
        <option value="${session.id}">
          ${session.session_code} · ${session.measurement_count} samples
        </option>
      `).join("");

    document.querySelectorAll("[data-export]").forEach(button => {
      button.onclick = () => download(button.dataset.export);
    });

  } catch (error) {
    $("sessionRows").innerHTML =
      `<tr><td colspan="6">Backend unavailable: ${error.message}</td></tr>`;
  }
}

function download(id) {
  if (!id) {
    toast("Choose a session first.");
    return;
  }

  const link = document.createElement("a");

  link.href = `${API}/api/sessions/${id}/export.csv`;
  link.download = `dream_session_${id}.csv`;

  document.body.appendChild(link);
  link.click();
  link.remove();
}

$("start").onclick = start;
$("stop").onclick = stop;
$("refresh").onclick = refresh;
$("loadSessions").onclick = loadSessions;

$("download").onclick = () => {
  download($("sessionSelect").value);
};

$("saveNotes").onclick = () => {
  localStorage.setItem(
    "dream-research-notes",
    $("notesText").value
  );

  toast("Research notes saved locally.");
};

$("notesText").value =
  localStorage.getItem("dream-research-notes") || "";

refresh();
loadSessions();
