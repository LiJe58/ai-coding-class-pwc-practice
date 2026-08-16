import { useEffect, useMemo, useState } from "react"

type Page = "dashboard" | "population" | "exceptions"
type Rule = { rule_id: string; rule_name: string; result: string; detail: string }
type Case = {
  change_id: string
  case_id?: string
  vendor_id?: string
  vendor_name?: string
  request_id?: string
  requested_at?: string
  requested_by?: string
  changed_at?: string
  changed_by?: string
  status?: "normal" | "review" | "error"
  reason?: string
  approval_ids?: string[]
  evidence_ids?: string[]
  rules?: Rule[]
}
type Payload = {
  summary: Record<string, number>
  population: Case[]
  exceptions?: Case[]
  input_errors?: Case[]
  persistence?: { database: string; valid_population_rows: number }
}

// Each checkpoint is a standalone snapshot. Later snapshots advance this number and add one visible layer.
const stage: number = 8
const labels: Record<string, string> = {
  population_count: "모집단",
  valid_count: "유효",
  normal_count: "정상",
  review_count: "검토 필요",
  input_error_count: "입력 오류",
}
const statusText = { normal: "정상", review: "검토 필요", error: "입력 오류" }
const resultText = { pass: "통과", fail: "위반", not_applicable: "제외" }

async function requestControlTest(): Promise<Payload> {
  const response = await fetch("/api/control-test/run", { method: "POST" })
  if (!response.ok) throw new Error(`모집단 API 오류 (${response.status})`)
  return response.json() as Promise<Payload>
}

function StatusBadge({ status }: { status: Case["status"] }) {
  if (!status) return null
  return <span className={`status-badge ${status}`}>{statusText[status]}</span>
}

function PageHeader({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <header className="page-header"><div><p className="eyebrow">Day 1 · 내부통제 학습</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action}</header>
}

function StateCard({ loading, error, onRetry }: { loading: boolean; error: string; onRetry: () => void }) {
  if (loading) return <div className="state-card" role="status"><span className="spinner" /><strong>모집단을 불러오는 중입니다.</strong><span>CSV 입력자료를 읽고 있습니다.</span></div>
  if (error) return <div className="state-card error-state" role="alert"><strong>API 연결 상태를 확인해주세요.</strong><span>{error}</span><button className="secondary-button" onClick={onRetry}>다시 시도</button></div>
  return null
}

function Shell({ page, setPage, children, ready }: { page: Page; setPage: (page: Page) => void; children: React.ReactNode; ready: boolean }) {
  const nav: { id: Page; label: string; step: string; enabled: boolean }[] = [
    { id: "dashboard", label: "대시보드", step: "01", enabled: true },
    { id: "population", label: "모집단 확인", step: "02", enabled: true },
    { id: "exceptions", label: "예외 검토", step: "03", enabled: stage >= 2 },
  ]
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark">AX</span><div><strong>내부통제 AX</strong><small>실습용 업무 화면</small></div></div><div className="control-context"><span>현재 통제</span><strong>거래처 계좌 변경</strong><small>CTL-VC-001</small></div><nav aria-label="통제 테스트 단계">{nav.map((item) => <button key={item.id} className={`${page === item.id ? "active" : ""} ${!item.enabled ? "prepared" : ""}`} disabled={!item.enabled} onClick={() => setPage(item.id)} aria-current={page === item.id ? "page" : undefined}><span>{item.step}</span>{item.label}</button>)}{stage >= 4 && <><button className="prepared" disabled title="다음 차시에서 연결됩니다."><span>04</span>검토자료 <small>(준비)</small></button><button className="prepared" disabled title="다음 차시에서 연결됩니다."><span>05</span>최종 검토 <small>(준비)</small></button></>}</nav><div className="sidebar-note"><strong>{ready ? "현재 단계 진행 중" : "입력자료 준비"}</strong><p>{stage < 2 ? "먼저 모집단 30건을 화면에서 확인합니다." : "실습 단계마다 화면과 데이터가 함께 확장됩니다."}</p></div></aside><div className="workspace"><header className="topbar"><div><strong>거래처 계좌 변경 통제</strong><span>{page === "dashboard" ? "대시보드" : page === "population" ? "모집단 확인" : "예외 검토"}</span></div><span className={`connection ${ready ? "" : "caution"}`}>{ready ? "API 연결 O" : "API 연결 중"}</span></header><main className="main-content">{children}</main></div></div>
}

function Workflow() {
  const current = stage >= 5 ? 5 : stage - 1
  const labels = ["모집단 확인", "규칙 테스트", "결과 저장", "Day 1 화면", "검증 완료"]
  return <section className="card"><div className="section-heading"><div><p className="eyebrow">학습 진행</p><h2>통제 테스트 흐름</h2></div><span className="quiet-badge">{stage < 5 ? `D1-${String(stage).padStart(2, "0")} 진행 중` : "Day 1 완료"}</span></div><ol className="workflow">{labels.map((label, index) => <li className={index < current ? "done" : index === current ? "current" : "pending"} key={label}><span>{index < current ? "✓" : index + 1}</span><div><strong>{label}</strong><small>{index < current ? "확인 완료" : index === current ? "이번 단계" : "다음 단계에서 연결"}</small></div></li>)}</ol></section>
}

