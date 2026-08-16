"""Create one local Python/Node runtime for a practice workspace."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


MINIMUM_PYTHON = (3, 14, 5)


def run(command: list[str], workspace: Path) -> None:
    subprocess.run(command, cwd=workspace, check=True)


def main() -> int:
    workspace = Path.cwd().resolve()
    if sys.version_info[:3] < MINIMUM_PYTHON:
        expected = ".".join(map(str, MINIMUM_PYTHON))
        actual = ".".join(map(str, sys.version_info[:3]))
        raise SystemExit(f"Python {expected} 이상이 필요합니다. 현재 버전: {actual}")
    requirements = workspace / "backend" / "requirements.txt"
    frontend = workspace / "frontend"
    if not requirements.is_file() or not (frontend / "package-lock.json").is_file():
        raise SystemExit("현재 폴더에 backend requirements와 frontend lockfile이 없습니다.")
    venv = workspace / ".venv"
    if not venv.exists():
        run([sys.executable, "-m", "venv", str(venv)], workspace)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)], workspace)
    node = os.environ.get("COURSE_NODE")
    npm_cli = os.environ.get("COURSE_NPM_CLI")
    npm = [node, npm_cli] if node and npm_cli else ["npm.cmd" if os.name == "nt" else "npm"]
    run([*npm, "ci", "--prefix", str(frontend)], workspace)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error
