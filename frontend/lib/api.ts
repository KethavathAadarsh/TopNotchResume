import type { GenerateRequest, GenerateResponse } from "@/types/resume";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Anonymous per-browser ID. Not authentication — it scopes history so each
// visitor sees only their own generations on the shared public backend.
const CLIENT_ID_KEY = "tnr_client_id";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function getClientId(): string {
  if (typeof window === "undefined") return "";
  try {
    let id = window.localStorage.getItem(CLIENT_ID_KEY);
    if (!id) {
      id = newId();
      window.localStorage.setItem(CLIENT_ID_KEY, id);
    }
    return id;
  } catch {
    return ""; // storage blocked (private mode) — history just stays empty
  }
}

/** fetch against the API with the client ID header attached. */
export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const clientId = getClientId();
  if (clientId) headers.set("X-Client-Id", clientId);
  return fetch(`${API_URL}${path}`, { ...init, headers });
}

function _throwDetail(err: { detail?: unknown }, fallback: string): never {
  const detail = err.detail;
  if (typeof detail === "string") throw new Error(detail);
  if (Array.isArray(detail)) {
    const msg = detail
      .map((e: { loc?: string[]; msg?: string }) =>
        e.loc ? `${e.loc.slice(1).join(".")}: ${e.msg}` : e.msg ?? JSON.stringify(e)
      )
      .join(" | ");
    throw new Error(msg);
  }
  throw new Error(fallback);
}

// ── Resume generation ────────────────────────────────────────────────────────

/** Synchronous fallback — returns full result when done. */
export async function generateResume(request: GenerateRequest): Promise<GenerateResponse> {
  const res = await apiFetch(`/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(180_000),
  });
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Server error (HTTP ${res.status})`);
  return res.json();
}

/** Phase 3: Kick off async job, returns job_id for SSE streaming. */
export async function startGenerationAsync(request: GenerateRequest): Promise<{ job_id: string }> {
  const res = await apiFetch(`/api/generate/async`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Server error (HTTP ${res.status})`);
  return res.json();
}

export function getDownloadUrl(downloadId: string): string {
  return `${API_URL}/api/download/${downloadId}`;
}

// ── Upload ───────────────────────────────────────────────────────────────────

export const UPLOAD_ACCEPT = ".pdf,.docx,.txt,.md";
export const UPLOAD_MAX_BYTES = 10 * 1024 * 1024; // keep in sync with backend MAX_FILE_BYTES

export async function uploadResume(
  file: File
): Promise<{ filename: string; text: string; char_count: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch(`/api/upload/resume`, {
    method: "POST",
    body: form,
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Upload failed (HTTP ${res.status})`);
  return res.json();
}

// ── SmartExtract ─────────────────────────────────────────────────────────────

export type SectionType =
  | "all" | "personal" | "experience" | "projects"
  | "skills" | "education" | "certifications";

export async function extractSection(
  section: SectionType,
  rawText: string
): Promise<{ section: SectionType; data: Record<string, unknown> }> {
  const res = await apiFetch(`/api/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section, raw_text: rawText }),
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Extraction failed (HTTP ${res.status})`);
  return res.json();
}

// ── History ──────────────────────────────────────────────────────────────────

export interface HistoryItem {
  id: string;
  created_at: string;
  candidate: string;
  role: string;
  company: string;
  format: string;
  ats_score: number;
  kw_matched: number;
  gen_ms: number;
  filename: string;
  session_id?: string;
}

export async function fetchHistory(limit = 50): Promise<{ items: HistoryItem[]; count: number }> {
  const res = await apiFetch(`/api/history?limit=${limit}`);
  if (!res.ok) throw new Error(`History fetch failed (HTTP ${res.status})`);
  return res.json();
}

export async function deleteHistoryItem(downloadId: string): Promise<void> {
  await apiFetch(`/api/history/${downloadId}`, { method: "DELETE" });
}

export interface RestoreData {
  profile: import("@/types/resume").CandidateProfile;
  job_description: string;
  target_role: string;
  format: import("@/types/resume").ResumeFormat;
  max_pages: 1 | 2;
  ats_score: number;
  session_id: string | null;
}

export async function fetchRestoreProfile(downloadId: string): Promise<RestoreData> {
  const res = await apiFetch(`/api/history/${downloadId}/restore`);
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Restore failed (HTTP ${res.status})`);
  return res.json();
}

// ── Cover letter ─────────────────────────────────────────────────────────────

export interface CoverLetterRequest {
  download_id: string;
  composition: Record<string, unknown>;
  jd_analysis: Record<string, unknown>;
  optimized_content: Record<string, unknown>;
}

export interface CoverLetterResponse {
  cover_letter: string;
  subject_line: string;
  tone: string;
}

export async function generateCoverLetter(
  req: CoverLetterRequest
): Promise<CoverLetterResponse> {
  const res = await apiFetch(`/api/cover-letter`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Cover letter failed (HTTP ${res.status})`);
  return res.json();
}

// ── RSEA v2 — Career Intelligence Types ──────────────────────────────────────

export interface RseaVersion {
  version: number;
  download_id: string;
  filename: string;
  ats_score: number;
  created_at: string;
}

export type AgentStatus = "pending" | "running" | "done" | "error";

export interface AgentProgress {
  skill_gap: AgentStatus;
  resume_quality: AgentStatus;
  learning_path: AgentStatus;
  career_intel: AgentStatus;
  [key: string]: AgentStatus;
}

