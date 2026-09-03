"""
Database connection setup for the API.

Deliberately mirrors etl/load.py's get_engine() (same env vars, same
.env loading, same pg8000 driver) so the whole project uses one
consistent way to reach PostgreSQL - one less thing to explain
differently in the technical report.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


def _build_dsn() -> str:
    user = os.getenv("POSTGRES_USER", "obrail")
    password = os.getenv("POSTGRES_PASSWORD", "obrail")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "obrail")
    return f"postgresql+pg8000://{user}:{password}@{host}:{port}/{db}"


engine = create_engine(_build_dsn(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency: yields one DB session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
