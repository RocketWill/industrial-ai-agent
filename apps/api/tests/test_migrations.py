import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]


def run_alembic(
    command: str,
    revision: str,
    database_path: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["APP_DATABASE_URL"] = f"sqlite:///{database_path}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", command, revision],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )


def read_database_tables(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()
    return {row[0] for row in rows}


def read_alembic_versions(database_path: Path) -> list[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall()
    return [row[0] for row in rows]


def read_table_columns(
    database_path: Path,
    table: str,
) -> dict[str, tuple[str, bool]]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1]: (row[2], bool(row[3])) for row in rows}


def test_migration_upgrades_empty_database_to_head(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"

    result = run_alembic("upgrade", "head", database_path)

    assert result.returncode == 0, result.stderr
    assert read_database_tables(database_path) == {
        "alembic_version",
        "conversations",
    }
    assert read_alembic_versions(database_path) == [
        "0002_create_conversations"
    ]


def test_conversation_migration_creates_required_schema(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"

    result = run_alembic("upgrade", "head", database_path)

    assert result.returncode == 0, result.stderr
    assert read_table_columns(database_path, "conversations") == {
        "id": ("CHAR(32)", True),
        "title": ("VARCHAR(200)", True),
        "created_at": ("DATETIME", True),
    }

    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO conversations (id, title, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                ("0" * 32, "   "),
            )


def test_conversation_migration_downgrades_to_foundation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    upgrade_result = run_alembic("upgrade", "head", database_path)
    assert upgrade_result.returncode == 0, upgrade_result.stderr

    downgrade_result = run_alembic("downgrade", "-1", database_path)

    assert downgrade_result.returncode == 0, downgrade_result.stderr
    assert read_database_tables(database_path) == {"alembic_version"}
    assert read_alembic_versions(database_path) == [
        "0001_initialize_database"
    ]


def test_migration_downgrades_head_to_base(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    upgrade_result = run_alembic("upgrade", "head", database_path)
    assert upgrade_result.returncode == 0, upgrade_result.stderr

    downgrade_result = run_alembic("downgrade", "base", database_path)

    assert downgrade_result.returncode == 0, downgrade_result.stderr
    assert read_database_tables(database_path) == {"alembic_version"}
    assert read_alembic_versions(database_path) == []
