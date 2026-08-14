import { useEffect, useRef, useState } from "react"

type Rule = { rule_id: string; rule_name: string; result: string; detail: string }
type Case = { change_id: string; vendor_name: string; status: string; reason: string; approval_ids: string[]; evidence_ids: string[]; rules: Rule[] }
type Day1 = { summary: Record<string, number>; exceptions: Case[] }
type PaperSample = { change_id: string; agent_draft: { draft_assessment: string }; requires_human_review: true }
type Paper = { summary: { sample_count: number; normal_sample_count: number; review_sample_count: number; draft_count: number }; samples: PaperSample[] }
type ReviewEvent = { review_action_id: string; reviewer_user_id: string; conclusion: string; review_comment: string; reviewed_at: string }
type ReviewItem = { change_id: string; vendor_name: string; current_review: ReviewEvent | null; history: ReviewEvent[] }
type ReviewSummary = { total_count: number; reviewed_count: number; pending_count: number; normal_count: number; follow_up_count: number; control_exception_count: number; export_ready: boolean }
type AgentRun = { agent_run_id: string; requester_user_id: string; status: string; tool_name: string; tool_status: string; response_text: string; started_at: string }
type AgentResult = { status: string; message: string }

const labels: Record<string, string> = { population_count: "전체", valid_count: "유효", normal_count: "정상", review_count: "검토 필요", input_error_count: "입력 오류" }
const agentStatus: Record<string, string> = { success: "성공", permission_denied: "권한 거부", config_error: "설정 오류", tool_error: "Tool 오류", model_error: "모델 오류" }
const users = {
  U701: { role: "내부통제 검토자", permissions: "CONTROL_REVIEW" },
  U601: { role: "지급 요청자", permissions: "PAYMENT_REQUEST" },
}

