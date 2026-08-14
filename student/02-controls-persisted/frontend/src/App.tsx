import { useEffect, useState } from "react"

type Payload = { summary: Record<string, number>; exceptions: { change_id: string; reason: string }[]; input_errors: { change_id: string; reason: string }[]; persistence: { database: string } | null }

export default function App() {
  const [data, setData] = useState<Payload | null>(null)
  const [error, setError] = useState("")
  const load = (persist = false) => { setError(""); fetch(persist ? "/api/control-test/run" : "/api/control-test", { method: persist ? "POST" : "GET" }).then((response) => response.ok ? response.json() : Promise.reject(new Error("통제 테스트 API 오류"))).then(setData).catch((reason: Error) => setError(reason.message)) }
  useEffect(() => load(), [])
  if (error) return <main><h1>통제 테스트 오류</h1><p role="alert">{error}</p><button onClick={() => load()}>다시 시도</button></main>
  return <main><p className="eyebrow">Day 1 · 규칙과 저장</p><h1>거래처 변경 통제</h1><button onClick={() => load(true)}>판정하고 SQLite 저장</button><section>{data && Object.entries(data.summary).map(([key, value]) => <div key={key}><strong>{key}</strong><span>{value}</span></div>)}</section><p>{data?.persistence ? `저장됨: ${data.persistence.database}` : "저장 전"}</p><section><strong>검토 필요</strong><span>{data?.exceptions.map((item) => item.change_id).join(", ")}</span></section></main>
}
