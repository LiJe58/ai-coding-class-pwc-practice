from fastapi import FastAPI


app = FastAPI(title="Internal Control Practice Starter")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ready", "message": "실습 처리 영역이 준비되었습니다."}
