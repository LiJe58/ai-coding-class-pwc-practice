# Excel Agent 실습 규칙

- `data/Excel_Copilot_anonymized.xlsx`만 사용하고 원본이나 대응표를 저장소에 넣지 않습니다.
- 필수 Tool은 `get_pbc_mismatches(top_n)` 하나이며 Python 함수와 MCP Tool이 같은 코드를 사용합니다.
- 모델 설정은 `OPENAI_API_KEY`, `OPENAI_MODEL`, 선택적 `OPENAI_BASE_URL`에서만 읽습니다.
- 비밀값과 Excel 원본 행 전체를 코드, 문서, 로그, 화면 결과에 남기지 않습니다.
- Agent는 최대 3단계로 끝내고 `tool_events`에는 Tool 이름, 인자, 상태만 기록합니다.
- 계산은 Tool이 담당하고 모델 설명은 사람이 검토해야 하는 초안으로 다룹니다.
- 추가 Tool은 선택 과제로만 다루며 기존 필수 Tool을 바꾸지 않습니다.
