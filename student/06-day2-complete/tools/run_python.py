"""Run a command with the current workspace virtual environment."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def venv_python(workspace: Path) -> Path:
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    python = workspace / ".venv" / relative
    if not python.is_file():
        raise SystemExit("가상환경이 없습니다. 먼저 `npm run setup`을 실행하세요.")
    return python


def main() -> int:
    workspace = Path.cwd().resolve()
    return subprocess.call([str(venv_python(workspace)), *sys.argv[1:]], cwd=workspace)


if __name__ == "__main__":
    raise SystemExit(main())
