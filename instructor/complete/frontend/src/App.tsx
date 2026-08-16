import { useCallback, useEffect, useMemo, useState } from "react"
import ReactMarkdown from "react-markdown"

type Page = "dashboard" | "population" | "exceptions" | "paper" | "review"
type RequestState = "loading" | "ready" | "empty" | "error"
type Day2RequestState = "loading" | "ready" | "not_generated" | "invalid" | "error"
type Day3RequestState = "loading" | "ready" | "blocked" | "empty" | "error"
type RecordStatus = "normal" | "review" | "error"
type ReviewConclusion = "normal" | "follow_up" | "control_exception"
type RuleResult = { rule_id: string; rule_name: string; result: "pass" | "fail" | "not_applicable"; detail: string }
type Summary = { population_count: number; valid_count: number; normal_count: number; review_count: number; input_error_count: number; duplicate_change_id_count: number }
type Source = { filename: string; row_count: number; status: string }
type PopulationRecord = {
  change_id: string
  case_id: string
  vendor_id: string
  vendor_name: string
  requested_at: string
  requested_by_name: string
  changed_at: string
  changed_by_name: string
  requested_account_token: string
  erp_account_token: string
  current_account_masked: string
  approved_by_name: string
  approved_account_token: string
  approval_ids: string[]
  evidence_ids: string[]
  evidence_attention_ids: string[]
  payment_ids: string[]
  amount_krw: number
  payment_risk: boolean
  payment_risk_note: string
  status: RecordStatus
  reason: string
  rules: RuleResult[]
}
type ApiResult = { test_run_id: string; summary: Summary; sources: Source[]; population: PopulationRecord[]; exceptions: PopulationRecord[]; input_errors: PopulationRecord[]; persistence: null | { database: string; valid_population_rows: number; rule_result_rows: number; input_error_rows: number } }
type EvidenceRecord = Record<string, string>
type WorkingPaperSample = {
  sample_id: string
  change_id: string
  case_id: string
  vendor_id: string
  vendor_name: string
  selection_reason: "교육용 고정 정상 표본" | "핵심 규칙 위반 전수"
  day1_status: "normal" | "review"
  rule_results: RuleResult[]
  source_ids: { approval_ids: string[]; evidence_ids: string[]; payment_ids: string[] }
  evidence: { vendor_change: EvidenceRecord; vendor_master: EvidenceRecord | null; approvals: EvidenceRecord[]; evidence_register: EvidenceRecord[]; payment_requests: EvidenceRecord[]; user_roles: EvidenceRecord[]; day1_result: { status: string; reason: string; rule_results: RuleResult[] } }
  agent_draft: { procedure: string; facts: string[]; draft_assessment: string; additional_follow_up: string[]; citations: string[] }
  requires_human_review: true
}
type WorkingPaperResult = {
  schema_version: string
  agent_run_id: string
  source_test_run_id: string
  generated_at: string
  mcp: { server: string; status: string; tools_used: string[]; calls: { tool: string; status: string; change_id?: string }[] }
  summary: { population_count: number; valid_count: number; sample_count: number; normal_sample_count: number; review_sample_count: number; draft_count: number; additional_follow_up_count: number }
  samples: WorkingPaperSample[]
}
type Day2ApiResult = { status: "ready" | "not_generated" | "invalid"; message: string; working_paper: WorkingPaperResult | null; validation: { valid: boolean; errors: string[] } }
type ReviewEvent = { event_id: string; review_action_id: string; source_test_run_id: string; agent_run_id: string; working_paper_generated_at: string; change_id: string; reviewer_user_id: string; conclusion: ReviewConclusion; review_comment: string; reviewed_at: string; is_current_working_paper?: boolean }
type ReviewSummary = { total_count: number; reviewed_count: number; pending_count: number; normal_count: number; follow_up_count: number; control_exception_count: number; export_ready: boolean }
type Day3ReviewItem = { sample_id: string; change_id: string; case_id: string; vendor_id: string; vendor_name: string; day1_status: "normal" | "review"; selection_reason: string; current_review: ReviewEvent | null; history: ReviewEvent[] }
type Day3ReadyResult = ReviewSummary & { status: "ready"; source_test_run_id: string; agent_run_id: string; working_paper_generated_at: string; summary: ReviewSummary; items: Day3ReviewItem[] }
type Day3BlockedResult = { status: "blocked"; reason: "not_generated" | "invalid"; blocked_reason: { code: "not_generated" | "invalid"; message: string }; items: [] }
type Day3ApiResult = Day3ReadyResult | Day3BlockedResult
type AgentPreview = { run_id: string; answer: string; tool_events: { tool: string; status: string }[]; requires_human_review: true }
type AgentRun = { run_id: string; requester_user_id: string; status: "success" | "permission_denied" | "config_error" | "tool_error" | "model_error"; tool_name: string | null; tool_status: string; model_status: string; answer: string | null; error_message: string | null; completed_at: string }
type AgentReviewState = "idle" | "loading" | "success" | "error"

class ApiError extends Error { constructor(message: string, readonly status = 0) { super(message) } }

const navItems: { id: Page; label: string; step: string }[] = [
  { id: "dashboard", label: "대시보드", step: "01" },
  { id: "population", label: "모집단 검토", step: "02" },
  { id: "exceptions", label: "예외 검토", step: "03" },
  { id: "paper", label: "검토자료", step: "04" },
  { id: "review", label: "최종 검토", step: "05" },
]

const sourceNames: Record<string, string> = {
  "vendor_changes.csv": "거래처 변경 요청",
  "vendor_master.csv": "ERP 거래처 마스터",
  "change_approvals.csv": "변경 승인 기록",
  "evidence_register.csv": "증빙 등록부",
  "payment_requests.csv": "지급 요청",
  "user_roles.csv": "사용자·역할",
}
const statusText = { normal: "정상 O", review: "검토 △", error: "오류 X" }
const ruleResultText = { pass: "충족 O", fail: "위반 X", not_applicable: "평가 불가 △" }
const conclusionText: Record<ReviewConclusion, string> = { normal: "정상", follow_up: "추가 확인", control_exception: "통제 예외" }
const formatAmount = (amount: number) => `${new Intl.NumberFormat("ko-KR").format(amount)}원`

async function requestControlTest(method: "GET" | "POST" = "GET") {
  const response = await fetch(method === "GET" ? "/api/control-test" : "/api/control-test/run", { method })
  if (!response.ok) throw new Error(`API 요청 실패 (${response.status})`)
  return response.json() as Promise<ApiResult>
}

