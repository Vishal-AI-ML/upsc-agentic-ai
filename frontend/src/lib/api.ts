import { getApiBase } from "./config"

const LS_TOKEN = "upscai-token"
const LS_REFRESH = "upscai-refresh"

export interface TokenPair {
  access_token: string
  refresh_token?: string
  token_type?: string
}

export interface CurrentUser {
  id?: string
  sub?: string
  email?: string
  name?: string
  [k: string]: unknown
}

export interface RegisterResult {
  verification_required?: boolean
  message?: string
  access_token?: string
  refresh_token?: string
}

export interface Conversation {
  id: string
  agent: string
  title: string
  created_at: string | null
  updated_at: string | null
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  created_at: string | null
}

export interface TopicMastery {
  topic: string
  score: number
  weak: boolean
  attempts: number
  last_tested: string | null
}

export interface ActivityPoint {
  date: string
  count: number
}

export interface ProgressOverview {
  streak: {
    current: number
    longest: number
    active_today: boolean
    activity: ActivityPoint[]
  }
  topics: TopicMastery[]
  weak_topics: string[]
  revision: { due: number; total: number }
  questions: { total: number; correct: number; accuracy: number }
  totals: { conversations: number; active_days: number; questions_asked: number }
}

export interface CostAgentRow {
  agent: string
  input_tokens: number
  output_tokens: number
  tokens: number
  calls: number
  cost_inr: number
}

export interface CostOverview {
  estimated: boolean
  currency: string
  totals: {
    cost_inr: number
    input_tokens: number
    output_tokens: number
    tokens: number
    calls: number
    avg_cost_per_call_inr: number
  }
  agents: CostAgentRow[]
  tier_mix: { lite: number; strong: number; lite_share: number }
  cache: {
    hit_exact: number
    hit_semantic: number
    miss: number
    skip: number
    hit_rate: number
    estimated_savings_inr: number
  }
  rates_inr_per_1k: Record<string, { input: number; output: number }>
}

export interface MonitoringEndpoint {
  method: string
  path: string
  count: number
  errors: number
  error_rate: number
  avg_ms: number
  max_ms: number
}
export interface MonitoringHourPoint {
  hour: string
  count: number
  errors: number
}
export interface MonitoringOverview {
  estimated: boolean
  uptime_seconds: number
  total_requests: number
  rps: number
  error_rate: number
  status_classes: Record<string, number>
  latency_ms: {
    count: number
    p50: number
    p95: number
    p99: number
    avg: number
    max: number
  }
  endpoints: MonitoringEndpoint[]
  hourly: MonitoringHourPoint[]
}

export interface FeedbackInput {
  rating: "up" | "down"
  agent?: string
  question?: string
  answer?: string
  comment?: string
}

export interface AnswerEvaluation {
  score: number | null
  max_score: number
  did_well: string[]
  missing: string[]
  improvements: string[]
}

export interface MainsEvaluation {
  score: number | null
  max_marks: number
  verdict: string | null
  strengths: string[]
  gaps: string[]
  improvements: string[]
}

export interface ExperimentVariantResult {
  variant: string
  up: number
  down: number
  total: number
  up_rate: number
  wilson_lower: number
  lift_vs_baseline: number | null
  enough_data: boolean
}
export interface ExperimentComparison {
  experiment: string
  baseline: string
  min_sample: number
  leader: string | null
  confident: boolean
  variants: ExperimentVariantResult[]
}
export interface ExperimentInfo {
  key: string
  description: string
  unit: string
  enabled: boolean
  variants: Array<{ name: string; weight: number; has_directive: boolean; directive: string }>
  results: ExperimentComparison
}
export interface FeedbackTally {
  up: number
  down: number
  total: number
  up_rate: number
}
export interface ExperimentsOverview {
  estimated: boolean
  experiments: ExperimentInfo[]
  feedback: {
    overall: FeedbackTally
    by_agent: Record<string, FeedbackTally>
    sample_size: number
  }
}

// ── Agent feature schemas (Planner / PYQ / NCERT / Current Affairs / Upload / Lecture) ──

