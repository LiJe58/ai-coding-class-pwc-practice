# Instructor Complete

완료 상태: Day 1–3 전체 기능, 상태 연결, 완료 조건, 권한 확인, 중복 저장 방지, CSV 내보내기 조건과 적용 범위 템플릿이 포함됩니다. 메인의 `Agent 검토 수행`은 기존 `get_case_evidence` Tool로 선택한 표본의 근거를 읽고 실행 결과를 사례별 이력에 남깁니다.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

Agent 확인을 실행하려면 `Copy-Item .env.example .env`로 로컬 설정 파일을 만든 뒤 `OPENAI_API_KEY`를 입력합니다. 내부 호환 API를 사용할 때만 `OPENAI_BASE_URL`을 추가합니다. `.env`는 Git에서 제외되고 workspace reset에서도 보존됩니다. 키를 코드나 브라우저에 넣지 마세요. 설정이 없으면 Agent 확인만 중단되고 기존 검토 기능은 계속 동작합니다.

초기 집계는 `12/0/12`, 완료 집계 예시는 `12/12/0/4/1/7`입니다. 12건을 모두 검토하기 전에는 CSV 내보내기가 거부됩니다. 입력 CSV와 Agent 검토자료 파일 `output/day-2/working-paper.json`은 보존하고 SQLite·다운로드 CSV는 실행 중에만 사용하세요. Agent 실행 이력은 SQLite에 저장되지만 최종 검토 결과와 검토자료는 바꾸지 않습니다. 복구는 `python scripts/checkpoint.py reset instructor/complete`를 사용합니다.
