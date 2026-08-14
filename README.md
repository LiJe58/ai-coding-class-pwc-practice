# AI Coding Class · 내부통제 실습

합성 거래처·승인·증빙·지급 데이터를 사용해 Day 1 규칙 기반 통제, Day 2 읽기 전용 MCP Agent 조서, Day 3 사람 검토와 export를 단계별로 구현하는 독립 공개 실습 저장소입니다.

## 검증 기준 환경

- Node.js `22.16.0`
- npm `10.9.2`
- Python `3.14.5`

위 버전에서 전체 검증했으며 더 높은 Node.js, npm, Python 버전도 사용할 수 있습니다. 애플리케이션 dependency는 재현성을 위해 exact 버전으로 고정하며 frontend 설치에는 `npm ci`를 사용합니다.

## 처음 시작하기

교육 기간에 공개되는 저장소를 HTTPS로 clone합니다.

```powershell
git clone https://github.com/LiJe58/ai-coding-class-pwc-practice.git
cd ai-coding-class-pwc-practice
python scripts/checkpoint.py reset instructor/complete
cd practice/workspace
npm run setup
cd ../..
python scripts/checkpoint.py reset student/00-starter
cd practice/workspace
npm run check
npm run start:backend
```

의존성은 강사용 superset으로 한 번만 설치합니다. 이후 reset은 `.venv`와 `frontend/node_modules`를 보존하므로 다시 설치하지 않습니다. 새 터미널에서 frontend는 `npm run dev:frontend`로 실행합니다.

기본 주소는 backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:5173`입니다. MCP가 필요한 단계는 `npm run start:mcp`를 사용합니다.

## 체크포인트

| 경로 | 이미 완료된 상태 | 다음 교재 묶음 |
|---|---|---|
| `student/00-starter` | health, 준비 화면, CSV 6종 | 환경·입력 연결 |
| `student/01-population-ready` | 모집단 30, 유효 29, 오류 1 | 통제 규칙·저장 |
| `student/02-controls-persisted` | 정상 21, 검토 8, SQLite 멱등 저장 | Day 1 화면 연결 |
| `student/03-day1-complete` | Day 1 API·UI·SQLite 완료 | Agent 구성·MCP 연결 |
| `student/04-mcp-connected` | 읽기 전용 `mock-erp` Tool 3개 | 표본·근거·Skill |
| `student/05-evidence-skill-ready` | 표본 12건, 권한 근거 조회, Skill | Agent 조서 생성·연결 |
| `student/06-day2-complete` | 고정 조서 12건, 모두 사람 검토 필요 | 결론 저장소 분리 |
| `student/07-review-storage-ready` | 권한 검증, append-only 검토 이벤트 | 멱등 이력·최종 화면 |
| `student/08-review-ui-ready` | action ID 멱등, 전체 이력, 검토 UI | 상태·완료·export |
| `instructor/complete` | Day 1~3 전체 기능과 적용 범위 템플릿 | 최종 시연 |

중간 합류나 오류 복구는 저장할 코드가 없는지 확인한 뒤 저장소 루트에서 다음처럼 실행합니다.

```powershell
python scripts/checkpoint.py reset student/05-evidence-skill-ready
cd practice/workspace
npm run check
```

직접 만든 올바른 상태를 새 체크포인트로 보관할 때만 `python scripts/checkpoint.py promote student/<새-이름>`을 사용합니다. 기존 대상은 덮어쓰지 않습니다. 전체 배포 계약은 `python scripts/checkpoint.py verify`로 검사합니다.

## 자료와 runtime 정책

`assets/day-1/input/`의 CSV 6종, `assets/scenario/control-card.md`, `assets/scenario/case-matrix.xlsx`, Day 2 이후의 `output/day-2/working-paper.json`은 합성 고정 자료입니다. 실제 회사 자료, 개인정보, 비밀번호, 인증정보, 운영 URL을 추가하지 마세요. Excel과 애플리케이션에서 경로는 저장소 상대경로만 사용합니다.

`.venv`, `node_modules`, `dist`, `backend/data`, SQLite/WAL/journal, pycache, 로그, 임시 JSON, 실제 검토 이벤트와 다운로드 CSV는 Git에 포함하지 않습니다. 강사용 완성본은 `instructor/complete`에 있으며 같은 내용의 학생 최종 폴더는 두지 않습니다.

## 이용 조건

이 저장소는 교육 기간에만 임시 공개됩니다. 승인된 강사와 수강생은 해당 교육 실습 목적으로만 clone·실행·수정할 수 있으며, 외부 공유·재배포·공개 게시·상업적 또는 운영 목적 이용은 허용되지 않습니다. 공개 상태 자체가 일반 이용 허락을 의미하지 않습니다. 자세한 조건은 [LICENSE](LICENSE)를 확인하세요.