export interface StudyPlanMeta {
  attempt_year: number
  months_left: number
  timeline_msg: string
  prelims_date: string | null
}
export interface PlannerResult {
  plan: string
  meta: StudyPlanMeta | null
}

export interface NcertList {
  items: string[]
}
export interface NcertSession {
  notes: string
  mindmap_html: string
  questions_html: string
  chapter_path: string
}

export interface CaMonthsResult {
  months: Array<[string, string]>
}

export interface PyqBankStatus {
  exists: boolean
}
export interface PyqBankUploadResult {
  success: boolean
  filename: string
  hash: string
  chunks: number
  approx_questions: number
}

export interface UploadResult {
  success: boolean
  filename: string
  hash: string
  book_info: Record<string, unknown>
  notes: string
}

export interface LectureResult {
  notes: string
  topic_info: Record<string, unknown>
  video_id: string
  mindmap_html: string
  questions_html: string
}

// Background jobs: heavy endpoints enqueue work and return a job id; the client
// polls GET /jobs/{id} until the job is done (or errors).
export type JobState = "queued" | "running" | "done" | "error"
export interface JobStatus<T = unknown> {
  job_id: string
  type: string
  status: JobState
  result: T | null
  error: string | null
  created_at: string | null
  updated_at: string | null
}
interface EnqueueResponse {
  job_id: string
  status: JobState
}

export function getToken(): string {
  return localStorage.getItem(LS_TOKEN) || ""
}
export function getRefreshToken(): string {
  return localStorage.getItem(LS_REFRESH) || ""
}
export function setTokens(t: TokenPair): void {
  if (t.access_token) localStorage.setItem(LS_TOKEN, t.access_token)
  if (t.refresh_token) localStorage.setItem(LS_REFRESH, t.refresh_token)
}
export function clearTokens(): void {
  localStorage.removeItem(LS_TOKEN)
  localStorage.removeItem(LS_REFRESH)
}

function authHeaders(): Record<string, string> {
  const t = getToken()
  return t ? { Authorization: "Bearer " + t } : {}
}

function url(path: string): string {
  return getApiBase() + path
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = "ApiError"
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const d = (await res.json()) as { detail?: string }
    return d.detail || res.statusText
  } catch {
    return res.statusText || "Request failed"
  }
}

