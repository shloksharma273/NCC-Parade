from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.camera_routes import router as camera_router
from .api.decision_routes import router as decision_router
from .api.pairing_routes import router as pairing_router
from .api.readiness_routes import router as readiness_router
from .api.recording_routes import router as recording_router
from .api.report_routes import router as report_router
from .api.session_routes import router as session_router
from .api.snapshot_routes import router as snapshot_router
from .api.status_routes import router as status_router
from .api.websocket_routes import router as websocket_router
from .config import MEDIA_DIR, PROJECT_ROOT, ensure_directories, settings
from .db.database import init_db
from .ml.drill_analyzer import drill_analyzer
from .startup_banner import print_startup_banner

WEBAPP_DIR = PROJECT_ROOT / "tablet-webapp" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()
    init_db()
    drill_analyzer.ensure_model_ready()
    print_startup_banner()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status_router)
app.include_router(pairing_router)
app.include_router(readiness_router)
app.include_router(snapshot_router)
app.include_router(session_router)
app.include_router(camera_router)
app.include_router(recording_router)
app.include_router(report_router)
app.include_router(decision_router)
app.include_router(websocket_router)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

if WEBAPP_DIR.exists():
    assets_dir = WEBAPP_DIR / "assets"
    if assets_dir.exists():
        app.mount("/app/assets", StaticFiles(directory=str(assets_dir)), name="app-assets")

    @app.get("/app")
    async def serve_app_root():
        return FileResponse(WEBAPP_DIR / "index.html")

    @app.get("/app/{full_path:path}")
    async def serve_app(full_path: str):
        file_path = WEBAPP_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(WEBAPP_DIR / "index.html")