async function requestWorkingPaper() {
  const response = await fetch("/api/day2/working-paper")
  if (!response.ok) throw new Error(`Day 2 API 요청 실패 (${response.status})`)
  return response.json() as Promise<Day2ApiResult>
}

async function requestAgentPreview(changeId: string, requesterUserId: string) {
  const response = await fetch(`/api/day2/agent-preview/${changeId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requester_user_id: requesterUserId }),
  })
  const payload = await response.json() as AgentPreview & { detail?: string }
  if (!response.ok) throw new Error(payload.detail ?? `Agent 검토 실패 (${response.status})`)
  return payload
}

async function requestAgentRuns(changeId: string, requesterUserId: string) {
  const response = await fetch(`/api/day2/agent-runs?change_id=${encodeURIComponent(changeId)}&requester_user_id=${encodeURIComponent(requesterUserId)}`)
  const payload = await response.json() as { items?: AgentRun[]; detail?: string }
  if (!response.ok) throw new Error(payload.detail ?? `Agent 실행 이력 조회 실패 (${response.status})`)
  return payload.items ?? []
}

async function requestDay3Reviews() {
  const response = await fetch("/api/day3/reviews")
  if (!response.ok) throw new ApiError(`Day 3 API 요청 실패 (${response.status})`, response.status)
  return response.json() as Promise<Day3ApiResult>
}

async function saveReview(changeId: string, body: { review_action_id: string; reviewer_user_id: string; conclusion: ReviewConclusion; review_comment: string }) {
  let response: Response
  try { response = await fetch(`/api/day3/reviews/${changeId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) }
  catch { throw new ApiError("API에 연결할 수 없습니다. 연결을 복구한 뒤 같은 요청을 다시 시도해 주세요.") }
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string | { message?: string } } | null
    const detail = typeof payload?.detail === "string" ? payload.detail : payload?.detail?.message
    throw new ApiError(detail ?? `검토 저장 실패 (${response.status})`, response.status)
  }
  return response.json() as Promise<{ status: "saved"; event: ReviewEvent; summary: ReviewSummary }>
}

function StatusBadge({ status }: { status: RecordStatus }) {
  return <span className={`status-badge ${status}`}>{statusText[status]}</span>
}

function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <header className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action}</header>
}

function StateBoundary({ state, error, onRetry, children }: { state: RequestState; error: string; onRetry: () => void; children: React.ReactNode }) {
  if (state === "loading") return <div className="state-card" role="status"><span className="spinner" />API에서 통제 테스트 자료를 불러오고 있습니다.</div>
  if (state === "empty") return <div className="state-card"><strong>표시할 모집단이 없습니다.</strong><span>입력 CSV의 거래처 변경 자료를 확인해 주세요.</span></div>
  if (state === "error") return <div className="state-card error-state"><strong>API 연결 상태를 확인해 주세요.</strong><span>{error}</span><button className="secondary-button" onClick={onRetry}>다시 연결</button></div>
  return children
}