function StageNote() { const notes: Record<number, [string, string]> = { 6: ["MCP 읽기 도구 연결", "get_control_population, select_day2_samples, get_case_evidence를 읽기 전용으로 연결했습니다."], 7: ["고정 샘플 12건 선택", "정상 4건과 검토 필요 8건이 반복 가능한 Day 2 샘플로 준비되었습니다."], 8: ["증적 참조 준비", "샘플별 승인·증적·지급 참조 ID를 다음 화면에서 확인할 수 있도록 연결했습니다."], 9: ["control-test Skill 준비", "같은 업무 순서를 Skill 계약으로 재사용할 수 있게 정리했습니다."], 10: ["Working paper API 준비", "API는 준비됐지만 검토자료 화면은 다음 차시에서 연결됩니다."] }; const note = notes[stage]; return note ? <section className="card prepared-card"><div className="section-heading"><div><p className="eyebrow">현재 체크포인트</p><h2>{note[0]}</h2></div><span className="quiet-badge">UI 준비 상태</span></div><p>{note[1]}</p></section> : null }
function Dashboard({ data, setPage, onReload }: { data: Payload; setPage: (page: Page) => void; onReload: () => void }) {
  const metricKeys = stage === 1 ? ["population_count"] : ["population_count", "valid_count", "normal_count", "review_count", "input_error_count"]
  return <><PageHeader title="거래처 계좌 변경 통제" description={stage === 1 ? "입력 CSV에서 모집단을 읽고 업무 화면의 첫 단계를 확인합니다." : "모집단부터 통제 결과까지, 현재 단계에서 구현된 내용을 확인합니다."} action={<button className="primary-button" onClick={onReload}>{stage >= 3 ? "통제 테스트 실행" : "모집단 새로고침"}</button>} />
    <section className="metric-grid" aria-label="현재 단계 요약">{metricKeys.map((key) => <article className="metric-card" key={key}><span>{labels[key]}</span><strong>{data.summary[key] ?? 0}</strong><small>{key === "population_count" ? "CSV 입력 행" : "현재 API 결과"}</small></article>)}</section>
    {stage === 1 && <section className="card prepared-card"><div className="section-heading"><div><p className="eyebrow">이번 단계</p><h2>모집단 화면이 열렸습니다</h2></div><span className="quiet-badge">판정 전</span></div><p>왼쪽의 모집단 확인에서 30건의 변경 요청과 입력 필드를 직접 살펴보세요. 통제 판정과 저장은 다음 단계에서 연결됩니다.</p><button className="secondary-button" onClick={() => setPage("population")}>모집단 30건 보기</button></section>}
    {stage >= 2 && <section className="card"><div className="section-heading"><div><p className="eyebrow">통제 결과</p><h2>검토가 필요한 변경 요청</h2></div><button className="text-button" onClick={() => setPage("exceptions")}>예외 전체 보기</button></div><div className="table-wrap"><table><thead><tr><th>변경 ID</th><th>거래처</th><th>사유</th><th>상태</th></tr></thead><tbody>{(data.exceptions ?? []).slice(0, 3).map((item) => <tr key={item.change_id}><td className="id-cell">{item.change_id}</td><td>{item.vendor_name ?? "-"}</td><td>{item.reason ?? "-"}</td><td><StatusBadge status={item.status} /></td></tr>)}</tbody></table></div></section>}
    {stage >= 3 && data.persistence && <section className="card persistence-card"><div className="section-heading"><div><p className="eyebrow">저장 결과</p><h2>통제 결과를 SQLite에 저장했습니다</h2></div><span className="status-badge normal">중복 없음</span></div><dl><div><dt>저장 행</dt><dd>{data.persistence.valid_population_rows}건</dd></div><div><dt>데이터베이스</dt><dd>{data.persistence.database}</dd></div></dl></section>}
    {stage >= 4 && stage < 5 && <section className="card prepared-card"><div className="section-heading"><div><p className="eyebrow">Day 2 · 준비</p><h2>검토자료와 최종 검토 화면</h2></div><span className="quiet-badge">다음 차시</span></div><p>메뉴는 미리 보이지만 아직 미래 API를 호출하지 않습니다. Day 1 화면에서 모집단과 예외를 먼저 익혀보세요.</p></section>}
    {stage >= 5 && <section className="card completion-card" role="status"><p className="eyebrow">검증 완료</p><h2>Day 1 완료</h2><p>통제 실행, 저장, 모집단·예외 화면을 모두 확인했습니다. 다음 차시에서 증적 검토를 연결합니다.</p></section>}
    {stage >= 6 && <StageNote />}
    <Workflow />
  </>
}

