# Instructor Complete

완료 상태: Day 1~3 전체 기능, 상태 연결, 완료 조건, 권한·멱등 저장, CSV export gate, 실패 복구 UI와 적용 범위 템플릿이 포함됩니다.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

초기 집계는 `12/0/12`, 완료 집계 예시는 `12/12/0/4/1/7`입니다. 12건 검토 전 export는 거부됩니다. 입력 CSV와 `output/day-2/working-paper.json`은 보존하고 SQLite·다운로드 CSV는 runtime으로만 사용하세요. 복구는 `python scripts/checkpoint.py reset instructor/complete`를 사용합니다.
