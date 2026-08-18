import { useEffect, useState } from "react"

type Rule = { rule_id: string; rule_name: string; result: string; detail: string }
type Case = { change_id: string; vendor_name: string; status: string; reason: string; approval_ids: string[]; evidence_ids: string[]; rules: Rule[] }
type Day1 = { summary: Record<string, number>; exceptions: Case[] }
type PaperSample = { change_id: string; agent_draft: { draft_assessment: string }; requires_human_review: true }
type Paper = { summary: { sample_count: number; normal_sample_count: number; review_sample_count: number; draft_count: number }; samples: PaperSample[] }
type ReviewEvent = { review_action_id: string; reviewer_user_id: string; conclusion: string; review_comment: string; reviewed_at: string }
type ReviewItem = { change_id: string; vendor_name: string; current_review: ReviewEvent | null; history: ReviewEvent[] }
type ReviewSummary = { total_count: number; reviewed_count: number; pending_count: number; normal_count: number; follow_up_count: number; control_exception_count: number; export_ready: boolean }

const labels: Record<string, string> = { population_count: "전체", valid_count: "유효", normal_count: "정상", review_count: "검토 필요", input_error_count: "입력 오류" }

export default function App() {
  const [day1, setDay1] = useState<Day1 | null>(null)
  const [paper, setPaper] = useState<Paper | null>(null)
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary | null>(null)
  const [selected, setSelected] = useState("CHG-2608-023")
  const [reviewer, setReviewer] = useState("U701")
  const [conclusion, setConclusion] = useState("normal")
  const [comment, setComment] = useState("검토 완료")
  const [actionId, setActionId] = useState(crypto.randomUUID())
  const [notice, setNotice] = useState("")
  const loadReviews = () => fetch("/api/day3/reviews").then((response) => response.json()).then((payload) => { setReviews(payload.items ?? []); setReviewSummary(payload.summary ?? null) })
  useEffect(() => {
    fetch("/api/control-test/run", { method: "POST" }).then((response) => response.json()).then(setDay1)
    fetch("/api/day2/working-paper").then((response) => response.json()).then((payload) => setPaper(payload.working_paper))
    loadReviews()
  }, [])
  const save = async () => {
    const response = await fetch(`/api/day3/reviews/${selected}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ review_action_id: actionId, reviewer_user_id: reviewer, conclusion, review_comment: comment }) })
    if (!response.ok) return setNotice(`저장 거부 (${response.status})`)
    setNotice("저장 완료")
    setActionId(crypto.randomUUID())
    await loadReviews()
  }
  const review = reviews.find((item) => item.change_id === selected)
  const draft = paper?.samples.find((item) => item.change_id === selected)
  const exportCsv = async () => {
    const response = await fetch(`/api/day3/export.csv?reviewer_user_id=${encodeURIComponent(reviewer)}`)
    if (!response.ok) return setNotice(`CSV 내보내기 거부 (${response.status})`)
    const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a")
    link.href = url; link.download = "human-reviews.csv"; link.click(); URL.revokeObjectURL(url)
  }
  return <main><p className="eyebrow">담당자 검토</p><h1>거래처 변경 통제</h1><section className="metrics">{day1 && Object.entries(day1.summary).map(([key, value]) => <div key={key}><strong>{labels[key]}</strong><span>{value}</span></div>)}</section>{reviewSummary && <section className="metrics"><div><strong>검토 완료</strong><span>{reviewSummary.reviewed_count} / {reviewSummary.total_count}</span></div><div><strong>미검토</strong><span>{reviewSummary.pending_count}</span></div><div><strong>정상</strong><span>{reviewSummary.normal_count}</span></div><div><strong>추가 확인</strong><span>{reviewSummary.follow_up_count}</span></div><div><strong>통제 예외</strong><span>{reviewSummary.control_exception_count}</span></div><button disabled={!reviewSummary.export_ready} onClick={exportCsv}>CSV 내보내기</button></section>}<div className="layout"><section><h2>표본 12건</h2>{paper?.samples.map((sample) => <button className={selected === sample.change_id ? "selected" : ""} key={sample.change_id} onClick={() => setSelected(sample.change_id)}>{sample.change_id}</button>)}</section><section><h2>{selected}</h2><h3>Agent 초안</h3><p>{draft?.agent_draft.draft_assessment}</p><h3>최종 검토 결과</h3><label>현재 테스트 사용자<select value={reviewer} onChange={(event) => setReviewer(event.target.value)}><option>U701</option><option>U601</option></select></label><small>교육용 역할 시뮬레이션이며 실제 로그인은 아닙니다.</small><select value={conclusion} onChange={(event) => setConclusion(event.target.value)}><option value="normal">정상</option><option value="follow_up">추가 확인</option><option value="control_exception">통제 예외</option></select><textarea value={comment} onChange={(event) => setComment(event.target.value)} /><button onClick={save}>검토 저장</button><p role="status">{notice}</p><p>현재 결론: {review?.current_review?.conclusion ?? "미검토"}</p><h3>전체 이력</h3>{review?.history.map((event) => <article key={event.review_action_id}><strong>{event.conclusion}</strong><p>{event.review_comment}</p><small>{event.reviewer_user_id} · {event.reviewed_at}</small></article>)}</section></div></main>
}
