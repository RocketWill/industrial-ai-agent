from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from industrial_agent.database import session as session_module
from industrial_agent.database.session import (
    create_database_engine,
    create_session_factory,
    get_db_session,
)


class TrackingSession(Session):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.was_closed = False
        self.was_rolled_back = False

    def rollback(self) -> None:
        self.was_rolled_back = True
        super().rollback()

    def close(self) -> None:
        self.was_closed = True
        super().close()


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path}"


def test_engine_and_session_factory_connect_to_temporary_sqlite(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database.db"
    engine = create_database_engine(sqlite_url(database_path))
    factory = create_session_factory(engine)

    with factory() as database_session:
        result = database_session.scalar(text("SELECT 1"))

    engine.dispose()

    assert isinstance(engine, Engine)
    assert isinstance(factory, sessionmaker)
    assert result == 1
    assert database_path.exists()


def test_sqlite_engine_enables_foreign_key_enforcement(
    tmp_path: Path,
) -> None:
    engine = create_database_engine(sqlite_url(tmp_path / "foreign-keys.db"))

    with engine.connect() as connection:
        enabled = connection.scalar(text("PRAGMA foreign_keys"))

    engine.dispose()

    assert enabled == 1


def test_database_dependency_closes_successful_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = sessionmaker(class_=TrackingSession)
    monkeypatch.setattr(
        session_module,
        "get_session_factory",
        lambda: factory,
    )
    dependency: Generator[Session, None, None] = get_db_session()

    database_session = next(dependency)

    assert isinstance(database_session, TrackingSession)
    assert not database_session.was_closed

    with pytest.raises(StopIteration):
        next(dependency)

    assert database_session.was_closed
    assert not database_session.was_rolled_back


def test_database_dependency_rolls_back_and_closes_after_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = sessionmaker(class_=TrackingSession)
    monkeypatch.setattr(
        session_module,
        "get_session_factory",
        lambda: factory,
    )
    dependency: Generator[Session, None, None] = get_db_session()
    database_session = next(dependency)

    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert isinstance(database_session, TrackingSession)
    assert database_session.was_rolled_back
    assert database_session.was_closed
