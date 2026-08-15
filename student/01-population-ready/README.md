# 01 · Population Ready

완료 상태: `vendor_changes.csv` 30건을 원본 순서로 읽고 첫·마지막 식별자를 API에서 확인합니다. 입력 오류와 통제 규칙 판정은 아직 구현하지 않습니다.

다음 교재: `separate-input-errors` → `save-results`.

프런트엔드는 백엔드 준비 상태만 표시합니다. 실제 검토 UI는 `connect-review-screens`부터 구현합니다.

```text
npm run setup
npm run check
npm run start:backend
npm run dev:frontend
```

기대값은 전체 30, 첫 ID `CHG-2608-001`, 마지막 ID `CHG-2608-030`입니다. CSV는 보존합니다. 문제 시 저장소 루트에서 `python scripts/checkpoint.py reset student/01-population-ready`로 복구합니다.
