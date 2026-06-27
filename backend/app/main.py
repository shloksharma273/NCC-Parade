from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.recording_routes import router as recording_router
from .api.report_routes import router as report_router
from .api.session_routes import router as session_router
from .api.status_routes import router as status_router
from .api.websocket_routes import router as websocket_router
from .config import MEDIA_DIR, ensure_directories, settings
from .db.database import init_db
from .ml.drill_analyzer import drill_analyzer


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()
    init_db()
    drill_analyzer.ensure_model_ready()
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
app.include_router(session_router)
app.include_router(recording_router)
app.include_router(report_router)
app.include_router(websocket_router)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
