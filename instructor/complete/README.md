# Instructor Complete

완료 상태: Day 1~3 전체 기능, 상태 연결, 완료 조건, 권한 확인, 중복 저장 방지, CSV 내보내기 조건과 적용 범위 템플릿이 포함됩니다. 선택한 표본의 `Agent로 다시 확인`은 기존 `get_case_evidence` Tool로 근거를 읽어 화면에만 보여줍니다.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

Agent 확인을 실행하려면 서버 환경에 `OPENAI_API_KEY`, `OPENAI_MODEL`을 설정합니다. 내부 호환 API를 사용할 때만 `OPENAI_BASE_URL`을 추가합니다. 값은 파일이나 브라우저에 넣지 않습니다. 설정이 없으면 Agent 확인만 중단되고 기존 검토 기능은 계속 동작합니다.

초기 집계는 `12/0/12`, 완료 집계 예시는 `12/12/0/4/1/7`입니다. 12건을 모두 검토하기 전에는 CSV 내보내기가 거부됩니다. 입력 CSV와 Agent 조서 파일 `output/day-2/working-paper.json`은 보존하고 SQLite·다운로드 CSV는 실행 중에만 사용하세요. Agent 확인 결과도 저장하지 않습니다. 복구는 `python scripts/checkpoint.py reset instructor/complete`를 사용합니다.