function Dashboard({ result, day2, day3, testerUserId, onRun, running, onNavigate }: { result: ApiResult; day2: WorkingPaperResult | null; day3: Day3ReadyResult | null; testerUserId: string; onRun: () => void; running: boolean; onNavigate: (page: Page) => void }) {
  const { summary } = result
  const [agentChangeId, setAgentChangeId] = useState("")
  const [agentState, setAgentState] = useState<AgentReviewState>("idle")
  const [agentPreview, setAgentPreview] = useState<AgentPreview | null>(null)
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([])
  const [agentError, setAgentError] = useState("")
  const selectedAgentChangeId = agentChangeId || day2?.samples[0]?.change_id || ""
  const loadAgentRuns = useCallback(async () => {
    if (!selectedAgentChangeId || testerUserId !== "U701") { setAgentRuns([]); return }
    try { setAgentRuns(await requestAgentRuns(selectedAgentChangeId, testerUserId)) }
    catch { setAgentRuns([]) }
  }, [selectedAgentChangeId, testerUserId])
  useEffect(() => { void loadAgentRuns() }, [loadAgentRuns])
  const selectAgentSample = (changeId: string) => {
    setAgentChangeId(changeId)
    setAgentState("idle")
    setAgentPreview(null)
    setAgentError("")
  }
  const runAgentReview = async () => {
    if (!selectedAgentChangeId) return
    setAgentState("loading")
    setAgentPreview(null)
    setAgentError("")
    try {
      setAgentPreview(await requestAgentPreview(selectedAgentChangeId, testerUserId))
      setAgentState("success")
    } catch (reason) {
      setAgentError(reason instanceof Error ? reason.message : "Agent 검토에 실패했습니다.")
      setAgentState("error")
    } finally { await loadAgentRuns() }
  }
  const metrics = [
    ["모집단", summary.population_count, "전체 변경 요청"],
    ["유효", summary.valid_count, "규칙 테스트 대상"],
    ["검토 필요", summary.review_count, "사람의 확인 필요"],
    ["입력 오류", summary.input_error_count, "원본 값 확인"],
  ]
  return <>
    <PageHeader eyebrow="업무 시작" title="거래처 계좌 변경 통제" description="모집단 적재부터 핵심 통제 규칙 판정까지 실제 API 결과를 확인합니다." action={<button className="primary-button" onClick={onRun} disabled={running}>{running ? "테스트 실행 중…" : "통제 테스트 실행"}</button>} />
    <section className="metric-grid" aria-label="통제 테스트 요약">{metrics.map(([label, value, note], index) => <article className={`metric-card metric-${index}`} key={label}><span>{label}</span><strong>{value}건</strong><small>{note}</small></article>)}</section>
    {day2 && <section className="card day2-overview">
      <div className="section-heading"><div><p className="eyebrow">Agent 실행 결과</p><h2>Day 2 검토자료 초안</h2></div><button className="secondary-button" onClick={() => onNavigate("paper")}>검토자료 보기</button></div>
      <div className="day2-metric-grid"><div><span>고정 표본</span><strong>{day2.summary.sample_count}건</strong></div><div><span>검토자료 초안</span><strong>{day2.summary.draft_count}건</strong></div><div><span>마지막 Agent 실행</span><strong>{day2.generated_at}</strong></div></div>
      <div className="review-meta"><div><span>현재 테스트 사용자</span><strong>{testerUserId} · {testerUserId === "U701" ? "내부통제 검토자" : "지급 업무 담당자"}</strong></div><div><span>Agent 권한</span><strong>{testerUserId === "U701" ? "근거 조회 허용 · 읽기 전용" : "근거 조회 불가"}</strong></div><div><span>실행 범위</span><strong>get_case_evidence 1회 · 사람 결론 변경 불가</strong></div></div>
      <div className="agent-review-action">
        <label><span>검토 표본</span><select value={selectedAgentChangeId} onChange={(event) => selectAgentSample(event.target.value)}>{day2.samples.map((sample) => <option key={sample.change_id} value={sample.change_id}>{sample.change_id} · {sample.vendor_name}</option>)}</select></label>
        <button className="primary-button" disabled={agentState === "loading"} onClick={() => void runAgentReview()}>{agentState === "loading" ? "Agent 검토 중…" : "Agent 검토 수행"}</button>
      </div>
      {agentState === "error" && <div className="inline-message error" role="alert">{agentError}</div>}
      {agentState === "success" && agentPreview && <aside className="agent-review-result"><div><strong>Agent 검토 결과</strong><span>{agentPreview.tool_events[0]?.tool} · {agentPreview.tool_events[0]?.status}</span></div><div className="agent-review-markdown"><ReactMarkdown>{agentPreview.answer}</ReactMarkdown></div><small>{agentPreview.requires_human_review && "사람의 최종 검토가 필요합니다."} 이 결과는 저장되지 않습니다.</small></aside>}
      <section><div className="section-heading"><div><p className="eyebrow">실행 기록</p><h3>사례별 Agent 실행 이력</h3></div><span className="quiet-badge">{agentRuns.length}건</span></div>{agentRuns.length ? <ol className="timeline">{agentRuns.map((run) => <li key={run.run_id}><span className={`timeline-dot ${run.status === "success" ? "active" : ""}`} /><div><strong>{run.status} · {run.requester_user_id}</strong><p>{run.answer ?? run.error_message}</p><small>{run.completed_at} · Tool {run.tool_status} · 모델 {run.model_status}</small></div></li>)}</ol> : <p className="section-note">이 사례에 저장된 Agent 실행 이력이 없습니다.</p>}</section>
    </section>}
    {day3 && <section className="card day3-overview"><div className="section-heading"><div><p className="eyebrow">사람의 최종 결론</p><h2>Day 3 사람 검토</h2></div><button className="day3-button" onClick={() => onNavigate("review")}>최종 검토 보기</button></div><div className="day3-metric-grid"><div><span>사람 검토 완료</span><strong>{day3.reviewed_count} / {day3.total_count}</strong></div><div><span>미검토</span><strong>{day3.pending_count}건</strong></div><div><span>정상</span><strong>{day3.normal_count}건</strong></div><div><span>추가 확인</span><strong>{day3.follow_up_count}건</strong></div><div><span>통제 예외</span><strong>{day3.control_exception_count}건</strong></div></div></section>}
    <section className="card workflow-card"><div className="section-heading"><div><p className="eyebrow">업무 진행</p><h2>현재 통제 테스트 흐름</h2></div><span className="quiet-badge">{day3 ? `Day 3 · ${day3.export_ready ? "완료" : "진행 중"}` : day2 ? "Day 2 · 4 / 5" : "Day 1 · 2 / 5"}</span></div><ol className="workflow">{["모집단 확인", "규칙 테스트", "증빙 조사", "검토자료 초안", "최종 검토"].map((label, index) => { const done = day3 ? index < 4 || (index === 4 && day3.export_ready) : day2 ? index < 3 : index === 0; const current = day3 ? index === 4 && !day3.export_ready : day2 ? index === 3 : index === 1; const notes = day3 ? [`${summary.population_count}건 확인`, `${summary.review_count}건 검토 필요`, `${day2?.summary.sample_count ?? 12}건 근거 조회`, `${day2?.summary.draft_count ?? 12}건 초안`, `${day3.reviewed_count} / ${day3.total_count} 검토`] : day2 ? [`${summary.population_count}건 확인`, `${summary.review_count}건 검토 필요`, `${day2.summary.sample_count}건 근거 조회`, `${day2.summary.draft_count}건 초안`, "Day 3에서 연결"] : [`${summary.population_count}건 확인`, `${summary.review_count}건 검토 필요`, "다음 차시에서 연결", "다음 차시에서 연결", "다음 차시에서 연결"]; return <li className={done ? "done" : current ? "current" : "pending"} key={label}><span>{done ? "O" : index + 1}</span><div><strong>{label}</strong><small>{notes[index]}</small></div></li> })}</ol></section>
    <section className="card"><div className="section-heading"><div><p className="eyebrow">최근 업무</p><h2>검토 대상</h2></div><button className="text-button" onClick={() => onNavigate("exceptions")}>전체 예외 보기</button></div><div className="table-wrap"><table><thead><tr><th>변경 ID</th><th>거래처</th><th>검토 사유</th><th>요청 시각</th><th>상태</th></tr></thead><tbody>{result.exceptions.slice(0, 3).map((item) => <tr key={item.change_id}><td className="id-cell">{item.change_id}</td><td>{item.vendor_name}</td><td>{item.reason}</td><td>{item.requested_at}</td><td><StatusBadge status={item.status} /></td></tr>)}</tbody></table></div></section>
  </>
}

