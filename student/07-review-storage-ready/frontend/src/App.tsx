import { useEffect, useState } from "react"

type Rule = { rule_id: string; rule_name: string; result: string; detail: string }
type Case = { change_id: string; vendor_name: string; status: string; reason: string; approval_ids: string[]; evidence_ids: string[]; rules: Rule[] }
type Payload = { summary: Record<string, number>; population: Case[]; exceptions: Case[]; input_errors: Case[] }
type WorkingPaper = { summary: { sample_count: number; normal_sample_count: number; review_sample_count: number; draft_count: number }; samples: { change_id: string; agent_draft: { draft_assessment: string }; requires_human_review: true }[] }

const labels: Record<string, string> = { population_count: "전체", valid_count: "유효", normal_count: "정상", review_count: "검토 필요", input_error_count: "입력 오류" }

export default function App() {
  const [data, setData] = useState<Payload | null>(null)
  const [selected, setSelected] = useState("CHG-2608-023")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [paper, setPaper] = useState<WorkingPaper | null>(null)
  const load = () => { setLoading(true); setError(""); fetch("/api/control-test/run", { method: "POST" }).then((response) => response.ok ? response.json() : Promise.reject(new Error("통제 테스트 API 오류"))).then(setData).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false)) }
  useEffect(load, [])
  useEffect(() => { fetch("/api/day2/working-paper").then((response) => response.json()).then((payload) => setPaper(payload.working_paper)) }, [])
  if (loading) return <main><h1>Day 1 결과</h1><p role="status">데이터를 불러오는 중입니다.</p></main>
  if (error) return <main><h1>Day 1 결과</h1><p className="error" role="alert">{error}</p><button onClick={load}>다시 시도</button></main>
  const detail = data?.exceptions.find((item) => item.change_id === selected)
  return <main><p className="eyebrow">Day 2 완료</p><h1>거래처 변경 통제</h1><section className="metrics">{data && Object.entries(data.summary).map(([key, value]) => <div key={key}><strong>{labels[key]}</strong><span>{value}</span></div>)}</section>{paper && <section><h2>Agent 통제조서</h2><p>표본 {paper.summary.sample_count} · 정상 {paper.summary.normal_sample_count} · 검토 필요 {paper.summary.review_sample_count} · 초안 {paper.summary.draft_count}</p>{paper.samples.map((sample) => <article key={sample.change_id}><strong>{sample.change_id}</strong><span>사람 검토 필요</span><p>{sample.agent_draft.draft_assessment}</p></article>)}</section>}<div className="layout"><section><h2>예외 목록</h2>{data?.exceptions.map((item) => <button className={selected === item.change_id ? "selected" : ""} key={item.change_id} onClick={() => setSelected(item.change_id)}>{item.change_id} · {item.vendor_name}</button>)}</section><section><h2>{detail?.change_id} 상세</h2><p>{detail?.reason}</p>{detail?.rules.map((rule) => <div key={rule.rule_id}><strong>{rule.rule_id} · {rule.rule_name}</strong><span>{rule.result}</span><small>{rule.detail}</small></div>)}<p>승인 {detail?.approval_ids.join(", ") || "없음"} · 증빙 {detail?.evidence_ids.join(", ")}</p></section></div></main>
}
