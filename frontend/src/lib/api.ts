/**
 * API client helpers for backend communication.
 */

const getBaseUrl = () =>
  process.env.NEXT_PUBLIC_API_URL || "/api";

export interface WorkspaceStats {
  page_count: number;
  issue_count: number;
  open_issue_count: number;
  recommendation_count: number;
  proposed_recommendation_count: number;
}

export interface Workspace {
  id: number;
  name: string;
  created_at: string;
  stats: WorkspaceStats;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export interface Subscore {
  name: string;
  score: number;
  weight: number;
  explanation: string;
}

export interface WorkspaceScore {
  overall: number;
  subscores: Subscore[];
  issue_count: number;
  open_issue_count: number;
  last_analysis_at?: string | null;
}

export interface Issue {
  id: number;
  workspace_id: number;
  page_id: number | null;
  type: string;
  severity: number;
  summary: string;
  details_json: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface Recommendation {
  id: number;
  workspace_id: number;
  page_id: number | null;
  type: string;
  priority: number;
  title: string;
  rationale: string | null;
  proposed_changes_json: string | null;
  why_this_matters: string | null;
  risk_tradeoff: string | null;
  expected_impact: string | null;
  status: string;
  created_at: string;
}

export interface AuditAction {
  id: number;
  action_type: string;
  actor: string;
  recommendation_id: number | null;
  payload_json: string | null;
  created_at: string;
}

export interface PageDetail {
  id: number;
  workspace_id: number;
  title: string;
  content_markdown: string | null;
  owner: string | null;
  last_updated_at: string;
  created_at: string;
  archived_at: string | null;
}

export interface PageMetric {
  id: number;
  page_id: number;
  word_count: number;
  block_count: number;
  embed_count: number;
  database_refs_count: number;
  computed_at: string;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${getBaseUrl()}/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function fetchWorkspaces(): Promise<Workspace[]> {
  const res = await fetch(`${getBaseUrl()}/workspaces`);
  if (!res.ok) throw new Error("Failed to fetch workspaces");
  return res.json();
}

export async function fetchWorkspace(id: number): Promise<Workspace> {
  const res = await fetch(`${getBaseUrl()}/workspaces/${id}`);
  if (!res.ok) throw new Error("Failed to fetch workspace");
  return res.json();
}

export async function fetchWorkspaceScore(workspaceId: number): Promise<WorkspaceScore> {
  const res = await fetch(`${getBaseUrl()}/workspaces/${workspaceId}/score`);
  if (!res.ok) throw new Error("Failed to fetch score");
  return res.json();
}

export async function runAnalysis(workspaceId: number): Promise<{ pages_processed: number; metrics_updated: number; issues_upserted: number }> {
  const res = await fetch(`${getBaseUrl()}/workspaces/${workspaceId}/analyze`, { method: "POST" });
  if (!res.ok) throw new Error("Analysis failed");
  return res.json();
}

export async function fetchWorkspaceIssues(workspaceId: number): Promise<Issue[]> {
  const res = await fetch(`${getBaseUrl()}/workspaces/${workspaceId}/issues`);
  if (!res.ok) throw new Error("Failed to fetch issues");
  return res.json();
}

export async function generateRecommendations(workspaceId: number): Promise<{ count: number; source: string }> {
  const res = await fetch(`${getBaseUrl()}/workspaces/${workspaceId}/recommendations/generate`, { method: "POST" });
  if (!res.ok) {
    if (res.status === 429) throw new Error("Rate limit exceeded. Try again in a minute.");
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Generate recommendations failed");
  }
  return res.json();
}

export async function fetchWorkspaceRecommendations(workspaceId: number): Promise<Recommendation[]> {
  const res = await fetch(`${getBaseUrl()}/workspaces/${workspaceId}/recommendations`);
  if (!res.ok) throw new Error("Failed to fetch recommendations");
  return res.json();
}

export async function fetchWorkspacePages(workspaceId: number): Promise<PageDetail[]> {
  const res = await fetch(`${getBaseUrl()}/workspaces/${workspaceId}/pages`);
  if (!res.ok) throw new Error("Failed to fetch pages");
  return res.json();
}

export async function fetchWorkspaceAudit(workspaceId: number): Promise<AuditAction[]> {
  const res = await fetch(`${getBaseUrl()}/workspaces/${workspaceId}/audit`);
  if (!res.ok) throw new Error("Failed to fetch audit");
  return res.json();
}

export async function explainRecommendation(recommendationId: number): Promise<{ why_this_matters: string; risk_tradeoff: string; expected_impact: string; source: string }> {
  const res = await fetch(`${getBaseUrl()}/recommendations/${recommendationId}/explain`, { method: "POST" });
  if (!res.ok) throw new Error("Explain failed");
  return res.json();
}

export async function approveRecommendation(recommendationId: number): Promise<{ id: number; status: string }> {
  const res = await fetch(`${getBaseUrl()}/recommendations/${recommendationId}/approve`, { method: "POST" });
  if (!res.ok) throw new Error("Approve failed");
  return res.json();
}

export async function dismissRecommendation(recommendationId: number): Promise<{ id: number; status: string }> {
  const res = await fetch(`${getBaseUrl()}/recommendations/${recommendationId}/dismiss`, { method: "POST" });
  if (!res.ok) throw new Error("Dismiss failed");
  return res.json();
}

export async function applyRecommendation(
  recommendationId: number,
  payload?: { owner?: string; summary_text?: string; section_text?: string; new_title?: string }
): Promise<{ applied: boolean; reason?: string; idempotent?: boolean; new_page_id?: number }> {
  const res = await fetch(`${getBaseUrl()}/recommendations/${recommendationId}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) throw new Error("Apply failed");
  return res.json();
}

export async function fetchPage(pageId: number): Promise<PageDetail> {
  const res = await fetch(`${getBaseUrl()}/pages/${pageId}`);
  if (!res.ok) throw new Error("Failed to fetch page");
  return res.json();
}

export async function fetchPageMetrics(pageId: number): Promise<PageMetric[]> {
  const res = await fetch(`${getBaseUrl()}/pages/${pageId}/metrics`);
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function fetchPageIssues(pageId: number): Promise<Issue[]> {
  const res = await fetch(`${getBaseUrl()}/pages/${pageId}/issues`);
  if (!res.ok) throw new Error("Failed to fetch issues");
  return res.json();
}

export async function fetchPageRecommendations(pageId: number): Promise<Recommendation[]> {
  const res = await fetch(`${getBaseUrl()}/pages/${pageId}/recommendations`);
  if (!res.ok) throw new Error("Failed to fetch recommendations");
  return res.json();
}
