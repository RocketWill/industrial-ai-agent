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


def read_foreign_keys(
    database_path: Path,
    table: str,
) -> list[tuple[object, ...]]:
    with sqlite3.connect(database_path) as connection:
        return connection.execute(
            f"PRAGMA foreign_key_list({table})"
        ).fetchall()


def read_indexes(database_path: Path, table: str) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(f"PRAGMA index_list({table})").fetchall()
    return {row[1] for row in rows}


def test_migration_upgrades_empty_database_to_head(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"

    result = run_alembic("upgrade", "head", database_path)

    assert result.returncode == 0, result.stderr
    assert read_database_tables(database_path) == {
        "alembic_version",
        "conversations",
        "messages",
    }
    assert read_alembic_versions(database_path) == ["0006_add_evidence_snapshot"]


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
        "environment": ("VARCHAR(20)", True),
        "device": ("VARCHAR(200)", False),
        "lot": ("VARCHAR(200)", False),
        "time_range": ("VARCHAR(100)", False),
        "data_source": ("VARCHAR(30)", True),
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


def test_message_migration_creates_required_schema_and_constraints(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    result = run_alembic("upgrade", "head", database_path)
    assert result.returncode == 0, result.stderr

    assert read_table_columns(database_path, "messages") == {
        "id": ("CHAR(32)", True),
        "conversation_id": ("CHAR(32)", True),
        "role": ("VARCHAR(9)", True),
        "content": ("TEXT", True),
        "suggested_actions": ("JSON", True),
        "evidence_snapshot": ("JSON", False),
        "created_at": ("DATETIME", True),
    }
    assert "ix_messages_conversation_id" in read_indexes(
        database_path,
        "messages",
    )
    assert any(
        row[2] == "conversations"
        and row[3] == "conversation_id"
        and row[4] == "id"
        and row[6] == "CASCADE"
        for row in read_foreign_keys(database_path, "messages")
    )

    conversation_id = "a" * 32
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            INSERT INTO conversations (id, title, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (conversation_id, "Constraint test"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, role, content, created_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                ("1" * 32, conversation_id, "system", "content"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, role, content, created_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                ("2" * 32, conversation_id, "user", "   "),
            )
        connection.execute(
            """
            INSERT INTO messages (
                id, conversation_id, role, content, created_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("3" * 32, conversation_id, "user", "Valid content"),
        )
        connection.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        remaining_messages = connection.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()

    assert remaining_messages == (0,)


def test_suggested_actions_migration_defaults_existing_rows_and_downgrades(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    upgrade_result = run_alembic(
        "upgrade", "0004_add_workspace_context", database_path
    )
    assert upgrade_result.returncode == 0, upgrade_result.stderr
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO conversations (id, title, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            ("a" * 32, "Existing conversation"),
        )
        connection.execute(
            """
            INSERT INTO messages (
                id, conversation_id, role, content, created_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("b" * 32, "a" * 32, "assistant", "Existing message"),
        )

    result = run_alembic("upgrade", "head", database_path)

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database_path) as connection:
        stored = connection.execute(
            "SELECT suggested_actions FROM messages"
        ).fetchone()
    assert stored == ("[]",)

    downgrade_result = run_alembic(
        "downgrade", "0004_add_workspace_context", database_path
    )
    assert downgrade_result.returncode == 0, downgrade_result.stderr
    assert "suggested_actions" not in read_table_columns(database_path, "messages")


def test_evidence_snapshot_migration_keeps_existing_messages_readable(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    upgrade_result = run_alembic(
        "upgrade", "0005_add_suggested_actions", database_path
    )
    assert upgrade_result.returncode == 0, upgrade_result.stderr

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO conversations (id, title, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            ("a" * 32, "Existing conversation"),
        )
        connection.execute(
            """
            INSERT INTO messages (
                id, conversation_id, role, content, created_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("b" * 32, "a" * 32, "assistant", "Existing message"),
        )

    result = run_alembic("upgrade", "head", database_path)

    assert result.returncode == 0, result.stderr
    assert read_table_columns(database_path, "messages")["evidence_snapshot"] == (
        "JSON",
        False,
    )
    with sqlite3.connect(database_path) as connection:
        stored = connection.execute(
            """
            SELECT role, content, evidence_snapshot
            FROM messages
            WHERE id = ?
            """,
            ("b" * 32,),
        ).fetchone()
    assert stored == ("assistant", "Existing message", None)


def test_message_migration_downgrades_to_conversations(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    upgrade_result = run_alembic("upgrade", "head", database_path)
    assert upgrade_result.returncode == 0, upgrade_result.stderr

    downgrade_result = run_alembic("downgrade", "-4", database_path)

    assert downgrade_result.returncode == 0, downgrade_result.stderr
    assert read_database_tables(database_path) == {
        "alembic_version",
        "conversations",
    }
    assert read_alembic_versions(database_path) == [
        "0002_create_conversations"
    ]


def test_conversation_migration_downgrades_to_foundation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    upgrade_result = run_alembic("upgrade", "head", database_path)
    assert upgrade_result.returncode == 0, upgrade_result.stderr
    message_downgrade = run_alembic("downgrade", "-4", database_path)
    assert message_downgrade.returncode == 0, message_downgrade.stderr

    conversation_downgrade = run_alembic(
        "downgrade",
        "-1",
        database_path,
    )

    assert conversation_downgrade.returncode == 0
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