function PopulationPage({ data, setPage }: { data: Payload; setPage: (page: Page) => void }) {
  return <><PageHeader title="모집단 확인" description="입력 CSV에서 읽은 변경 요청을 한 행씩 확인합니다." action={<button className="secondary-button" onClick={() => setPage("dashboard")}>대시보드로</button>} /><section className="card"><div className="section-heading"><div><p className="eyebrow">vendor_changes.csv</p><h2>변경 요청 {data.population.length}건</h2></div><span className="quiet-badge">판정 전 데이터</span></div><div className="table-wrap"><table className="clickable-table"><thead><tr><th>변경 ID</th><th>Case ID</th><th>거래처 ID</th><th>요청 ID</th><th>요청 시각</th><th>요청자</th></tr></thead><tbody>{data.population.map((item) => <tr key={item.change_id}><td className="id-cell">{item.change_id}</td><td>{item.case_id ?? "-"}</td><td>{item.vendor_id ?? "-"}</td><td>{item.request_id ?? "-"}</td><td>{item.requested_at ?? "-"}</td><td>{item.requested_by ?? "-"}</td></tr>)}</tbody></table></div></section><section className="card prepared-card"><h2>다음 단계에서 채워질 내용</h2><p>각 행의 승인·증적·계좌 일치 여부는 통제 규칙을 연결한 뒤 표시됩니다.</p></section></>
}

function ExceptionsPage({ data, selected, setSelected }: { data: Payload; selected: string; setSelected: (id: string) => void }) {
  const exceptions = data.exceptions ?? []
  const detail = exceptions.find((item) => item.change_id === selected) ?? exceptions[0]
  return <><PageHeader title="예외 검토" description="통제 규칙에서 검토가 필요한 요청과 규칙별 결과를 확인합니다." /><div className="exception-layout"><section className="card exception-list"><div className="section-heading"><div><p className="eyebrow">R-01 ~ R-04</p><h2>예외 {exceptions.length}건</h2></div></div>{exceptions.map((item) => <button className={`exception-item ${detail?.change_id === item.change_id ? "selected" : ""}`} key={item.change_id} onClick={() => setSelected(item.change_id)}><div><span className="id-cell">{item.change_id}</span><strong>{item.vendor_name ?? "거래처 미확인"}</strong><p>{item.reason ?? "상세 사유 없음"}</p></div><StatusBadge status={item.status} /></button>)}</section><section className="card exception-detail">{detail ? <><div className="detail-title"><div><p className="eyebrow">선택한 변경 요청</p><h2>{detail.change_id}</h2><span>{detail.vendor_name ?? "거래처 미확인"}</span></div><StatusBadge status={detail.status} /></div><p>{detail.reason ?? "검토 사유가 없습니다."}</p><div className="rule-list">{(detail.rules ?? []).map((rule) => <div className={`rule-row ${rule.result === "fail" ? "fail" : ""}`} key={rule.rule_id}><strong>{rule.rule_id} · {rule.rule_name}</strong><span>{resultText[rule.result as keyof typeof resultText] ?? rule.result}</span><small>{rule.detail}</small></div>)}</div><div className="reference-row">{(detail.approval_ids ?? []).map((id) => <span className="reference-chip" key={id}>승인 {id}</span>)}{(detail.evidence_ids ?? []).map((id) => <span className="reference-chip" key={id}>증적 {id}</span>)}{!detail.approval_ids?.length && !detail.evidence_ids?.length && <span className="reference-chip">참조 ID 없음</span>}</div></> : <div className="state-card"><strong>검토할 예외가 없습니다.</strong></div>}</section></div></>
}

function InputErrors({ errors }: { errors: Case[] }) {
  return <section className="card"><div className="section-heading"><div><p className="eyebrow">입력 품질</p><h2>입력 오류 행 {errors.length}건</h2></div><span className="status-badge error">통제 판정 제외</span></div><div className="table-wrap"><table><thead><tr><th>변경 ID</th><th>거래처 ID</th><th>오류 사유</th><th>상태</th></tr></thead><tbody>{errors.map((item) => <tr key={item.change_id}><td className="id-cell">{item.change_id}</td><td>{item.vendor_id ?? "-"}</td><td>{item.reason ?? "입력값을 확인해주세요."}</td><td><StatusBadge status={item.status} /></td></tr>)}</tbody></table></div></section>
}

export default function App() {
  const [page, setPage] = useState<Page>(stage >= 2 ? "dashboard" : "population")
  const [data, setData] = useState<Payload | null>(null)
  const [selected, setSelected] = useState("CHG-2608-023")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const load = () => { setLoading(true); setError(""); void requestControlTest().then(setData).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "API 오류")).finally(() => setLoading(false)) }
  useEffect(load, [])
  const ready = !loading && !error && Boolean(data)
  const content = useMemo(() => {
    if (!data) return null
    if (page === "population") return <PopulationPage data={data} setPage={setPage} />
    if (page === "exceptions" && stage >= 2) return <><ExceptionsPage data={data} selected={selected} setSelected={setSelected} /><InputErrors errors={data.input_errors ?? []} /></>
    return <Dashboard data={data} setPage={setPage} onReload={load} />
  }, [data, page, selected])
  return <Shell page={page} setPage={setPage} ready={ready}>{loading || error ? <StateCard loading={loading} error={error} onRetry={load} /> : content}</Shell>
}
