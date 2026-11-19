import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import settings
from app.db import Base, add_missing_columns, engine
from app.routers import admin, auth, complaints, meta, officer
from app.services.ml import classifier

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
settings.media_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # Alembic migrations come in Phase 3
    add_missing_columns()
    classifier.load()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Citizen grievance portal: submit complaints with photos, AI routing to the right "
        "department and ward, officer workflow with email updates.\n\n"
        "Use **Authorize** with a demo account (e.g. `citizen1@gp.demo` / `Demo@123`)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(auth.users_router)
app.include_router(meta.router)
app.include_router(complaints.router)
app.include_router(officer.router)
app.include_router(admin.router)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "docs": "/docs"}
