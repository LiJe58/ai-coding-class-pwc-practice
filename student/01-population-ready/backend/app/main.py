import csv
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException


app = FastAPI(title="Internal Control Population")
ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "input" / "day-1" / "vendor_changes.csv"
FIELDS = ["change_id", "case_id", "vendor_id", "request_id", "requested_at", "requested_by", "before_account_token", "requested_account_token", "changed_at", "changed_by", "change_reason"]


def load_population() -> dict:
    try:
        with INPUT.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != FIELDS:
                raise ValueError("vendor_changes.csv 헤더가 입력 명세와 다릅니다.")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    counts = Counter(row["change_id"] for row in rows if row["change_id"])
    if any(count > 1 for count in counts.values()):
        raise HTTPException(status_code=500, detail="중복 change_id가 있습니다.")
    return {
        "summary": {"population_count": len(rows)},
        "first_change_id": rows[0]["change_id"],
        "last_change_id": rows[-1]["change_id"],
        "population": rows,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ready", "message": "실습 처리 영역이 준비되었습니다."}


@app.get("/api/control-test")
def control_test() -> dict:
    return load_population()
