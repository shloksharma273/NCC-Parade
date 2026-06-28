from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from ..services.pairing_service import pairing_service

router = APIRouter(tags=["pairing"])


@router.get("/pairing/info")
def pairing_info() -> dict:
    return pairing_service.info()


@router.get("/pairing/qr.png")
def pairing_qr_png() -> Response:
    return Response(content=pairing_service.qr_png_bytes(), media_type="image/png")


@router.get("/pair", response_class=HTMLResponse)
def pairing_page() -> str:
    info = pairing_service.info()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Drill Recognition — Pair Tablet</title>
  <style>
    body {{
      font-family: Inter, system-ui, sans-serif;
      background: #1e2614;
      color: #f8f8f2;
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 2rem;
    }}
    .card {{
      background: #263315;
      border: 2px solid #c2b280;
      border-radius: 16px;
      padding: 2rem;
      max-width: 520px;
      width: 100%;
      text-align: center;
    }}
    h1 {{ margin: 0 0 0.5rem; font-size: 1.5rem; letter-spacing: 0.04em; }}
    .status {{ color: #1f6b3a; font-weight: 700; margin-bottom: 1.5rem; }}
    .meta {{ text-align: left; background: #1e2614; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; font-size: 0.9rem; }}
    .meta div {{ margin: 0.35rem 0; word-break: break-all; }}
    img {{ background: #f7f1dc; padding: 12px; border-radius: 12px; }}
    p {{ color: #efe6c8; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>DRILL RECOGNITION COMMAND SERVER</h1>
    <div class="status">● ONLINE</div>
    <div class="meta">
      <div><strong>Backend:</strong> {info["backend_url"]}</div>
      <div><strong>Tablet Control:</strong> {info["webapp_url"]}</div>
      <div><strong>Pairing Token:</strong> {info["pairing_token"]}</div>
    </div>
    <img src="/pairing/qr.png" width="280" height="280" alt="Pairing QR code" />
    <p>Scan from tablet camera to open the drill control panel.<br/>Ensure tablet and PC are on the same Wi‑Fi.</p>
  </div>
</body>
</html>"""
