"""Database setup.

Works with PostgreSQL (production / docker-compose) or SQLite (local demo)
depending on the DATABASE_URL environment variable.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./retaildesk.db",  # local quickstart default
)

# Free Postgres hosts (Neon, Supabase, Render) hand out URLs like
# "postgres://..." or "postgresql://...". SQLAlchemy 2.x no longer accepts
# the bare "postgres://" scheme, and the driver must be named explicitly —
# normalise both forms to postgresql+psycopg2:// so a copied connection
# string works as-is.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgresql://"):]


def _strip_unsupported_params(url: str) -> str:
    """Drop query params psycopg2 rejects.

    Neon appends "channel_binding=require" to its connection strings;
    SQLAlchemy passes URL query params through to psycopg2 as connect
    kwargs, and psycopg2 raises on that one. Other params (e.g.
    sslmode=require) are supported and kept.
    """
    if "?" not in url:
        return url
    base, _, query = url.partition("?")
    kept = [p for p in query.split("&") if not p.startswith("channel_binding=")]
    return base + ("?" + "&".join(kept) if kept else "")


if DATABASE_URL.startswith("postgresql"):
    DATABASE_URL = _strip_unsupported_params(DATABASE_URL)

connect_args = {}
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    # Needed so SQLite can be used across FastAPI's threadpool.
    connect_args = {"check_same_thread": False}
else:
    # Postgres: fail fast instead of hanging if the DB container is not up yet.
    engine_kwargs = {"pool_pre_ping": True}

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: one DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