function PopulationReview({ result }: { result: ApiResult }) {
  const [search, setSearch] = useState("")
  const [filter, setFilter] = useState<"all" | RecordStatus>("all")
  const [selectedId, setSelectedId] = useState(result.population[0]?.change_id ?? "")
  const filtered = useMemo(() => result.population.filter((item) => (filter === "all" || item.status === filter) && `${item.change_id}${item.vendor_name}${item.requested_by_name}`.toLowerCase().includes(search.toLowerCase())), [filter, search, result.population])
  const selected = filtered.find((item) => item.change_id === selectedId) ?? filtered[0] ?? result.population[0]
  return <>
    <PageHeader eyebrow="1단계 · 모집단" title="모집단 검토" description="연결된 CSV 6종과 입력 품질을 확인하고 실제 규칙 결과를 검토합니다." />
    <section className="card"><div className="section-heading"><div><p className="eyebrow">데이터 연결</p><h2>데이터 출처 6종</h2></div><span className="status-badge normal">연결됨 O</span></div><div className="source-grid">{result.sources.map((source, index) => <div className="source-item" key={source.filename}><span className="source-mark">{index + 1}</span><div><strong>{sourceNames[source.filename]}</strong><small>{source.row_count}행 · {source.filename}</small></div><span className="connection">정상 O</span></div>)}</div></section>
    <section className="quality-grid" aria-label="데이터 품질 요약"><article className="quality-card"><span>전체 행</span><strong>{result.summary.population_count}</strong><small>100% 수신</small></article><article className="quality-card"><span>유효 데이터</span><strong>{result.summary.valid_count}</strong><small>규칙 적용 대상</small></article><article className="quality-card"><span>입력 오류</span><strong>{result.summary.input_error_count}</strong><small>R-01 분리</small></article><article className="quality-card"><span>중복 키</span><strong>{result.summary.duplicate_change_id_count}</strong><small>change_id 기준</small></article></section>
    <section className="card population-card"><div className="section-heading"><div><p className="eyebrow">거래처 변경 목록</p><h2>변경 요청 {result.summary.population_count}건</h2></div><span className="quiet-badge">검색 결과 {filtered.length}건</span></div><div className="toolbar"><label className="search-field"><span className="sr-only">거래처 변경 검색</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="거래처명, 변경 ID, 요청자 검색" /></label><label><span>상태</span><select value={filter} onChange={(event) => setFilter(event.target.value as "all" | RecordStatus)}><option value="all">전체 상태</option><option value="normal">정상 O</option><option value="review">검토 △</option><option value="error">오류 X</option></select></label></div><div className="master-detail"><div className="table-wrap"><table className="clickable-table"><thead><tr><th>변경 ID</th><th>거래처</th><th>요청자</th><th>요청 시각</th><th>상태</th></tr></thead><tbody>{filtered.length ? filtered.map((item) => <tr key={item.change_id} className={selected?.change_id === item.change_id ? "selected" : ""} tabIndex={0} onClick={() => setSelectedId(item.change_id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedId(item.change_id) }}><td className="id-cell">{item.change_id}</td><td>{item.vendor_name}</td><td>{item.requested_by_name}</td><td>{item.requested_at}</td><td><StatusBadge status={item.status} /></td></tr>) : <tr><td colSpan={5} className="empty-cell">검색 조건에 맞는 변경 요청이 없습니다.</td></tr>}</tbody></table></div>{selected && <aside className="detail-panel" aria-label="선택한 변경 요청 상세"><div className="detail-title"><div><p className="eyebrow">선택 항목</p><h3>{selected.vendor_name}</h3><span className="id-cell">{selected.change_id}</span></div><StatusBadge status={selected.status} /></div><dl><div><dt>요청자</dt><dd>{selected.requested_by_name}</dd></div><div><dt>ERP 변경자</dt><dd>{selected.changed_by_name}</dd></div><div><dt>변경 시각</dt><dd>{selected.changed_at}</dd></div><div><dt>연계 지급액</dt><dd>{formatAmount(selected.amount_krw)}</dd></div><div><dt>승인 ID</dt><dd>{selected.approval_ids.join(", ") || "기록 없음"}</dd></div><div><dt>증빙 ID</dt><dd>{selected.evidence_ids.join(", ") || "기록 없음"}</dd></div><div><dt>판정 사유</dt><dd>{selected.reason}</dd></div></dl><div className="rule-summary"><strong>핵심 규칙 결과</strong>{selected.rules.map((item) => <span className={item.result === "fail" ? "rule-fail" : ""} key={item.rule_id}>{item.rule_id} {item.rule_name} · {ruleResultText[item.result]}</span>)}</div></aside>}</div></section>
  </>
}

function ExceptionReview({ exceptions, day2Ids, onOpenPaper }: { exceptions: PopulationRecord[]; day2Ids: Set<string>; onOpenPaper: (changeId: string) => void }) {
  const [selectedId, setSelectedId] = useState(exceptions[0]?.change_id ?? "")
  useEffect(() => { if (!exceptions.some((item) => item.change_id === selectedId)) setSelectedId(exceptions[0]?.change_id ?? "") }, [exceptions, selectedId])
  const selected = exceptions.find((item) => item.change_id === selectedId) ?? exceptions[0]
  if (!selected) return <div className="state-card"><strong>검토 대상이 없습니다.</strong></div>
  const failures = selected.rules.filter((item) => item.result === "fail")
  const followUp = ["연결된 승인 기록과 ERP 변경이력 원본 확인", ...(selected.evidence_attention_ids.length ? ["미수취 또는 추가 확인 증빙의 보완 상태 확인"] : []), ...(selected.payment_risk ? ["변경 직후 지급 예정의 필요성과 승인 상태 확인"] : [])]
  return <><PageHeader eyebrow="2단계 · 예외" title="예외 검토" description="위반 규칙과 연결 승인·증빙 및 지급 참고정보를 함께 확인합니다." /><div className="exception-layout"><section className="card exception-list"><div className="section-heading"><div><p className="eyebrow">검토 대기</p><h2>예외 {exceptions.length}건</h2></div><span className="quiet-badge">미검토 {exceptions.length}</span></div>{exceptions.map((item) => <button className={`exception-item ${selected.change_id === item.change_id ? "selected" : ""}`} key={item.change_id} onClick={() => setSelectedId(item.change_id)}><div><span className="id-cell">{item.change_id}</span><strong>{item.vendor_name}</strong><p>{item.reason}</p></div><span className="risk warning">검토 X</span></button>)}</section><section className="card exception-detail"><div className="detail-title"><div><p className="eyebrow">선택한 예외</p><h2>{selected.vendor_name}</h2><span className="id-cell">{selected.change_id}</span></div><span className="risk warning">검토 X</span></div><div className="rule-callout"><span>위반 규칙</span><strong>{failures.map((item) => `${item.rule_id} ${item.rule_name}`).join(" · ")}</strong><p>{selected.reason}</p></div><h3 className="subheading">승인 계좌와 ERP 반영 정보</h3><div className="comparison"><div><span>최종 승인</span><strong>{selected.approved_account_token || "승인 기록 없음"}</strong><small>{selected.approved_by_name}</small></div><div><span>ERP 현재 계좌</span><strong>{selected.erp_account_token}</strong><small>{selected.current_account_masked}</small></div></div><h3 className="subheading">연결된 승인 및 증빙</h3><div className="reference-row">{selected.approval_ids.length ? selected.approval_ids.map((id) => <span className="reference-chip" key={id}>승인 {id}</span>) : <span className="reference-chip missing-reference">승인 기록 없음</span>}{selected.evidence_ids.map((id) => <span className="reference-chip" key={id}>증빙 {id}</span>)}</div><div className="reference-note"><strong>참고정보</strong><span>증빙 확인: {selected.evidence_attention_ids.join(", ") || "추가 확인 없음"}</span><span>지급 위험: {selected.payment_risk_note}</span><span>지급 ID: {selected.payment_ids.join(", ") || "연결 없음"}</span></div>{day2Ids.has(selected.change_id) && <button className="secondary-button paper-link-button" onClick={() => onOpenPaper(selected.change_id)}>Agent 검토자료 초안 보기</button>}<h3 className="subheading">추가 확인할 사항</h3><ul className="check-list">{followUp.map((item) => <li key={item}><span>□</span>{item}</li>)}</ul></section></div></>
}

