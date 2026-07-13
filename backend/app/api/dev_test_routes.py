"""TEMPORARY dev-only test harness (added for the slow_march drill).

Lets a video be analyzed WITHOUT a camera/DB session, and ships a tiny inline HTML
page for manual testing. Safe to delete once real camera recording is wired up.
Mounted from backend/app/main.py behind /dev/test and clearly marked as temporary.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..config import PROJECT_ROOT, RAW_MEDIA_DIR, settings
from ..ml.drill_analyzer import drill_analyzer

router = APIRouter(prefix="/dev/test", tags=["dev-test (TEMPORARY)"])

DATASET_DIR = PROJECT_ROOT / "test_data" / "dataset"
_SEARCH_DIRS = [DATASET_DIR, RAW_MEDIA_DIR]
DEV_SESSION_ID = "DEVTEST-SLOW"


class RunRequest(BaseModel):
    video: str
    drill_type: str = "slow_march"
    difficulty: float | None = None


def _list_videos() -> list[dict]:
    videos: list[dict] = []
    seen: set[str] = set()
    for directory in _SEARCH_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.mp4")):
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
    candidate = Path(video)
    if candidate.is_file():
        return candidate
    for directory in _SEARCH_DIRS:  # search dataset first, then media/raw
        match = directory / Path(video).name
        if match.is_file():
            return match
    return None


def _output_url(absolute_path: str | None) -> str | None:
    if not absolute_path:
        return None
    try:
        rel = Path(absolute_path).resolve().relative_to(settings.ml_output_dir.resolve())
    except (ValueError, OSError):
        return None
    return f"/dev/test/output/{rel.as_posix()}"


@router.get("/videos")
def list_test_videos() -> list[dict]:
    return _list_videos()


@router.post("/run")
def run_test(request: RunRequest) -> dict:
    video_path = _resolve_video(request.video)
    if video_path is None:
        raise HTTPException(status_code=400, detail={"error": "VIDEO_NOT_FOUND", "message": f"Video not found: {request.video}"})

    if request.difficulty is not None:
        settings.ml_difficulty = max(0.0, min(5.0, float(request.difficulty)))

    try:
        result = drill_analyzer.analyze(str(video_path), request.drill_type, session_id=DEV_SESSION_ID)
    except Exception as exc:  # clean JSON error, HTTP 400
        raise HTTPException(status_code=400, detail={"error": "ANALYSIS_FAILED", "message": str(exc)})

    return {
        "video": video_path.name,
        "drill_type": request.drill_type,
        "difficulty": settings.ml_difficulty,
        "score": result.get("score"),
        "iteration_count": result.get("iteration_count", result.get("kadam_tal_count", result.get("salute_candidate_count"))),
        "result": result.get("result"),
        "summary": result.get("summary"),
        "parameters": result.get("parameters"),
        "key_frame_url": _output_url(result.get("key_frame_path")),
        "pdf_url": _output_url(result.get("report_pdf_path")),
    }


@router.get("", response_class=HTMLResponse)
def test_page() -> str:
    return _PAGE_HTML


_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Drill Dev Test Harness (TEMPORARY)</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 900px; color: #1a1a1a; }
  h1 { font-size: 1.4rem; }
  .banner { background: #fff4e5; border: 1px solid #ffb020; padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; }
  label { display: block; margin: 0.8rem 0 0.2rem; font-weight: 600; }
  select, input, button { font-size: 1rem; padding: 6px 8px; }
  button { background: #2f5597; color: #fff; border: 0; border-radius: 6px; cursor: pointer; margin-top: 1rem; }
  button:disabled { opacity: 0.6; cursor: default; }
  table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
  th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 0.9rem; }
  th { background: #2f5597; color: #fff; }
  #score { font-size: 1.6rem; font-weight: 700; margin-top: 1rem; }
  img { max-width: 100%; border: 1px solid #ccc; border-radius: 6px; margin-top: 1rem; }
  .muted { color: #666; font-size: 0.85rem; }
  ul { margin: 0.4rem 0; }
</style>
</head>
<body>
<div class="banner">TEMPORARY dev-only harness. Runs a drill analysis on a stored video without a camera.</div>
<h1>Drill Dev Test Harness</h1>

<label for="video">Video</label>
<select id="video"></select>

<label for="drill">Drill type</label>
<select id="drill">
  <option value="slow_march">slow_march</option>
  <option value="kadam_tal">kadam_tal</option>
  <option value="salute">salute</option>
</select>

<label for="difficulty">Difficulty (0-5)</label>
<input id="difficulty" type="number" min="0" max="5" step="0.5" value="2"/>

<div><button id="run">Run analysis</button></div>

<div id="status" class="muted"></div>
<div id="score"></div>
<div id="summary"></div>
<div id="params"></div>
<div id="frame"></div>
<div id="pdf"></div>

<script>
async function loadVideos() {
  const res = await fetch('/dev/test/videos');
  const videos = await res.json();
  const sel = document.getElementById('video');
  sel.innerHTML = '';
  videos.forEach(v => {
    const o = document.createElement('option');
    o.value = v.name;
    o.textContent = v.name + ' (' + v.size_mb + ' MB)';
    sel.appendChild(o);
  });
  if (!videos.length) { sel.innerHTML = '<option>(no videos found)</option>'; }
}

document.getElementById('run').addEventListener('click', async () => {
  const btn = document.getElementById('run');
  btn.disabled = true;
  document.getElementById('status').textContent = 'Running analysis... (this can take a while)';
  ['score','summary','params','frame','pdf'].forEach(id => document.getElementById(id).innerHTML = '');
  try {
    const body = {
      video: document.getElementById('video').value,
      drill_type: document.getElementById('drill').value,
      difficulty: parseFloat(document.getElementById('difficulty').value)
    };
    const res = await fetch('/dev/test/run', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) {
      const msg = (data.detail && data.detail.message) ? data.detail.message : JSON.stringify(data);
      document.getElementById('status').textContent = 'Error: ' + msg;
      return;
    }
    document.getElementById('status').textContent = 'Done.';
    document.getElementById('score').textContent =
      'Score: ' + data.score + '/100  |  Result: ' + data.result + '  |  Iterations: ' + data.iteration_count;

    const sum = document.getElementById('summary');
    if (Array.isArray(data.summary)) {
      sum.innerHTML = '<ul>' + data.summary.map(s => '<li>' + s + '</li>').join('') + '</ul>';
    }

    const params = document.getElementById('params');
    if (Array.isArray(data.parameters) && data.parameters.length) {
      let t = '<table><tr><th>Parameter</th><th>Expected</th><th>Actual</th><th>Status</th><th>Feedback</th></tr>';
      data.parameters.forEach(p => {
        t += '<tr><td>' + p.name + '</td><td>' + p.expected + '</td><td>' + p.actual +
             '</td><td>' + p.status + '</td><td>' + p.feedback + '</td></tr>';
      });
      params.innerHTML = t + '</table>';
    }

    if (data.key_frame_url) {
      document.getElementById('frame').innerHTML = '<img src="' + data.key_frame_url + '" alt="key frame"/>';
    }
    if (data.pdf_url) {
      document.getElementById('pdf').innerHTML = '<p><a href="' + data.pdf_url + '" target="_blank">Open PDF report</a></p>';
    }
  } catch (e) {
    document.getElementById('status').textContent = 'Error: ' + e;
  } finally {
    btn.disabled = false;
  }
});

loadVideos();
</script>
</body>
</html>
"""
