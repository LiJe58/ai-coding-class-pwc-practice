# 리허설 workspace

`practice/workspace`는 Git에서 제외되는 실행 폴더입니다. 의존성을 한 번만 설치하려면 먼저 강사용 전체 기능 포함 환경을 설치한 뒤 starter로 reset합니다.

```powershell
python scripts/checkpoint.py reset instructor/complete
cd practice/workspace
npm run setup
Copy-Item .env.example .env
cd ../..
python scripts/checkpoint.py reset student/00-starter
```

이후 `python scripts/checkpoint.py reset <체크포인트>`는 `.venv`, `frontend/node_modules`, `.env`를 보존하고, 강사용 `.env.example`과 공통 `assets/scenario`를 작업공간에 다시 복사합니다. 각 상태에서 `npm run check`, `npm run start:backend`, `npm run dev:frontend`를 사용합니다.
