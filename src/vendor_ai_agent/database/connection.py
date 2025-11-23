import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


_engine = None
_SessionLocal = None


def init_db(database_url: str | None = None) -> None:
    global _engine, _SessionLocal
    
    if database_url is None:
        database_url = os.getenv(
            "DATABASE_URL",
            "sqlite:///vendor_ai.db"
        )
    
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    
    _engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10 if not database_url.startswith("sqlite") else 0,
        max_overflow=20 if not database_url.startswith("sqlite") else 0,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        connect_args=connect_args
    )
    
    _SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine
    )
    
    Base.metadata.create_all(bind=_engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        init_db()
    
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine():
    if _engine is None:
        init_db()
    return _engine
