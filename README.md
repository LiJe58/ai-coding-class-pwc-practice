# AI Coding Class · 내부통제 실습

합성 거래처·승인·증빙·지급 데이터를 사용해 Day 1 규칙 기반 통제, Day 2 읽기 전용 MCP Agent 검토자료, Day 3 담당자 검토와 CSV 내보내기를 단계별로 구현하는 독립 공개 실습 저장소입니다.

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
Copy-Item .env.example .env
cd ../..
python scripts/checkpoint.py reset student/00-starter
cd practice/workspace
npm run check
npm run start:backend
```

의존성은 `practice/workspace`의 전체 기능 환경에서 한 번만 설치합니다. 이후 reset은 `.venv`, `frontend/node_modules`, 로컬 비밀 설정 `.env`를 보존하고 `.env.example`을 다시 복사하므로 다시 설치하거나 키를 재입력하지 않습니다. 새 터미널에서는 저장소 루트 또는 `practice/workspace`에서 `npm run dev:frontend`를 실행합니다.

기본 주소는 backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:5173`입니다. MCP가 필요한 단계는 `npm run start:mcp`를 사용합니다.

## 체크포인트

| 경로 | 이미 완료된 상태 | 다음 교재 묶음 |
|---|---|---|
| `student/00-starter` | health, 준비 화면, CSV 6종 | 환경·입력 연결 |
| `student/01-population-ready` | 모집단 30건 로드 | 입력 오류·통제 규칙 |
| `student/02-controls-ready` | 유효 29, 정상 21, 검토 8, 입력 오류 1 | SQLite 저장 |
| `student/03-controls-persisted` | 정상 21, 검토 8, 같은 실행을 중복 없이 SQLite에 저장 | Day 1 화면 연결 |
| `student/04-day1-ui-ready` | Day 1 집계·예외·상세 화면 연결 | Day 1 검증 |
| `student/05-day1-complete` | Day 1 API·UI·SQLite 검증 완료 | Agent 구성·MCP 연결 |
| `student/06-mcp-connected` | 읽기 전용 `mock-erp` Tool 3개 | 고정 표본 선정 |
| `student/07-samples-ready` | 정상 4건·검토 8건의 고정 표본 | 권한 기반 근거 연결 |
| `student/08-evidence-ready` | U701 근거 조회·U601 권한 거부 | Skill·Agent 초안 |
| `student/09-evidence-skill-ready` | 통제 Skill과 고정 검토자료 12건 | 검토자료 API |
| `student/10-working-paper-api-ready` | 검토자료 API와 오류 구분 | Day 2 화면 연결 |
| `student/11-day2-complete` | 고정 검토자료 12건, 모두 담당자 검토 필요 | 결론 저장소 분리 |
| `student/12-review-storage-ready` | 권한 검증, 기존 기록을 남기는 검토 이력 | 중복 저장 방지·최종 화면 |
| `student/13-review-ui-ready` | 요청 ID로 중복 저장 방지, 전체 이력, 검토 화면 | 상태·완료·CSV 내보내기 |
| `student/14-agent-history-ready` | Agent 권한·실행 이력 API와 UI, 전체 검증 | 발표·마무리 |
| `instructor/complete` | Day 1–3 전체 기능과 적용 범위 템플릿 | 최종 시연 |

중간 합류나 오류 복구는 저장할 코드가 없는지 확인한 뒤 저장소 루트에서 다음처럼 실행합니다.

```powershell
python scripts/checkpoint.py reset student/09-evidence-skill-ready
cd practice/workspace
npm run check
```

직접 만든 올바른 상태를 새 체크포인트로 보관할 때만 `python scripts/checkpoint.py promote student/<새-이름>`을 사용합니다. 기존 대상은 덮어쓰지 않습니다. 전체 배포 계약은 `python scripts/checkpoint.py verify`로 검사합니다.

## 자료와 실행 중 생성되는 파일

`assets/day-1/input/`의 CSV 6종, `assets/scenario/control-card.md`, `assets/scenario/case-matrix.xlsx`, Day 2 이후의 Agent 검토자료 파일 `output/day-2/working-paper.json`은 제공된 합성 자료입니다. 체크포인트를 reset하면 시나리오 자산은 `practice/workspace/assets/scenario`에도 복사됩니다. 실제 회사 자료, 개인정보, 비밀번호, 인증정보, 운영 URL을 추가하지 마세요. Excel과 애플리케이션에서 경로는 저장소 상대경로만 사용합니다.

`.venv`, `node_modules`, `dist`, `backend/data`, SQLite/WAL/journal, pycache, 로그, 임시 JSON, 실제 검토 이벤트와 다운로드 CSV는 Git에 포함하지 않습니다. 마지막 복구 지점은 `student/14-agent-history-ready`이며 전체 기능 시연에는 `instructor/complete`를 사용합니다.

## 이용 조건

이 저장소는 교육 기간에만 임시 공개됩니다. 승인된 강사와 수강생은 해당 교육 실습 목적으로만 clone·실행·수정할 수 있으며, 외부 공유·재배포·공개 게시·상업적 또는 운영 목적 이용은 허용되지 않습니다. 공개 상태 자체가 일반 이용 허락을 의미하지 않습니다. 자세한 조건은 [LICENSE](LICENSE)를 확인하세요.
