import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException


app = FastAPI(title="Internal Control Population")
ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "input" / "day-1" / "vendor_changes.csv"
FIELDS = ["change_id", "case_id", "vendor_id", "request_id", "requested_at", "requested_by", "before_account_token", "requested_account_token", "changed_at", "changed_by", "change_reason"]
REQUIRED = ["change_id", "case_id", "vendor_id", "request_id", "requested_by", "before_account_token", "requested_account_token", "changed_by"]


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
    errors = []
    for row in rows:
        reasons = [f"{field} 필수값 누락" for field in REQUIRED if not row[field].strip()]
        for field in ("requested_at", "changed_at"):
            try:
                datetime.strptime(row[field], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                reasons.append(f"{field} 형식 오류")
        if row["change_id"] and counts[row["change_id"]] > 1:
            reasons.append("중복 change_id")
        if reasons:
            errors.append({"change_id": row["change_id"], "reasons": reasons})
    return {
        "summary": {"population_count": len(rows), "valid_count": len(rows) - len(errors), "input_error_count": len(errors)},
        "first_change_id": rows[0]["change_id"],
        "last_change_id": rows[-1]["change_id"],
        "population": rows,
        "input_errors": errors,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ready", "message": "실습 처리 영역이 준비되었습니다."}


@app.get("/api/control-test")
def control_test() -> dict:
    return load_population()
