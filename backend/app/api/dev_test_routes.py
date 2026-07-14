"""TEMPORARY dev-only test harness for drill analysis.

Lets a video be analysed from disk without a camera or a paired session. This
module is NOT part of the production tablet/backend flow and can be removed
without affecting it. Registered in backend/app/main.py behind clear TEMPORARY
comments.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import PROJECT_ROOT, RAW_MEDIA_DIR, settings
from ..ml.drill_analyzer import drill_analyzer

router = APIRouter(prefix="/dev/test", tags=["dev-test"])

# Where returned frame/PDF URLs are served from (mounted in main.py).
OUTPUT_MOUNT = "/dev/test/output"

DATASET_DIR = PROJECT_ROOT / "test_data" / "dataset"
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}


def mount_output_static(app) -> None:
    """Mount settings.ml_output_dir so returned frame/PDF URLs resolve.

    Called from main.py. Kept here so the whole harness lives in one file.
    """
    settings.ml_output_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        OUTPUT_MOUNT,
        StaticFiles(directory=str(settings.ml_output_dir)),
        name="dev-test-output",
    )


class RunRequest(BaseModel):
    video: str
    drill_type: str = "baju_swing"
    difficulty: float | None = None
    # baju_swing camera view: "side" (default) or "front". Ignored by other drills.
    view: str = "side"


def _scan_videos() -> list[dict]:
    videos: list[dict] = []
    seen: set[str] = set()
    for base in (DATASET_DIR, RAW_MEDIA_DIR):
        if not base.exists():
            continue
        for path in sorted(base.glob("*.mp4")):
            if path.name in seen:
                continue
            seen.add(path.name)
            videos.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
                }
            )
    return videos


def _resolve_video(video: str) -> Path | None:
    """Resolve a video by name or relative path, searching dataset then media/raw."""
    candidate = Path(video)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for base in (DATASET_DIR, RAW_MEDIA_DIR):
        for probe in (base / video, base / candidate.name):
            if probe.exists():
                return probe
    return None


def _output_url(abs_path: str | None) -> str | None:
    """Build a URL under OUTPUT_MOUNT for a file inside ml_output_dir."""
    if not abs_path:
        return None
    try:
        rel = Path(abs_path).resolve().relative_to(settings.ml_output_dir.resolve())
    except ValueError:
        return None
    return f"{OUTPUT_MOUNT}/{quote(str(rel))}"


@router.get("/videos")
def list_videos() -> JSONResponse:
    return JSONResponse(_scan_videos())


@router.post("/run")
def run_analysis(req: RunRequest) -> JSONResponse:
    video_path = _resolve_video(req.video)
    if video_path is None:
        return JSONResponse(
            status_code=400,
            content={"error": "VIDEO_NOT_FOUND", "message": f"Could not resolve video: {req.video}"},
        )

    if req.difficulty is not None:
        settings.ml_difficulty = max(0.0, min(5.0, float(req.difficulty)))

    try:
        result = drill_analyzer.analyze(
            str(video_path),
            req.drill_type,
            session_id="DEVTEST-BAJU",
            view=req.view,
        )
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the client
        return JSONResponse(
            status_code=400,
            content={"error": "ANALYSIS_FAILED", "message": str(exc)},
        )

    iteration_count = (
        result.get("iteration_count")
        or result.get("kadam_tal_count")
        or result.get("salute_candidate_count")
        or 0
    )

    return JSONResponse(
        {
            "video": video_path.name,
            "drill_type": req.drill_type,
            "difficulty": settings.ml_difficulty,
            "score": result.get("score"),
            "iteration_count": iteration_count,
            "result": result.get("result"),
            "summary": result.get("summary"),
            "parameters": result.get("parameters"),
            "key_frame_url": _output_url(result.get("key_frame_path")),
            "pdf_url": _output_url(result.get("report_pdf_path")),
        }
    )


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def test_page() -> HTMLResponse:
    return HTMLResponse(_PAGE_HTML)


_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Drill Dev Test Harness</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
  header { padding: 16px 24px; background: #1e293b; border-bottom: 1px solid #334155; }
  header h1 { margin: 0; font-size: 18px; }
  header p { margin: 4px 0 0; font-size: 12px; color: #94a3b8; }
  main { padding: 24px; max-width: 1000px; margin: 0 auto; }
  .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }
  label { display: block; font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
  select, input { padding: 8px; border-radius: 6px; border: 1px solid #334155; background: #0b1220; color: #e2e8f0; }
  button { padding: 9px 18px; border-radius: 6px; border: 0; background: #2563eb; color: #fff; font-weight: 600; cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: default; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; margin-top: 20px; }
  .stat { display: inline-block; margin-right: 28px; }
  .stat b { display: block; font-size: 26px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #334155; font-size: 14px; }
  img { max-width: 100%; border-radius: 8px; border: 1px solid #334155; }
  a { color: #60a5fa; }
  .err { color: #f87171; }
  ul { margin: 6px 0 0; padding-left: 18px; }
</style>
</head>
<body>
<header>
  <h1>Drill Dev Test Harness <span style="color:#f59e0b">(TEMPORARY)</span></h1>
  <p>Analyse a video from disk without a camera. Dev-only endpoint.</p>
</header>
<main>
  <div class="controls">
    <div>
      <label for="video">Video</label>
      <select id="video"></select>
    </div>
    <div>
      <label for="drill">Drill type</label>
      <select id="drill">
        <option value="baju_swing">baju_swing</option>
        <option value="kadam_tal">kadam_tal</option>
        <option value="salute">salute</option>
      </select>
    </div>
    <div>
      <label for="difficulty">Difficulty (0-5)</label>
      <input id="difficulty" type="number" min="0" max="5" step="0.5" value="2"/>
    </div>
    <button id="run">Run analysis</button>
  </div>
  <div id="status" class="card" style="display:none"></div>
  <div id="results" class="card" style="display:none"></div>
</main>
<script>
const vsel = document.getElementById('video');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');
const runBtn = document.getElementById('run');

async function loadVideos() {
  const r = await fetch('/dev/test/videos');
  const list = await r.json();
  vsel.innerHTML = '';
  for (const v of list) {
    const o = document.createElement('option');
    o.value = v.name;
    o.textContent = v.name + ' (' + v.size_mb + ' MB)';
    vsel.appendChild(o);
  }
}

function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

runBtn.addEventListener('click', async () => {
  runBtn.disabled = true;
  statusEl.style.display = 'block';
  statusEl.className = 'card';
  statusEl.textContent = 'Running analysis... (this can take a while)';
  resultsEl.style.display = 'none';
  try {
    const body = {
      video: vsel.value,
      drill_type: document.getElementById('drill').value,
      difficulty: parseFloat(document.getElementById('difficulty').value)
    };
    const r = await fetch('/dev/test/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const data = await r.json();
    if (!r.ok) {
      statusEl.className = 'card err';
      statusEl.textContent = 'Error: ' + (data.message || JSON.stringify(data));
      return;
    }
    statusEl.style.display = 'none';
    renderResults(data);
  } catch (e) {
    statusEl.className = 'card err';
    statusEl.textContent = 'Request failed: ' + e;
  } finally {
    runBtn.disabled = false;
  }
});

function renderResults(d) {
  let html = '';
  html += '<div class="stat"><span>Score</span><b>' + (d.score ?? '-') + '/100</b></div>';
  html += '<div class="stat"><span>Iterations</span><b>' + (d.iteration_count ?? '-') + '</b></div>';
  html += '<div class="stat"><span>Result</span><b>' + esc(d.result ?? '-') + '</b></div>';
  html += '<div class="stat"><span>Difficulty</span><b>' + (d.difficulty ?? '-') + '</b></div>';

  if (Array.isArray(d.summary) && d.summary.length) {
    html += '<h3>Summary</h3><ul>';
    for (const s of d.summary) html += '<li>' + esc(s) + '</li>';
    html += '</ul>';
  }
  if (Array.isArray(d.parameters) && d.parameters.length) {
    html += '<h3>Parameters</h3><table><tr><th>Name</th><th>Expected</th><th>Actual</th><th>Score</th><th>Status</th></tr>';
    for (const p of d.parameters) {
      html += '<tr><td>' + esc(p.name) + '</td><td>' + esc(p.expected) + '</td><td>' + esc(p.actual) +
              '</td><td>' + p.score + '</td><td>' + esc(p.status) + '</td></tr>';
    }
    html += '</table>';
  }
  if (d.key_frame_url) {
    html += '<h3>Key frame</h3><img src="' + d.key_frame_url + '"/>';
  }
  if (d.pdf_url) {
    html += '<h3>Report</h3><a href="' + d.pdf_url + '" target="_blank">Download PDF</a>';
  }
  resultsEl.innerHTML = html;
  resultsEl.style.display = 'block';
}

loadVideos();
</script>
</body>
</html>"""
