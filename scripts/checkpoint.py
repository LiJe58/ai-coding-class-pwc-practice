"""Reset, promote, and verify standalone course checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO / "practice" / "workspace"
RUNTIME_NAMES = {".venv", "node_modules", "dist", "__pycache__", ".pytest_cache"}
RUNTIME_SUFFIXES = (".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".log")
DAY2_TARGETS = {
    "student/06-day2-complete",
    "student/07-review-storage-ready",
    "student/08-review-ui-ready",
    "instructor/complete",
}


def checkpoint_path(value: str, *, must_exist: bool) -> Path:
    normalized = value.replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if len(parts) != 2 or parts[0] not in {"student", "instructor"} or parts[1] in {"", ".", ".."}:
        raise ValueError("체크포인트는 student/<name> 또는 instructor/<name> 형식이어야 합니다.")
    path = (REPO / normalized).resolve()
    if REPO.resolve() not in path.parents:
        raise ValueError("저장소 밖 경로는 사용할 수 없습니다.")
    if must_exist and not path.is_dir():
        raise ValueError(f"체크포인트가 없습니다: {normalized}")
    return path


def ignored(path: Path) -> bool:
    return any(part in RUNTIME_NAMES for part in path.parts) or path.name.endswith(RUNTIME_SUFFIXES) or path.name.endswith((".sqlite3-wal", ".sqlite3-shm", ".sqlite3-journal"))


def copy_clean(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, ignore=lambda directory, names: [name for name in names if ignored(Path(directory) / name)])


def reset(value: str) -> None:
    source = checkpoint_path(value, must_exist=True)
    preserved: list[tuple[Path, Path]] = []
    with tempfile.TemporaryDirectory(dir=REPO / "practice") as temporary:
        temporary_path = Path(temporary)
        for relative in (Path(".venv"), Path("frontend/node_modules")):
            runtime = WORKSPACE / relative
            if runtime.exists():
                saved = temporary_path / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(runtime, saved)
                preserved.append((saved, relative))
        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
        copy_clean(source, WORKSPACE)
        for saved, relative in preserved:
            destination = WORKSPACE / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(saved, destination)


def promote(value: str) -> None:
    target = checkpoint_path(value, must_exist=False)
    if not WORKSPACE.is_dir():
        raise ValueError("먼저 practice/workspace를 준비하세요.")
    if target.exists():
        raise ValueError(f"대상이 이미 존재합니다: {value}")
    target.parent.mkdir(parents=True, exist_ok=True)
    copy_clean(WORKSPACE, target)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest() -> dict:
    path = REPO / "checkpoints.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def verify() -> None:
    data = manifest()
    names = data.get("checkpoints") or [
        path.relative_to(REPO).as_posix()
        for root in (REPO / "student", REPO / "instructor")
        if root.exists()
        for path in root.iterdir()
        if path.is_dir()
    ]
    canonical = REPO / "assets" / "day-1" / "input"
    csvs = sorted(canonical.glob("*.csv"))
    if len(csvs) != 6:
        raise ValueError("canonical CSV는 6종이어야 합니다.")
    expected_assets = data.get("assets", {})
    for csv_path in csvs:
        expected = expected_assets.get(csv_path.name)
        if expected and sha256(csv_path) != expected:
            raise ValueError(f"canonical asset 해시 불일치: {csv_path.name}")
    fixture_hash = data.get("working_paper_sha256")
    for name in names:
        root = checkpoint_path(name, must_exist=True)
        for csv_path in csvs:
            copy = root / "input" / "day-1" / csv_path.name
            if not copy.is_file() or sha256(copy) != sha256(csv_path):
                raise ValueError(f"CSV 사본 불일치: {name}/{csv_path.name}")
        fixture = root / "output" / "day-2" / "working-paper.json"
        if name in DAY2_TARGETS and (not fixture.is_file() or fixture_hash and sha256(fixture) != fixture_hash):
            raise ValueError(f"Day 2 조서 fixture 불일치: {name}")
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, check=True, capture_output=True, text=True).stdout.splitlines()
    bad = [path for path in tracked if ignored(Path(path)) and not path.endswith("output/day-2/working-paper.json")]
    if bad:
        raise ValueError("runtime 파일이 추적됩니다: " + ", ".join(bad))
    print(f"verified {len(names)} checkpoints, {len(csvs)} canonical CSV files")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("reset", "promote"):
        subparsers.add_parser(command).add_argument("checkpoint")
    subparsers.add_parser("verify")
    args = parser.parse_args()
    try:
        if args.command == "reset":
            reset(args.checkpoint)
        elif args.command == "promote":
            promote(args.checkpoint)
        else:
            verify()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
