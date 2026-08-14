import { useEffect, useState } from "react"

type Health = { status: string; message: string }

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState("")

  const load = () => {
    setError("")
    fetch("/api/health")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("health API 오류")))
      .then(setHealth)
      .catch((reason: Error) => setError(reason.message))
  }

  useEffect(load, [])
  return <main>
    <p className="eyebrow">AI Coding Class</p>
    <h1>실습 준비 완료</h1>
    <p>CSV 6종을 보존한 상태에서 Day 1 구현을 시작합니다.</p>
    {error ? <section className="error" role="alert">{error}<button onClick={load}>다시 시도</button></section> :
      <section aria-live="polite"><strong>처리 영역</strong><span>{health?.status === "ready" ? "정상" : "확인 중"}</span><small>{health?.message}</small></section>}
  </main>
}
