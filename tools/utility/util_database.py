"""
Database session management for SQL Server.

Provides:
- SQLAlchemy engine and session factory
- Context-managed session with auto-commit/rollback
- Generic table management (ensure, upsert, get, delete)
"""

import os
import logging
import datetime
from contextlib import contextmanager
from typing import Generator
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")

missing = [k for k, v in [
    ("DB_SERVER", DB_SERVER),
    ("DB_DATABASE", DB_DATABASE),
    ("DB_USERNAME", DB_USERNAME),
    ("DB_PASSWORD", DB_PASSWORD)
] if not v]

if missing:
    logging.warning(f"Missing required DB environment variables: {missing}. Database operations will fail.")
    DB_SERVER = DB_DATABASE = DB_USERNAME = DB_PASSWORD = None

driver = "ODBC Driver 18 for SQL Server"

engine = None
SessionLocal = None
Base = declarative_base()

if not missing:
    odbc_str = (
        f"DRIVER={driver};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        f"UID={DB_USERNAME};"
        f"PWD={DB_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )

    SQLALCHEMY_URL = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_str)}"

    try:
        engine = create_engine(
            SQLALCHEMY_URL,
            pool_pre_ping=True,
            fast_executemany=True
        )
        SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    except Exception as e:
        logging.error(f"Failed to create database engine: {e}")
        engine = None
        SessionLocal = None


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context-managed session with auto-commit/rollback."""
    if SessionLocal is None:
        raise RuntimeError("Database not configured. Check DB environment variables.")

    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_table(model_class: type) -> None:
    """Ensure table exists using model's __create_sql__. Idempotent."""
    if engine is None:
        raise RuntimeError("Database engine not initialized.")

    if not hasattr(model_class, '__create_sql__'):
        raise ValueError(f"{model_class.__name__} missing __create_sql__ attribute")

    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(model_class.__create_sql__))


def upsert(model_class: type, data: dict) -> dict:
    """Generic upsert using model's __upsert_keys__."""
    try:
        ensure_table(model_class)
    except Exception as e:
        return {"status_code": 500, "message": f"Error ensuring table schema: {str(e)}"}

    upsert_keys = getattr(model_class, '__upsert_keys__', [])
    if not upsert_keys:
        return {"status_code": 500, "message": f"{model_class.__name__} missing __upsert_keys__"}

    filters = {k: data.get(k) for k in upsert_keys}
    missing_keys = [k for k, v in filters.items() if v is None]
    if missing_keys:
        return {"status_code": 400, "message": f"Missing required upsert keys: {missing_keys}"}

    try:
        with get_session() as session:
            query = session.query(model_class)
            for key, value in filters.items():
                query = query.filter(getattr(model_class, key) == value)
            existing = query.one_or_none()

            if existing:
                for attr, value in data.items():
                    if hasattr(existing, attr) and value is not None:
                        setattr(existing, attr, value)
                existing.updated_at = datetime.datetime.utcnow()
                session.flush()
                return {
                    "status_code": 200,
                    "message": f"{model_class.__tablename__} updated",
                    "action": "updated",
                    "record_id": existing.id
                }
            else:
                valid_attrs = {k: v for k, v in data.items()
                             if hasattr(model_class, k) and v is not None}
                record = model_class(**valid_attrs)
                session.add(record)
                session.flush()
                return {
                    "status_code": 201,
                    "message": f"{model_class.__tablename__} created",
                    "action": "created",
                    "record_id": record.id
                }
    except Exception as e:
        logging.exception(f"Error in upsert for {model_class.__tablename__}: {e}")
        return {"status_code": 500, "message": f"Database error: {str(e)}"}
