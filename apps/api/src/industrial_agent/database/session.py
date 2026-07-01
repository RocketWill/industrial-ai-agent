from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from industrial_agent.config.settings import Settings


def create_database_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )


@lru_cache
def get_database_engine() -> Engine:
    return create_database_engine(Settings().database_url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return create_session_factory(get_database_engine())


def get_db_session() -> Generator[Session, None, None]:
    database_session = get_session_factory()()
    try:
        yield database_session
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()
