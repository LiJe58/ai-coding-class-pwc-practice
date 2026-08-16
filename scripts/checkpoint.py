"""Reset, promote, and verify standalone course checkpoints."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import zipfile
from xml.etree import ElementTree
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO / "practice" / "workspace"
RUNTIME_NAMES = {".venv", "node_modules", "dist", "__pycache__", ".pytest_cache"}
RUNTIME_SUFFIXES = (".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".log")
DAY2_TARGETS = {
    "student/09-evidence-skill-ready",
    "student/10-working-paper-api-ready",
    "student/11-day2-complete",
    "student/12-review-storage-ready",
    "student/13-review-ui-ready",
    "student/14-agent-history-ready",
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
    parts = path.parts
    if path.name == ".env" or any(part in RUNTIME_NAMES for part in parts) or any(parts[index:index + 2] == ("backend", "data") for index in range(len(parts) - 1)):
        return True
    if "output" in parts:
        suffix = parts[parts.index("output"):]
        if suffix not in {("output",), ("output", "day-2"), ("output", "day-2", "working-paper.json")}:
            return True
    return path.name.endswith(RUNTIME_SUFFIXES) or path.name.endswith((".sqlite3-wal", ".sqlite3-shm", ".sqlite3-journal"))


def copy_clean(source: Path, destination: Path, *, root_excludes: tuple[str, ...] = ()) -> None:
    shutil.copytree(source, destination, ignore=lambda directory, names: [name for name in names if (Path(directory) == source and name in root_excludes) or ignored(Path(directory) / name)])


def reset(value: str) -> None:
    source = checkpoint_path(value, must_exist=True)
    preserved: list[tuple[Path, Path]] = []
    with tempfile.TemporaryDirectory(dir=REPO / "practice") as temporary:
        temporary_path = Path(temporary)
        for relative in (Path(".venv"), Path("frontend/node_modules"), Path(".env")):
            runtime = WORKSPACE / relative
            if runtime.exists():
                saved = temporary_path / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(runtime, saved)
                preserved.append((saved, relative))
        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
        copy_clean(source, WORKSPACE)
        copy_clean(REPO / "assets" / "scenario", WORKSPACE / "assets" / "scenario")
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
    copy_clean(WORKSPACE, target, root_excludes=("assets",))


def manifest() -> dict:
    path = REPO / "checkpoints.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def verify_excel(data: dict) -> None:
    path = REPO / "assets" / "scenario" / "case-matrix.xlsx"
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        content = b"".join(package.read(name) for name in names)
        if any(token in content for token in (b"C:\\", b"/Users/", b"/home/", b"x15ac:absPath")):
            raise ValueError("Excel 패키지에 로컬 경로가 남아 있습니다.")
        core = package.read("docProps/core.xml")
        if b"<dc:creator" in core or b"<cp:lastModifiedBy" in core:
            raise ValueError("Excel 작성자 메타데이터가 남아 있습니다.")
        if any(name.startswith("xl/externalLinks/") or name == "xl/connections.xml" for name in names):
            raise ValueError("Excel 외부 연결이 남아 있습니다.")
        workbook = ElementTree.fromstring(package.read("xl/workbook.xml"))
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        sheets = [sheet.attrib["name"] for sheet in workbook.findall(f"{namespace}sheets/{namespace}sheet")]
        if sheets != data["case_matrix_sheets"] or len([name for name in names if name.startswith("xl/tables/table") and name.endswith(".xml")]) != 8:
            raise ValueError("Excel 시트 또는 표 구성이 다릅니다.")


def verify() -> None:
    data = manifest()
    names = data.get("checkpoints", [])
    if not names:
        raise ValueError("checkpoints.json에 체크포인트 목록이 필요합니다.")
    canonical = REPO / "assets" / "day-1" / "input"
    csvs = sorted(canonical.glob("*.csv"))
    if len(csvs) != 6:
        raise ValueError("canonical CSV는 6종이어야 합니다.")
    for position, name in enumerate(names):
        root = checkpoint_path(name, must_exist=True)
        workspace_metadata = json.loads((root / ".course-workspace.json").read_text(encoding="utf-8"))
        expected_stage = name.split("/", 1)[1] if name.startswith("student/") else "complete"
        expected_audience = name.split("/", 1)[0]
        if workspace_metadata.get("stage") != expected_stage or workspace_metadata.get("audience") != expected_audience:
            raise ValueError(f"체크포인트 메타데이터 불일치: {name}")
        for required in (".node-version", ".python-version", ".npmrc", "package.json", "backend/requirements.txt", "frontend/package.json", "frontend/package-lock.json"):
            if not (root / required).is_file():
                raise ValueError(f"필수 파일 누락: {name}/{required}")
        if (root / ".node-version").read_text(encoding="utf-8").strip() != data["versions"]["node"] or (root / ".python-version").read_text(encoding="utf-8").strip() != data["versions"]["python"]:
            raise ValueError(f"runtime 버전 불일치: {name}")
        if "engine-strict=true" in (root / ".npmrc").read_text(encoding="utf-8"):
            raise ValueError(f"상위 Node/npm 버전을 차단하는 설정이 있습니다: {name}")
        frontend = json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))
        versions = [*frontend.get("dependencies", {}).values(), *frontend.get("devDependencies", {}).values()]
        if any(not version[:1].isdigit() or "latest" in version.lower() for version in versions):
            raise ValueError(f"frontend direct dependency가 exact pin이 아닙니다: {name}")
        requirements = [line.split(";", 1)[0].strip() for line in (root / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
        if any("==" not in line or "*" in line for line in requirements):
            raise ValueError(f"Python dependency가 exact pin이 아닙니다: {name}")
        scripts = json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts", {})
        if not {"setup", "check", "start:backend", "dev:frontend"}.issubset(scripts):
            raise ValueError(f"공통 npm 명령 누락: {name}")
        if (position >= 6 or name == "instructor/complete") and not (root / ".mcp.json").is_file():
            raise ValueError(f"MCP 설정 누락: {name}")
        if (position >= 9 or name == "instructor/complete") and not (root / ".claude" / "skills" / "control-test" / "SKILL.md").is_file():
            raise ValueError(f"control-test Skill 누락: {name}")
        for csv_path in csvs:
            copy = root / "input" / "day-1" / csv_path.name
            if not copy.is_file() or copy.read_bytes() != csv_path.read_bytes():
                raise ValueError(f"CSV 사본 불일치: {name}/{csv_path.name}")
        working_paper = root / "output" / "day-2" / "working-paper.json"
        if name in DAY2_TARGETS and not working_paper.is_file():
            raise ValueError(f"Day 2 검토자료 누락: {name}")
        links = [path for path in root.rglob("*") if path.is_symlink() or getattr(path, "is_junction", lambda: False)()]
        if links:
            raise ValueError(f"링크를 사용할 수 없습니다: {links[0]}")
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, check=True, capture_output=True, text=True).stdout.splitlines()
    versioned = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    versioned_set = set(versioned)
    for name in DAY2_TARGETS:
        working_paper = f"{name}/output/day-2/working-paper.json"
        if working_paper not in versioned_set:
            raise ValueError(f"Day 2 검토자료가 버전 관리 대상이 아닙니다: {working_paper}")
    bad = [path for path in tracked if ignored(Path(path)) and not path.endswith("output/day-2/working-paper.json")]
    if bad:
        raise ValueError("runtime 파일이 추적됩니다: " + ", ".join(bad))
    verify_excel(data)
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
