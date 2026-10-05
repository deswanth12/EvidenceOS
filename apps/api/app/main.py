"""FastAPI application entry point for EvidenceOS / VeriDock."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.routes.cases import router as cases_router
from apps.api.app.routes.cases import seed_canonical_demo_cases
from core.config import get_settings
from core.datasets_generator import write_synthetic_datasets_to_disk
from core.db.models import CaseModel, get_session_factory, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Write synthetic dataset files to datasets/synthetic_cases if not present
    datasets_dir = Path("datasets/synthetic_cases")
    if not (datasets_dir / "manifest.json").exists():
        write_synthetic_datasets_to_disk(datasets_dir)
    # Seed canonical cases on first startup if database is empty
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        if db.query(CaseModel).count() == 0:
            seed_canonical_demo_cases(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="EvidenceOS API (VeriDock)",
        description=(
            "AI evidence verification engine for high-stakes business decisions. "
            "VeriDock reconciles B2B delivery and procurement disputes across Purchase Orders, "
            "Delivery Challans, Inspection Photos, and Warehouse Voice Reports."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health_check():
        return {
            "status": "healthy",
            "service": "EvidenceOS",
            "application": "VeriDock",
            "version": "0.1.0",
            "ai_provider": settings.ai_provider,
        }

    app.include_router(cases_router)
    app.include_router(cases_router, prefix="/api")
    return app


app = create_app()
