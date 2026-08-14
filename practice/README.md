# 강사 리허설 workspace

저장소 루트에서 다음 명령으로 체크포인트를 `practice/workspace`에 복구합니다.

```text
python scripts/checkpoint.py reset student/00-starter
```

`practice/workspace`는 Git에서 제외됩니다. reset은 설치한 `.venv`와 `frontend/node_modules`를 보존하지만 SQLite, 빌드 결과와 로그는 보존하지 않습니다.
