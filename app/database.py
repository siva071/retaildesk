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

# Neon/Supabase pooled endpoints work fine with psycopg2 defaults; if the
# provider string includes query params (e.g. ?sslmode=require) SQLAlchemy
# passes them through to psycopg2 unchanged.

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
