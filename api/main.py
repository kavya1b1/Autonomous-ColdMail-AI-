"""FastAPI backend for ColdMail AI Pro.

Serves the existing agent/workflow backend (LangGraph, Groq, SMTP, etc,
unchanged) over a REST API, and serves the new HTML/CSS/vanilla-JS frontend
that replaces the old Streamlit UI.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.logging import logger
from config.settings import settings
from api.routes import auth as auth_routes
from api.routes import campaign as campaign_routes
from api.routes import extract as extract_routes
from api.routes import profile as profile_routes

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENV,
    }


@app.get("/api")
async def api_root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


app.include_router(auth_routes.router)
app.include_router(profile_routes.router)
app.include_router(extract_routes.router)
app.include_router(campaign_routes.router)

# Serve the frontend (HTML/CSS/JS) last, as a catch-all, so it never shadows
# an /api or /health route registered above.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
