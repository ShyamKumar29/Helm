# api/db.py — engine, session factory, schema reset. B1.
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from api import config

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, future=True
)


class Base(DeclarativeBase):
    pass


def get_session():
    """FastAPI dependency. One session per request, always closed."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def reset_schema():
    """Drop everything and recreate. This IS our migration strategy."""
    from api import models  # noqa: F401 — registers the tables on Base

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