// Single-flight refresh: many 401s at once trigger only one refresh call.
let refreshing: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  const rt = getRefreshToken()
  if (!rt) return false
  if (!refreshing) {
    refreshing = fetch(url("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    })
      .then(async (r) => {
        if (!r.ok) return false
        setTokens((await r.json()) as TokenPair)
        return true
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const res = await fetch(url(path), {
    ...init,
    headers: { ...(init.headers || {}), ...authHeaders() },
  })
  if (res.status === 401 && retry) {
    if (await tryRefresh()) return request<T>(path, init, false)
  }
  if (!res.ok) throw new ApiError(res.status, await parseError(res))
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// Poll a background job to completion. onStatus fires on each status change so
// the UI can show "queued" vs "running". Resolves with the job result, or throws
// an ApiError if the job errors or exceeds the timeout.
async function pollJob<T>(
  jobId: string,
  onStatus?: (status: JobState) => void,
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<T> {
  const intervalMs = opts.intervalMs ?? 2000
  const timeoutMs = opts.timeoutMs ?? 10 * 60 * 1000
  const started = Date.now()
  let last: JobState | null = null
  for (;;) {
    const job = await request<JobStatus<T>>("/jobs/" + encodeURIComponent(jobId))
    if (job.status !== last) {
      last = job.status
      onStatus?.(job.status)
    }
    if (job.status === "done") {
      if (job.result == null)
        throw new ApiError(500, "The job finished but returned no result.")
      return job.result
    }
    if (job.status === "error")
      throw new ApiError(500, job.error || "The background job failed. Please retry.")
    if (Date.now() - started > timeoutMs)
      throw new ApiError(504, "This is taking longer than expected. Please try again.")
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}

export const api = {
  async login(email: string, password: string): Promise<TokenPair> {
    // Backend uses OAuth2PasswordRequestForm: form-encoded, field name 'username'.
    const body = new URLSearchParams()
    body.set("username", email)
    body.set("password", password)
    const res = await fetch(url("/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    })
    if (!res.ok) throw new ApiError(res.status, await parseError(res))
    const data = (await res.json()) as TokenPair
    setTokens(data)
    return data
  },

  async register(
    email: string,
    password: string,
    name: string,
  ): Promise<RegisterResult> {
    const data = await request<RegisterResult>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    })
    if (data.access_token) setTokens(data as TokenPair)
    return data
  },

  me(): Promise<CurrentUser> {
    return request<CurrentUser>("/auth/me")
  },

  async verifyEmail(token: string): Promise<TokenPair & { message?: string }> {
    const data = await request<TokenPair & { message?: string }>(
      "/auth/verify-email",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      },
    )
    if (data.access_token) setTokens(data)
    return data
  },

  resendVerification(email: string): Promise<{ message: string }> {
    return request("/auth/resend-verification", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    })
  },

  forgotPassword(email: string): Promise<{ message: string }> {
    return request("/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    })
  },

  resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    return request("/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, new_password: newPassword }),
    })
  },

  async logout(): Promise<void> {
    const rt = getRefreshToken()
    if (rt) {
      try {
        await request("/auth/logout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: rt }),
        })
      } catch {
        // best-effort; clear local tokens regardless
      }
    }
    clearTokens()
  },

  conversations(agent?: string): Promise<{ conversations: Conversation[] }> {
    const q = agent ? "?agent=" + encodeURIComponent(agent) : ""
    return request("/history/conversations" + q)
  },

  conversationMessages(id: string): Promise<{ messages: ChatMessage[] }> {
    return request("/history/conversations/" + encodeURIComponent(id) + "/messages")
  },

  progress(): Promise<ProgressOverview> {
    return request("/progress/overview")
  },

  // Admin-only cost dashboard. `costAccess` is auth-only (returns {admin})
  // so the UI can decide whether to show the tab without catching a 403.
  costAccess(): Promise<{ admin: boolean }> {
    return request("/cost/access")
  },

  cost(): Promise<CostOverview> {
    return request("/cost/overview")
  },

  // Admin-only operational monitoring dashboard (#18). `monitoringAccess` is
  // auth-only (returns {admin}) so the UI can hide the tab without a 403.
  monitoringAccess(): Promise<{ admin: boolean }> {
    return request("/monitoring/access")
  },

  monitoring(): Promise<MonitoringOverview> {
    return request("/monitoring/overview")
  },

  // Admin-only prompt A/B experiments dashboard (#12). `experimentsAccess` is
  // auth-only (returns {admin}) so the UI can hide the tab without a 403.
  experimentsAccess(): Promise<{ admin: boolean }> {
    return request("/experiments/access")
  },

  experiments(): Promise<ExperimentsOverview> {
    return request("/experiments/overview")
  },

  submitFeedback(input: FeedbackInput): Promise<{ id: string; rating: string }> {
    return request("/feedback/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  },

  saveMessage(input: {
    role: "user" | "assistant"
    content: string
    agent?: string
    conversation_id?: string | null
    title?: string
  }): Promise<{ id: string; conversation_id: string }> {
    return request("/history/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  },

  evaluateAnswer(input: {
    question: string
    answer: string
  }): Promise<{ response: string; structured: AnswerEvaluation }> {
    return request("/evaluator/evaluate/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  },

  evaluateMains(input: {
    question: string
    answer: string
    marks?: number
    keywords?: string[]
    word_limit?: number
  }): Promise<{ response: string; structured: MainsEvaluation }> {
    return request("/evaluator/mains/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  },

  modelAnswer(input: {
    question: string
    marks?: number
    keywords?: string[]
    word_limit?: number
  }): Promise<{ response: string }> {
    return request("/evaluator/model-answer/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  },

  // ── Planner (study plan) ──
  plannerSync(input: {
    goal: string
    hours?: string
    optional?: string
    weak?: string
    attempt_number?: string
  }): Promise<PlannerResult> {
    return request("/planner/generate/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  },

  // ── NCERT (class -> subject -> chapter study) ──
  ncertClasses(): Promise<NcertList> {
    return request<NcertList>("/ncert/classes")
  },
  ncertSubjects(className: string): Promise<NcertList> {
    return request<NcertList>("/ncert/subjects/" + encodeURIComponent(className))
  },
  ncertChapters(className: string, subject: string): Promise<NcertList> {
    return request<NcertList>(
      "/ncert/chapters/" +
        encodeURIComponent(className) +
        "/" +
        encodeURIComponent(subject),
    )
  },
  ncertStudy(input: {
    class_name: string
    subject: string
    chapter: string
  }): Promise<NcertSession> {
    return request<NcertSession>("/ncert/study", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  },

  // ── Current Affairs (daily / editorial / monthly) ──
  caTopics(): Promise<{ topics: string[] }> {
    return request("/current-affairs/topics")
  },
  caDates(): Promise<{ dates: string[] }> {
    return request("/current-affairs/dates")
  },
  caMonths(): Promise<CaMonthsResult> {
    return request<CaMonthsResult>("/current-affairs/months")
  },

  // ── PYQ (practice questions + personal bank) ──
  pyqTopics(questionType: string): Promise<{ topics: string[] }> {
    return request("/pyq/topics/" + encodeURIComponent(questionType))
  },
  pyqBankStatus(): Promise<PyqBankStatus> {
    return request<PyqBankStatus>("/pyq/bank/status")
  },
  async pyqBankUpload(
    file: File,
    onStatus?: (status: JobState) => void,
  ): Promise<PyqBankUploadResult> {
    const form = new FormData()
    form.append("file", file)
    const { job_id } = await request<EnqueueResponse>("/pyq/bank/upload", {
      method: "POST",
      body: form,
    })
    return pollJob<PyqBankUploadResult>(job_id, onStatus)
  },
  pyqBankClear(): Promise<Record<string, unknown>> {
    return request("/pyq/bank/clear", { method: "POST" })
  },

  // ── Upload (PDF study notes) — runs as a background job, then polls ──
  async uploadProcess(
    file: File,
    onStatus?: (status: JobState) => void,
  ): Promise<UploadResult> {
    const form = new FormData()
    form.append("file", file)
    const { job_id } = await request<EnqueueResponse>("/upload/process", {
      method: "POST",
      body: form,
    })
    return pollJob<UploadResult>(job_id, onStatus)
  },

  // ── Lecture (YouTube / pasted transcript) — runs as a background job, then polls ──
  async lectureProcess(
    input: { youtube_url: string; medium?: string },
    onStatus?: (status: JobState) => void,
  ): Promise<LectureResult> {
    const { job_id } = await request<EnqueueResponse>("/lecture/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
    return pollJob<LectureResult>(job_id, onStatus)
  },
  async lectureProcessText(
    input: { transcript: string; medium?: string },
    onStatus?: (status: JobState) => void,
  ): Promise<LectureResult> {
    const { job_id } = await request<EnqueueResponse>("/lecture/process-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
    return pollJob<LectureResult>(job_id, onStatus)
  },
}

export interface MentorMessage {
  role: "user" | "assistant"
  content: string
}

// Generic text/plain token streamer for the agent endpoints that stream their
// output (planner, pyq, ncert, current affairs, and the upload/lecture chats).
// Takes an arbitrary path + JSON body and streams the text/plain response.
export async function streamAgent(
  path: string,
  body: unknown,
  onChunk: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(url(path), {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    })
  } catch {
    onChunk(
      "\n\n⚠️ Backend connection error. Is the API reachable at " + getApiBase() + "?",
    )
    return
  }
  if (!res.ok || !res.body) {
    if (res.status === 401) onChunk("\n\n⚠️ Session expired. Please sign in again.")
    else onChunk("\n\n⚠️ Error " + res.status + ": " + (await parseError(res)))
    return
  }
  const reader = res.body.getReader()
  const dec = new TextDecoder("utf-8")
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    const piece = dec.decode(value, { stream: true })
    if (piece) onChunk(piece)
  }
}