// Skill Gap Agent
export interface SkillGap {
  skill: string;
  category: string;
  severity: "critical" | "high" | "medium" | "low";
  jd_context: string;
  candidate_adjacent: string;
  is_mandatory: boolean;
}
export interface SkillGapReport {
  overall_readiness_score: number;
  readiness_label: string;
  readiness_summary: string;
  skill_gaps: SkillGap[];
  strengths: string[];
  competitive_advantages: string[];
  critical_blockers: string[];
}

// Learning Path Agent
export interface LearningResource { name: string; type: string; why: string; }
export interface LearningProject { title: string; description: string; tech_stack: string[]; github_ready: boolean; }
export interface LearningItem {
  skill: string;
  priority: "critical" | "high" | "medium" | "low";
  estimated_weeks: number;
  resources: LearningResource[];
  project_idea: LearningProject;
  why_matters: string;
}
export interface Certification {
  name: string;
  provider: string;
  relevance: string;
  estimated_months: number;
  priority: "high" | "medium" | "low";
  exam_cost_usd?: number;
  prep_resource?: string;
}
export interface QuickWin { action: string; time_required: string; impact: string; }
export interface LearningPathReport {
  total_prep_timeline: string;
  executive_summary: string;
  quick_wins: QuickWin[];
  learning_items: LearningItem[];
  certifications: Certification[];
  github_portfolio_tips?: string[];
}

// Resume Quality Agent
export interface ResumeImprovement {
  id: string;
  type: string;
  priority: "high" | "medium" | "low";
  title: string;
  description: string;
  impact: string;
  example_fix: string;
  keywords_to_add?: string[];
}
export interface ResumeScores {
  bullet_quality: number;
  ats_coverage: number;
  summary_effectiveness: number;
  quantification_rate: number;
  leadership_language: number;
}
export interface ResumeQualityReport {
  improvements: ResumeImprovement[];
  scores: ResumeScores;
  top_missing_keywords: string[];
  strongest_bullets?: string[];
  weakest_bullets?: string[];
}

// Career Intel Agent
export interface InterviewTopic {
  topic: string;
  why: string;
  depth: "surface" | "moderate" | "deep";
  prep_resources: string[];
  likely_questions: string[];
  candidate_angle: string;
}
export interface NegotiationPoint { point: string; how_to_use: string; }
export interface CareerIntelReport {
  interview_prep: InterviewTopic[];
  culture_signals: string;
  company_stage_intel: string;
  role_realities: string[];
  negotiation_leverage: NegotiationPoint[];
  red_flags: string[];
  application_strategy: string[];
  questions_to_ask: string[];
}

export interface CareerReport {
  skill_gap: SkillGapReport | null;
  learning_path: LearningPathReport | null;
  resume_quality: ResumeQualityReport | null;
  career_intel: CareerIntelReport | null;
}

export interface RseaSession {
  session_id: string;
  analysis_status: "pending" | "analyzing" | "ready" | "error";
  analysis_error?: string;
  agent_progress: AgentProgress;
  career_report: CareerReport | null;
  versions: RseaVersion[];
  created_at: string;
}

export interface RseaGenerateResponse {
  version: number;
  download_id: string;
  ats_score: number;
  keywords_matched: string[];
  keywords_missing: string[];
  message: string;
}

export async function fetchEnhanceSession(sessionId: string): Promise<RseaSession> {
  const res = await apiFetch(`/api/enhance/${sessionId}`);
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Session fetch failed (HTTP ${res.status})`);
  return res.json();
}

export async function triggerAnalysis(sessionId: string): Promise<{ status: string }> {
  const res = await apiFetch(`/api/enhance/${sessionId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Analysis trigger failed (HTTP ${res.status})`);
  return res.json();
}

export async function generateEnhanced(
  sessionId: string,
  acceptedImprovementIds: string[],
): Promise<RseaGenerateResponse> {
  const res = await apiFetch(`/api/enhance/${sessionId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accepted_improvement_ids: acceptedImprovementIds }),
    signal: AbortSignal.timeout(120_000),
  });
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Enhancement failed (HTTP ${res.status})`);
  return res.json();
}

// ── Quality Check & Iterative Refinement ─────────────────────────────────────

export interface QualityReport {
  quality_score: number;
  satisfied: boolean;
  missing_sections: string[];
  issues: string[];
  critical_issues: string[];
  recommendations: string[];
  deterministic_issues: string[];
  iteration: number;
}

export interface RefineResponse {
  quality_report: QualityReport | null;
  job_id: string;
}

export async function runQualityCheck(req: {
  download_id: string;
  user_feedback?: string;
  iteration?: number;
}): Promise<QualityReport> {
  const res = await apiFetch(`/api/quality-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Quality check failed (HTTP ${res.status})`);
  return res.json();
}

export async function startRefine(req: {
  download_id: string;
  user_feedback: string;
  iteration: number;
  model?: string;
}): Promise<RefineResponse> {
  const res = await apiFetch(`/api/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal: AbortSignal.timeout(30_000),
  });
  if (!res.ok) _throwDetail(await res.json().catch(() => ({})), `Refine request failed (HTTP ${res.status})`);
  return res.json();
}

// ── Utilities ────────────────────────────────────────────────────────────────

export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(" ");
}