function WorkingPaper({ state, result, error, selectedChangeId, onRetry, onOpenReview }: { state: Day2RequestState; result: Day2ApiResult | null; error: string; selectedChangeId: string; onRetry: () => void; onOpenReview: (changeId: string) => void }) {
  const samples = result?.working_paper?.samples ?? []
  const [selectedId, setSelectedId] = useState(selectedChangeId || samples[0]?.change_id || "")
  useEffect(() => { if (selectedChangeId) setSelectedId(selectedChangeId); else if (!samples.some((item) => item.change_id === selectedId)) setSelectedId(samples[0]?.change_id ?? "") }, [samples, selectedChangeId, selectedId])
  if (state === "loading") return <div className="state-card" role="status"><span className="spinner" />Agent 검토자료를 불러오고 있습니다.</div>
  if (state === "not_generated") return <div className="state-card"><strong>검토자료가 아직 생성되지 않았습니다.</strong><span>`/control-test` Skill로 working-paper.json을 생성한 뒤 다시 확인해 주세요.</span><button className="secondary-button" onClick={onRetry}>새로고침</button></div>
  if (state === "error") return <div className="state-card error-state"><strong>Day 2 API 연결 상태를 확인해 주세요.</strong><span>{error}</span><button className="secondary-button" onClick={onRetry}>다시 연결</button></div>
  if (state === "invalid") {
    const failedMcp = result?.working_paper?.mcp?.status && result.working_paper.mcp.status !== "connected"
    const empty = result?.working_paper?.samples?.length === 0
    return <div className="state-card error-state"><strong>{failedMcp ? "MCP 실행 실패가 기록된 결과입니다." : empty ? "표본 결과가 없습니다." : "working-paper.json이 유효하지 않습니다."}</strong><span>{result?.message}</span>{result?.validation.errors.map((item) => <span key={item}>{item}</span>)}<button className="secondary-button" onClick={onRetry}>파일 다시 읽기</button></div>
  }
  const paper = result?.working_paper
  const selected = samples.find((item) => item.change_id === selectedId) ?? samples[0]
  if (!paper || !selected) return <div className="state-card"><strong>표본 결과가 없습니다.</strong><button className="secondary-button" onClick={onRetry}>새로고침</button></div>
  return <>
    <PageHeader eyebrow="3단계 · 검토자료 초안" title="통제 검토자료" description="Mock ERP 근거와 Agent 초안을 표본별로 확인합니다. 모든 결론은 사람 검토 전 상태입니다." />
    <section className="card mcp-status-card"><div><p className="eyebrow">MCP 실행</p><h2>{paper.mcp.server}</h2><span className="connection">연결 O</span></div><dl><div><dt>마지막 실행</dt><dd>{paper.generated_at}</dd></div><div><dt>사용 도구</dt><dd>{paper.mcp.tools_used.join(", ")}</dd></div><div><dt>호출 건수</dt><dd>{paper.mcp.calls.length}회</dd></div></dl></section>
    <section className="day2-summary" aria-label="Day 2 검토자료 요약"><div><span>정상 표본</span><strong>{paper.summary.normal_sample_count}건</strong></div><div><span>검토 필요 표본</span><strong>{paper.summary.review_sample_count}건</strong></div><div><span>검토자료 초안</span><strong>{paper.summary.draft_count}건</strong></div><div><span>사람 검토 대기</span><strong>{paper.summary.sample_count}건</strong></div></section>
    <div className="paper-layout"><section className="card paper-sample-list"><div className="section-heading"><div><p className="eyebrow">고정 표본</p><h2>표본 {samples.length}건</h2></div></div>{samples.map((sample) => <button className={`paper-sample ${selected.change_id === sample.change_id ? "selected" : ""}`} key={sample.change_id} onClick={() => setSelectedId(sample.change_id)}><div><span className="id-cell">{sample.change_id}</span><strong>{sample.vendor_name}</strong><small>{sample.selection_reason}</small></div><StatusBadge status={sample.day1_status} /></button>)}</section>
      <section className="card paper-detail"><div className="detail-title"><div><p className="eyebrow">{selected.sample_id}</p><h2>{selected.vendor_name}</h2><span className="id-cell">{selected.change_id}</span></div><div className="paper-actions"><span className="risk caution">사람 검토 필요 △</span><button className="day3-button" onClick={() => onOpenReview(selected.change_id)}>사람 검토로 이동</button></div></div>
        <dl className="paper-meta"><div><dt>사례 ID</dt><dd>{selected.case_id}</dd></div><div><dt>거래처 ID</dt><dd>{selected.vendor_id}</dd></div><div><dt>선정 사유</dt><dd>{selected.selection_reason}</dd></div><div><dt>Day 1 상태</dt><dd>{statusText[selected.day1_status]}</dd></div></dl>
        <h3 className="subheading">Day 1 규칙 결과</h3><div className="paper-rules">{selected.rule_results.map((item) => <div key={item.rule_id}><strong>{item.rule_id} · {item.rule_name}</strong><span className={item.result === "fail" ? "rule-fail" : ""}>{ruleResultText[item.result]}</span><p>{item.detail}</p></div>)}</div>
        <h3 className="subheading">연결 참조 ID</h3><div className="reference-row">{selected.source_ids.approval_ids.length ? selected.source_ids.approval_ids.map((id) => <span className="reference-chip" key={id}>승인 {id}</span>) : <span className="reference-chip missing-reference">승인 기록 없음</span>}{selected.source_ids.evidence_ids.map((id) => <span className="reference-chip" key={id}>증빙 {id}</span>)}{selected.source_ids.payment_ids.map((id) => <span className="reference-chip" key={id}>지급 {id}</span>)}</div>
        <h3 className="subheading">증빙 등록부 메타데이터</h3><div className="evidence-list">{selected.evidence.evidence_register.length ? selected.evidence.evidence_register.map((item) => <article key={item.evidence_id}><div><strong>{item.document_type}</strong><span className="id-cell">{item.evidence_id}</span></div><p>{item.document_name}</p><dl><div><dt>등록 상태</dt><dd>{item.document_status}</dd></div><div><dt>수취 시각</dt><dd>{item.received_at || "확인 불가"}</dd></div><div><dt>확인자</dt><dd>{item.verified_by || "확인 불가"}</dd></div><div><dt>저장 참조</dt><dd>{item.storage_ref}</dd></div></dl></article>) : <p className="section-note">연결된 증빙 등록부가 없습니다.</p>}</div>
        <h3 className="subheading">승인·지급 참고정보</h3><div className="evidence-grid"><div><strong>승인 기록</strong>{selected.evidence.approvals.length ? selected.evidence.approvals.map((item) => <span key={item.approval_id}>{item.approval_id} · {item.approved_by} · {item.approved_at}</span>) : <span>승인 기록 없음 · 승인자 확인 불가</span>}</div><div><strong>지급 요청</strong>{selected.evidence.payment_requests.length ? selected.evidence.payment_requests.map((item) => <span key={item.payment_id}>{item.payment_id} · {formatAmount(Number(item.amount_krw))} · {item.payment_status}</span>) : <span>연결된 지급 요청 없음</span>}</div></div>
        <section className="agent-draft"><div className="draft-banner"><span>Agent 초안</span><strong>사람의 최종 결론이 아닙니다.</strong></div><div><h3>수행 절차</h3><p>{selected.agent_draft.procedure}</p><h3>확인 사실</h3><ul>{selected.agent_draft.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul><h3>초안 평가</h3><p>{selected.agent_draft.draft_assessment}</p><h3>추가 확인 사항</h3>{selected.agent_draft.additional_follow_up.length ? <ul>{selected.agent_draft.additional_follow_up.map((item) => <li key={item}>{item}</li>)}</ul> : <p>추가 확인 필요 사항이 기록되지 않았습니다.</p>}<div className="reference-row">{selected.agent_draft.citations.map((id) => <span className="reference-chip" key={id}>{id}</span>)}</div></div></section>
      </section>
    </div>
  </>
}

function FinalReview({ state, result, paper, error, selectedChangeId, testerUserId, onRetry, onSaved }: { state: Day3RequestState; result: Day3ApiResult | null; paper: WorkingPaperResult | null; error: string; selectedChangeId: string; testerUserId: string; onRetry: () => void; onSaved: () => Promise<void> }) {
  const items = result?.status === "ready" ? result.items : []
  const [selectedId, setSelectedId] = useState(selectedChangeId || items[0]?.change_id || "")
  const [conclusion, setConclusion] = useState<ReviewConclusion | "">("")
  const [comment, setComment] = useState("")
  const [pendingActionId, setPendingActionId] = useState("")
  const [saveState, setSaveState] = useState<"idle" | "saving" | "success" | "error">("idle")
  const [saveMessage, setSaveMessage] = useState("")
  const [exportState, setExportState] = useState<"idle" | "exporting" | "error">("idle")
  const [exportMessage, setExportMessage] = useState("")
  const selected = items.find((item) => item.change_id === selectedId) ?? items[0]
  const sample = paper?.samples.find((item) => item.change_id === selected?.change_id)

  useEffect(() => { if (selectedChangeId) setSelectedId(selectedChangeId); else if (!items.some((item) => item.change_id === selectedId)) setSelectedId(items[0]?.change_id ?? "") }, [items, selectedChangeId, selectedId])
  useEffect(() => {
    setConclusion(selected?.current_review?.conclusion ?? "")
    setComment(selected?.current_review?.review_comment ?? "")
    setPendingActionId("")
  }, [selected?.change_id, selected?.current_review?.event_id])
  useEffect(() => { setSaveState("idle"); setSaveMessage("") }, [selected?.change_id])

  const changeConclusion = (value: ReviewConclusion) => { setConclusion(value); setPendingActionId(""); setSaveState("idle") }
  const changeComment = (value: string) => { setComment(value); setPendingActionId(""); setSaveState("idle") }
  const submit = async () => {
    const trimmed = comment.trim()
    if (!conclusion || !trimmed || trimmed.length > 1000) {
      setSaveState("error"); setSaveMessage(!conclusion ? "사람의 최종 결론을 선택해 주세요." : !trimmed ? "검토 의견을 입력해 주세요." : "검토 의견은 1,000자 이하로 입력해 주세요."); return
    }
    const actionId = pendingActionId || crypto.randomUUID()
    setPendingActionId(actionId); setSaveState("saving"); setSaveMessage("검토 의견을 저장하고 있습니다.")
    try {
      await saveReview(selected.change_id, { review_action_id: actionId, reviewer_user_id: testerUserId, conclusion, review_comment: trimmed })
      await onSaved(); setPendingActionId(""); setSaveState("success"); setSaveMessage("사람의 최종 결론과 감사 이벤트를 저장했습니다.")
    } catch (reason) {
      const apiError = reason instanceof ApiError ? reason : new ApiError("알 수 없는 저장 오류")
      const prefix = apiError.status === 403 ? "권한 거부" : apiError.status === 422 ? "입력 검증 오류" : apiError.status === 0 ? "API 연결 오류" : "저장 실패"
      setSaveState("error"); setSaveMessage(`${prefix}: ${apiError.message}`)
    }
  }
  const exportCsv = async () => {
    setExportState("exporting"); setExportMessage("")
    try {
      const response = await fetch(`/api/day3/export.csv?reviewer_user_id=${encodeURIComponent(testerUserId)}`)
      if (!response.ok) { const payload = await response.json().catch(() => null) as { detail?: string } | null; throw new ApiError(payload?.detail ?? `CSV 내보내기 실패 (${response.status})`, response.status) }
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a")
      link.href = url; link.download = "day3-human-reviews.csv"; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url)
      setExportState("idle")
    } catch (reason) {
      const apiError = reason instanceof ApiError ? reason : new ApiError("API에 연결할 수 없습니다.")
      setExportState("error"); setExportMessage(`내보내기 실패: ${apiError.message}`)
    }
  }

  if (state === "loading") return <div className="state-card" role="status"><span className="spinner" />Day 3 사람 검토 목록을 불러오고 있습니다.</div>
  if (state === "error") return <div className="state-card error-state"><strong>Day 3 API에 연결할 수 없습니다.</strong><span>{error}</span><button className="secondary-button" onClick={onRetry}>다시 연결</button></div>
  if (state === "blocked" && result?.status === "blocked") return <div className="state-card error-state"><strong>{result.reason === "not_generated" ? "Day 2 검토자료가 아직 생성되지 않았습니다." : "Day 2 working-paper.json이 올바르지 않습니다."}</strong><span>{result.blocked_reason.message}</span><button className="secondary-button" onClick={onRetry}>새로고침 후 복구</button></div>
  if (state === "empty" || !items.length) return <div className="state-card"><strong>검토 목록 결과가 없습니다.</strong><span>Day 2 고정 표본 12건을 확인해 주세요.</span><button className="secondary-button" onClick={onRetry}>새로고침</button></div>
  if (!selected || !sample || result?.status !== "ready") return <div className="state-card error-state"><strong>Agent 초안 세부정보를 연결하지 못했습니다.</strong><span>Day 2와 Day 3 API를 새로고침해 주세요.</span><button className="secondary-button" onClick={onRetry}>다시 연결</button></div>

  return <>
    <PageHeader eyebrow="4단계 · 사람 검토" title="최종 검토" description="Agent 초안과 근거를 확인한 사람이 명시적으로 최종 결론과 의견을 저장합니다." action={<button className="day3-button" disabled={!result.export_ready || exportState === "exporting"} onClick={() => void exportCsv()} title={result.export_ready ? "현재 최신 결론 12건을 CSV로 내보냅니다." : `검토 ${result.pending_count}건이 남아 있습니다.`}>{exportState === "exporting" ? "CSV 준비 중…" : "CSV 내보내기"}</button>} />
    <section className="day3-summary" aria-label="Day 3 사람 검토 요약"><div><span>검토 완료</span><strong>{result.reviewed_count} / {result.total_count}</strong></div><div><span>미검토</span><strong>{result.pending_count}건</strong></div><div><span>정상</span><strong>{result.normal_count}건</strong></div><div><span>추가 확인</span><strong>{result.follow_up_count}건</strong></div><div><span>통제 예외</span><strong>{result.control_exception_count}건</strong></div></section>
    {!result.export_ready && <div className="review-notice">12건을 모두 검토해야 CSV를 내보낼 수 있습니다. 현재 {result.pending_count}건이 남았습니다.</div>}
    {exportState === "error" && <div className="inline-message error" role="alert">{exportMessage}<button className="text-button" onClick={() => void exportCsv()}>다시 시도</button></div>}
    <div className="review-layout"><section className="card review-sample-list"><div className="section-heading"><div><p className="eyebrow">고정 표본</p><h2>사람 검토 {items.length}건</h2></div></div>{items.map((item) => <button className={`review-sample ${selected.change_id === item.change_id ? "selected" : ""}`} key={item.change_id} onClick={() => setSelectedId(item.change_id)}><div><span className="id-cell">{item.change_id}</span><strong>{item.vendor_name}</strong><small>{item.selection_reason}</small></div><span className={`review-status ${item.current_review ? "complete" : "pending"}`}>{item.current_review ? `완료 · ${conclusionText[item.current_review.conclusion]}` : "미검토"}</span></button>)}</section>
      <section className="review-detail"><section className="card"><div className="detail-title"><div><p className="eyebrow">{sample.sample_id}</p><h2>{sample.vendor_name}</h2><span className="id-cell">{sample.change_id}</span></div><span className={`review-status ${selected.current_review ? "complete" : "pending"}`}>{selected.current_review ? "검토 완료" : "미검토"}</span></div>
        <dl className="paper-meta"><div><dt>Day 1 상태</dt><dd>{statusText[sample.day1_status]}</dd></div><div><dt>선정 사유</dt><dd>{sample.selection_reason}</dd></div><div><dt>사례 ID</dt><dd>{sample.case_id}</dd></div><div><dt>거래처 ID</dt><dd>{sample.vendor_id}</dd></div></dl>
        <h3 className="subheading">승인·증빙·지급 참조 ID</h3><div className="reference-row">{sample.source_ids.approval_ids.length ? sample.source_ids.approval_ids.map((id) => <span className="reference-chip" key={id}>승인 {id}</span>) : <span className="reference-chip missing-reference">승인 기록 없음</span>}{sample.source_ids.evidence_ids.map((id) => <span className="reference-chip" key={id}>증빙 {id}</span>)}{sample.source_ids.payment_ids.map((id) => <span className="reference-chip" key={id}>지급 {id}</span>)}</div>
      </section>
      <div className="review-comparison"><section className="card ai-review"><div className="review-label"><span>Agent 검토자료 초안</span><span className="risk caution">최종 결론 아님 △</span></div><h3>수행 절차</h3><p>{sample.agent_draft.procedure}</p><h3 className="subheading">확인 사실</h3><ul>{sample.agent_draft.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul><h3 className="subheading">초안 평가</h3><p>{sample.agent_draft.draft_assessment}</p><h3 className="subheading">추가 확인 사항</h3>{sample.agent_draft.additional_follow_up.length ? <ul>{sample.agent_draft.additional_follow_up.map((item) => <li key={item}>{item}</li>)}</ul> : <p>Agent가 기록한 추가 확인 사항이 없습니다.</p>}<div className="ai-notice">이 Agent 초안은 사람의 결론이 아니며 자동으로 선택되지 않습니다.</div></section>
        <section className="card human-review"><div className="review-label"><span>사람의 최종 결론</span><span className="day3-chip">검토자 {testerUserId}</span></div>{selected.current_review && <div className="current-review"><span>현재 사람 결론</span><strong>{conclusionText[selected.current_review.conclusion]}</strong><p>{selected.current_review.review_comment}</p><small>{selected.current_review.reviewed_at}</small></div>}
          <fieldset><legend>최종 결론 선택</legend><div className="decision-options">{(Object.keys(conclusionText) as ReviewConclusion[]).map((value) => <label className={conclusion === value ? "selected" : ""} key={value}><input type="radio" name="conclusion" value={value} checked={conclusion === value} onChange={() => changeConclusion(value)} />{conclusionText[value]}</label>)}</div></fieldset>
          <label className="form-field"><span>검토 의견</span><textarea rows={7} maxLength={1000} value={comment} onChange={(event) => changeComment(event.target.value)} placeholder="원본과 근거를 확인한 사람의 의견을 직접 입력하세요." /><small className="character-count">{comment.length} / 1,000자</small></label>
          <div className="review-meta"><div><span>현재 검토자</span><strong>{testerUserId} · {testerUserId === "U701" ? "내부통제 검토자" : "지급 업무 담당자"}</strong></div><div><span>저장 방식</span><strong>기존 기록을 남기는 검토 이력</strong></div></div><button className="day3-button full-button" disabled={saveState === "saving"} onClick={() => void submit()}>{saveState === "saving" ? "저장 중…" : selected.current_review ? "수정 의견 저장" : "최종 결론 저장"}</button>{saveMessage && <div className={`inline-message ${saveState}`} role={saveState === "error" ? "alert" : "status"}>{saveMessage}{saveState === "error" && pendingActionId && <button className="text-button" onClick={() => void submit()}>같은 요청 다시 시도</button>}</div>}
        </section></div>
      <section className="card"><div className="section-heading"><div><p className="eyebrow">기존 기록을 남기는 저장 방식</p><h2>검토 이력</h2></div><span className="quiet-badge">{selected.history.length}건</span></div>{selected.history.length ? <ol className="timeline">{selected.history.map((event) => <li key={event.event_id}><span className={`timeline-dot ${event.is_current_working_paper ? "active" : ""}`} /><div><strong>{conclusionText[event.conclusion]} · {event.reviewer_user_id}</strong><span className="timeline-draft">{event.is_current_working_paper ? "현재 Agent 초안" : "이전 Agent 초안"}</span><p>{event.review_comment}</p><small>{event.reviewed_at} · {event.working_paper_generated_at}</small></div></li>)}</ol> : <p className="section-note">아직 저장된 사람 검토 이력이 없습니다.</p>}</section>
    </section></div>
  </>
}

function App() {
  const [page, setPage] = useState<Page>("dashboard")
  const [testerUserId, setTesterUserId] = useState("U701")
  const [requestState, setRequestState] = useState<RequestState>("loading")
  const [result, setResult] = useState<ApiResult | null>(null)
  const [error, setError] = useState("")
  const [day2State, setDay2State] = useState<Day2RequestState>("loading")
  const [day2Result, setDay2Result] = useState<Day2ApiResult | null>(null)
  const [day2Error, setDay2Error] = useState("")
  const [day3State, setDay3State] = useState<Day3RequestState>("loading")
  const [day3Result, setDay3Result] = useState<Day3ApiResult | null>(null)
  const [day3Error, setDay3Error] = useState("")
  const [paperSelectedId, setPaperSelectedId] = useState("")
  const [reviewSelectedId, setReviewSelectedId] = useState("")
  const [running, setRunning] = useState(false)
  const [notice, setNotice] = useState("")
  const current = navItems.find((item) => item.id === page) ?? navItems[0]
  const load = useCallback(async () => {
    setRequestState("loading"); setError("")
    try { const next = await requestControlTest(); setResult(next); setRequestState(next.summary.population_count ? "ready" : "empty") }
    catch (reason) { setRequestState("error"); setError(reason instanceof Error ? reason.message : "알 수 없는 연결 오류") }
  }, [])
  const loadDay2 = useCallback(async () => {
    setDay2State("loading"); setDay2Error("")
    try { const next = await requestWorkingPaper(); setDay2Result(next); setDay2State(next.status) }
    catch (reason) { setDay2State("error"); setDay2Error(reason instanceof Error ? reason.message : "Day 2 API 연결 오류") }
  }, [])
  const loadDay3 = useCallback(async () => {
    setDay3State("loading"); setDay3Error("")
    try { const next = await requestDay3Reviews(); setDay3Result(next); setDay3State(next.status === "blocked" ? "blocked" : next.items.length ? "ready" : "empty") }
    catch (reason) { setDay3State("error"); setDay3Error(reason instanceof Error ? reason.message : "Day 3 API 연결 오류") }
  }, [])
  useEffect(() => { void load(); void loadDay2(); void loadDay3() }, [load, loadDay2, loadDay3])
  const navigate = (nextPage: Page) => { setPage(nextPage); setNotice("") }
  const openPaper = (changeId: string) => { setPaperSelectedId(changeId); setPage("paper"); setNotice("") }
  const openReview = (changeId: string) => { setReviewSelectedId(changeId); setPage("review"); setNotice("") }
  const runControlTest = async () => {
    setRunning(true); setNotice("")
    try { const next = await requestControlTest("POST"); setResult(next); setRequestState("ready"); setPage("exceptions"); setNotice(`통제 테스트와 SQLite 저장이 완료되었습니다. 검토 대상 ${next.summary.review_count}건입니다.`) }
    catch (reason) { setRequestState("error"); setError(reason instanceof Error ? reason.message : "통제 테스트 실행 오류") }
    finally { setRunning(false) }
  }
  const workingPaper = day2State === "ready" ? day2Result?.working_paper ?? null : null
  const day3Ready = day3State === "ready" && day3Result?.status === "ready" ? day3Result : null
  const day2Ids = useMemo(() => new Set(workingPaper?.samples.map((sample) => sample.change_id) ?? []), [workingPaper])
  let content: React.ReactNode = null
  if (result) {
    if (page === "dashboard") content = <Dashboard result={result} day2={workingPaper} day3={day3Ready} testerUserId={testerUserId} onRun={runControlTest} running={running} onNavigate={navigate} />
    if (page === "population") content = <PopulationReview result={result} />
    if (page === "exceptions") content = <ExceptionReview exceptions={result.exceptions} day2Ids={day2Ids} onOpenPaper={openPaper} />
    if (page === "paper") content = <WorkingPaper state={day2State} result={day2Result} error={day2Error} selectedChangeId={paperSelectedId} onRetry={() => void loadDay2()} onOpenReview={openReview} />
    if (page === "review") content = <FinalReview state={day3State} result={day3Result} paper={workingPaper} error={day3Error} selectedChangeId={reviewSelectedId} testerUserId={testerUserId} onRetry={() => { void loadDay2(); void loadDay3() }} onSaved={loadDay3} />
  }
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark">AX</span><div><strong>내부통제 AX</strong><small>업무 혁신 과정</small></div></div><div className="control-context"><span>현재 통제</span><strong>거래처 계좌 변경</strong><small>CTL-VC-001</small></div><nav aria-label="통제 테스트 단계">{navItems.map((item) => <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => navigate(item.id)} aria-current={page === item.id ? "page" : undefined}><span>{item.step}</span>{item.label}</button>)}</nav><div className="sidebar-note"><strong>교육용 합성자료</strong><p>입력 CSV는 읽기 전용이며 실제 개인정보를 사용하지 않습니다.</p></div></aside><div className="workspace"><header className="topbar"><div><strong>내부통제 테스트 Agent 과정</strong><span>{current.label}</span></div><div className="topbar-actions"><span className={`status-badge ${requestState === "error" ? "error" : requestState === "loading" ? "review" : "normal"}`}>{requestState === "error" ? "API 오류 X" : requestState === "loading" ? "API 연결 중 △" : "API 연결 O"}</span><label className="user-role"><span>현재 테스트 사용자</span><select value={testerUserId} onChange={(event) => setTesterUserId(event.target.value)}><option value="U701">U701 · 내부통제 검토자</option><option value="U601">U601 · 지급 업무 담당자</option></select><small>교육용 역할 시뮬레이션 · 실제 로그인 아님</small></label></div></header><main className="main-content"><StateBoundary state={requestState} error={error} onRetry={() => void load()}>{content}</StateBoundary></main></div>{notice && <div className="toast" role="status"><span>O</span>{notice}<button aria-label="알림 닫기" onClick={() => setNotice("")}>×</button></div>}</div>
}

export default App
