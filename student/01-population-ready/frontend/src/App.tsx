import { useEffect, useState } from "react"

type Payload = { summary: { population_count: number; valid_count: number; input_error_count: number }; first_change_id: string; last_change_id: string; input_errors: { change_id: string; reasons: string[] }[] }

export default function App() {
  const [data, setData] = useState<Payload | null>(null)
  const [error, setError] = useState("")
  const load = () => { setError(""); fetch("/api/control-test").then((response) => response.ok ? response.json() : Promise.reject(new Error("모집단 API 오류"))).then(setData).catch((reason: Error) => setError(reason.message)) }
  useEffect(load, [])
  if (error) return <main><h1>모집단 연결 오류</h1><p role="alert">{error}</p><button onClick={load}>다시 시도</button></main>
  return <main><p className="eyebrow">Day 1 · 모집단</p><h1>거래처 변경 모집단</h1><p>{data ? `${data.first_change_id} ~ ${data.last_change_id}` : "불러오는 중"}</p><section>{data && Object.entries(data.summary).map(([key, value]) => <div key={key}><strong>{key}</strong><span>{value}</span></div>)}</section>{data?.input_errors.map((item) => <section className="error" key={item.change_id}><strong>{item.change_id}</strong><small>{item.reasons.join(", ")}</small></section>)}</main>
}