export default function App() {
  const [day1, setDay1] = useState<Day1 | null>(null)
  const [paper, setPaper] = useState<Paper | null>(null)
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary | null>(null)
  const [selected, setSelected] = useState("CHG-2608-023")
  const [reviewer, setReviewer] = useState<keyof typeof users>("U701")
  const [conclusion, setConclusion] = useState("normal")
  const [comment, setComment] = useState("검토 완료")
  const [actionId, setActionId] = useState(crypto.randomUUID())
  const [notice, setNotice] = useState("")
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentResult, setAgentResult] = useState<AgentResult | null>(null)
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([])
  const [agentHistoryNotice, setAgentHistoryNotice] = useState("")
  const agentViewId = useRef(0)

  const loadReviews = () => fetch("/api/day3/reviews")
    .then((response) => response.json())
    .then((payload) => { setReviews(payload.items ?? []); setReviewSummary(payload.summary ?? null) })

  const loadAgentRuns = async (changeId: string, userId: string, viewId: number) => {
    try {
      const response = await fetch(`/api/day2/agent-runs?change_id=${changeId}&requester_user_id=${userId}`)
      if (viewId !== agentViewId.current) return
      if (response.ok) {
        const payload = await response.json()
        setAgentRuns(payload.runs ?? [])
        setAgentHistoryNotice("")
        return
      }
      setAgentRuns([])
      setAgentHistoryNotice(response.status === 403 ? "현재 사용자는 실행 이력을 조회할 권한이 없습니다." : "실행 이력을 불러오지 못했습니다.")
    } catch {
      if (viewId !== agentViewId.current) return
      setAgentRuns([])
      setAgentHistoryNotice("실행 이력을 불러오지 못했습니다.")
    }
  }

  useEffect(() => {
    fetch("/api/control-test/run", { method: "POST" }).then((response) => response.json()).then(setDay1)
    fetch("/api/day2/working-paper").then((response) => response.json()).then((payload) => setPaper(payload.working_paper))
    loadReviews()
  }, [])

  useEffect(() => {
    const viewId = ++agentViewId.current
    setAgentLoading(false)
    setAgentResult(null)
    loadAgentRuns(selected, reviewer, viewId)
  }, [selected, reviewer])

  const save = async () => {
    const response = await fetch(`/api/day3/reviews/${selected}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_action_id: actionId, reviewer_user_id: reviewer, conclusion, review_comment: comment }),
    })
    if (!response.ok) return setNotice(`저장 거부 (${response.status})`)
    setNotice("저장 완료")
    setActionId(crypto.randomUUID())
    await loadReviews()
  }

  const runAgent = async () => {
    const viewId = ++agentViewId.current
    setAgentLoading(true)
    setAgentResult(null)
    try {
      const response = await fetch(`/api/day2/agent-preview/${selected}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requester_user_id: reviewer }),
      })
      const payload = await response.json()
      if (viewId !== agentViewId.current) return
      if (response.ok) {
        setAgentResult({ status: payload.run.status, message: payload.run.response_text })
      } else {
        setAgentResult({ status: payload.detail?.status ?? "model_error", message: payload.detail?.message ?? `Agent 실행 실패 (${response.status})` })
      }
      setAgentLoading(false)
      await loadAgentRuns(selected, reviewer, viewId)
    } catch {
      if (viewId !== agentViewId.current) return
      setAgentLoading(false)
      setAgentResult({ status: "model_error", message: "Agent API에 연결하지 못했습니다." })
    }
  }

  const review = reviews.find((item) => item.change_id === selected)
  const draft = paper?.samples.find((item) => item.change_id === selected)
  const currentUser = users[reviewer]
  const download = async () => {
    const response = await fetch(`/api/day3/export.csv?reviewer_user_id=${reviewer}`)
    if (!response.ok) return setNotice(`내보내기 거부 (${response.status})`)
    const url = URL.createObjectURL(await response.blob())
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = "day3-human-reviews.csv"
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return <main>
    <p className="eyebrow">Day 3 Agent 실행 이력</p>
    <h1>거래처 변경 통제</h1>
    <section className="metrics">
      {day1 && Object.entries(day1.summary).map(([key, value]) => <div key={key}><strong>{labels[key]}</strong><span>{value}</span></div>)}
    </section>
    {reviewSummary && <section>
      <h2>완료 상태</h2>
      <p>{reviewSummary.reviewed_count}/{reviewSummary.total_count} 완료 · {reviewSummary.pending_count}건 대기 · 정상 {reviewSummary.normal_count} · 추가 확인 {reviewSummary.follow_up_count} · 통제 예외 {reviewSummary.control_exception_count}</p>
      <button disabled={!reviewSummary.export_ready} onClick={download}>CSV export</button>
    </section>}
    <div className="layout">
      <section>
        <h2>표본 12건</h2>
        {paper?.samples.map((sample) => <button className={selected === sample.change_id ? "selected" : ""} key={sample.change_id} onClick={() => setSelected(sample.change_id)}>{sample.change_id}</button>)}
      </section>
      <section>
        <h2>{selected}</h2>
        <h3>Agent 초안</h3>
        <p>{draft?.agent_draft.draft_assessment}</p>
        <h3>현재 테스트 사용자</h3>
        <select value={reviewer} onChange={(event) => setReviewer(event.target.value as keyof typeof users)}><option>U701</option><option>U601</option></select>
        <small>교육용 역할 시뮬레이션이며 실제 로그인은 아닙니다.</small>
        <article className="agent-card">
          <strong>Agent 권한</strong>
          <p>현재 사용자: {reviewer}</p>
          <p>역할·permissions: {currentUser.role} · {currentUser.permissions}</p>
          <p>허용 Tool: get_case_evidence</p>
          <p>데이터 접근: 읽기 전용 · 최대 Tool 호출: 1회</p>
          <p>사람 결론 변경: 불가 · 실행 결과: SQLite 기록</p>
        </article>
        <button disabled={agentLoading} onClick={runAgent}>{agentLoading ? "Agent 확인 중…" : "Agent로 다시 확인"}</button>
        {agentResult && <p className={`agent-result ${agentResult.status}`} role="status"><strong>{agentStatus[agentResult.status] ?? agentResult.status}</strong> · {agentResult.message}</p>}
        <h3>사람 결론</h3>
        <select value={conclusion} onChange={(event) => setConclusion(event.target.value)}><option value="normal">정상</option><option value="follow_up">추가 확인</option><option value="control_exception">통제 예외</option></select>
        <textarea value={comment} onChange={(event) => setComment(event.target.value)} />
        <button onClick={save}>검토 저장</button>
        <p role="status">{notice}</p>
        <p>현재 결론: {review?.current_review?.conclusion ?? "미검토"}</p>
        <h3>전체 이력</h3>
        {review?.history.map((event) => <article key={event.review_action_id}><strong>{event.conclusion}</strong><p>{event.review_comment}</p><small>{event.reviewer_user_id} · {event.reviewed_at}</small></article>)}
        <h3>Agent 실행 이력</h3>
        {agentHistoryNotice && <p>{agentHistoryNotice}</p>}
        {!agentHistoryNotice && agentRuns.length === 0 && <p>저장된 실행 이력이 없습니다.</p>}
        <div className="agent-history">
          {agentRuns.map((run) => <article key={run.agent_run_id}>
            <strong>{agentStatus[run.status] ?? run.status}</strong>
            <p>{run.tool_name} · {run.tool_status}</p>
            <p>{run.response_text}</p>
            <small>{run.requester_user_id} · {run.started_at}</small>
          </article>)}
        </div>
      </section>
    </div>
  </main>
}
