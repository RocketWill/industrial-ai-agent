import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from industrial_agent.database.session import (
    create_database_engine,
    create_session_factory,
    get_db_session,
)
from industrial_agent.main import create_app

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_database_url(tmp_path: Path) -> str:
    database_path = tmp_path / "application.db"
    database_url = f"sqlite:///{database_path}"
    environment = os.environ.copy()
    environment["APP_DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return database_url


@pytest.fixture
def database_engine(
    migrated_database_url: str,
) -> Generator[Engine, None, None]:
    engine = create_database_engine(migrated_database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def database_session(
    database_engine: Engine,
) -> Generator[Session, None, None]:
    factory = create_session_factory(database_engine)
    with factory() as session:
        yield session


@pytest.fixture
def conversation_client(
    database_engine: Engine,
) -> Generator[TestClient, None, None]:
    factory = create_session_factory(database_engine)
    application = create_app()

    def override_db_session() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    application.dependency_overrides[get_db_session] = override_db_session
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
