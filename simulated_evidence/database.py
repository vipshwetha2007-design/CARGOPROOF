"""
Database engine + session management for the CargoProof simulated evidence API.

Uses SQLite for zero-config hackathon deployment. The DB file lives at
../data/cargoproof.db (relative to the project root), matching the project
structure requested for CargoProof.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Project root is one level up from this package (cargoproof/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "cargoproof.db"

# check_same_thread=False is required because FastAPI/Uvicorn may use the
# session from different threads for a single-worker dev server.
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def get_db() -> Generator:
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (idempotent - safe to call multiple times)."""
    # Importing models here (not at module top) avoids circular imports,
    # since models.py imports Base from this module.
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
