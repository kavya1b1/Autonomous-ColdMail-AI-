"""Self-contained SQLite persistence for users, profiles, and campaign history.

The project's original ``DATABASE_URL`` points at Postgres (see config/settings.py)
but nothing was ever wired up to it (api/dependencies/store.py explicitly notes the
Postgres models "were never actually wired into the workflow"). Standing up Postgres
is out of scope for this environment, so authentication and per-user persistence use
a local SQLite file instead — same SQLAlchemy models, zero external services required,
and it survives server restarts (a plain file on disk).

If a real Postgres instance is available in production, point AUTH_DATABASE_URL at it
and these models will create the same tables there instead.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database.models import Base

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_SQLITE_PATH = BASE_DIR / "coldmail.db"

AUTH_DATABASE_URL = os.getenv("AUTH_DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

_connect_args = {"check_same_thread": False} if AUTH_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(AUTH_DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
