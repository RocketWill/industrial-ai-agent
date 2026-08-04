import subprocess
import sys
import tomllib
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_server_import_is_quiet_and_does_not_start_transport() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import industrial_agent.mcp.server"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def test_project_exposes_explicit_mcp_server_entrypoint() -> None:
    with (API_ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)

    assert project["project"]["scripts"]["industrial-agent-mcp"] == (
        "industrial_agent.mcp.server:main"
    )
