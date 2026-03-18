"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import {
  fetchWorkspaces,
  fetchWorkspaceScore,
  fetchWorkspaceIssues,
  fetchWorkspaceRecommendations,
  fetchWorkspaceAudit,
  runAnalysis,
  generateRecommendations,
  explainRecommendation,
  approveRecommendation,
  dismissRecommendation,
  applyRecommendation,
  fetchPage,
  type Workspace,
  type WorkspaceScore,
  type Issue,
  type Recommendation,
  type AuditAction,
  type PageDetail,
} from "@/lib/api";
import { DiffPreview } from "@/components/DiffPreview";

export default function Dashboard() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  const [score, setScore] = useState<WorkspaceScore | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [audit, setAudit] = useState<AuditAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [diffRecId, setDiffRecId] = useState<number | null>(null);
  const [pageForDiff, setPageForDiff] = useState<PageDetail | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const DIFF_TYPES = ["summarize", "standardize_template", "split_page"] as const;

  function getDiffSnippets(rec: Recommendation, page: PageDetail): { before: string; after: string } | null {
    const content = page.content_markdown || "";
    let proposed: Record<string, unknown> = {};
    try {
      if (rec.proposed_changes_json) proposed = JSON.parse(rec.proposed_changes_json) as Record<string, unknown>;
    } catch {
      /* ignore */
    }

    if (rec.type === "summarize") {
      const summary = (proposed.summary_text as string) || (content.length > 300 ? content.slice(0, 300) + "..." : content) || "(Summary)";
      const section = `\n\n---\n## Summary\n\n${summary}\n`;
      return { before: content, after: content + section };
    }
    if (rec.type === "standardize_template") {
      const now = new Date().toISOString().slice(0, 10);
      const header =
        "---\n" +
        "**Purpose:** (To be filled)\n" +
        `**Owner:** ${page.owner || "(Unassigned)"}\n` +
        `**Last Updated:** ${now}\n` +
        "---\n\n";
      if (content.trim().startsWith("---")) return null;
      return { before: content, after: header + content };
    }
    if (rec.type === "split_page") {
      const sectionText = (proposed.section_text as string) || (content.length > 500 ? content.slice(0, 500) + "..." : content) || "(Extracted section)";
      const newTitle = (proposed.new_title as string) || `${page.title} (Part 2)`;
      const before = content;
      const after = `[Original page - kept]\n${content}\n\n---\n\n[New page: "${newTitle}"]\n${sectionText}`;
      return { before, after };
    }
    return null;
  }

  const toggleDiff = useCallback(
    async (rec: Recommendation) => {
      if (diffRecId === rec.id) {
        setDiffRecId(null);
        setPageForDiff(null);
        return;
      }
      if (!rec.page_id || !DIFF_TYPES.includes(rec.type as (typeof DIFF_TYPES)[number])) return;
      setDiffRecId(rec.id);
      setDiffLoading(true);
      try {
        const page = await fetchPage(rec.page_id);
        setPageForDiff(page);
      } catch {
        setPageForDiff(null);
      } finally {
        setDiffLoading(false);
      }
    },
    [diffRecId]
  );

  const loadData = useCallback(async () => {
    if (!selectedWorkspaceId) return;
    setLoading(true);
    try {
      const [scoreRes, issuesRes, recsRes, auditRes] = await Promise.all([
        fetchWorkspaceScore(selectedWorkspaceId),
        fetchWorkspaceIssues(selectedWorkspaceId),
        fetchWorkspaceRecommendations(selectedWorkspaceId),
        fetchWorkspaceAudit(selectedWorkspaceId),
      ]);
      setScore(scoreRes);
      setIssues(
        issuesRes
          .filter((i) => !i.resolved_at)
          .sort((a, b) => b.severity - a.severity)
      );
      setRecommendations(recsRes);
      setAudit(auditRes.slice(0, 10));
      setDiffRecId(null);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [selectedWorkspaceId]);

  useEffect(() => {
    async function init() {
      try {
        const ws = await fetchWorkspaces();
        setWorkspaces(ws);
        if (ws.length > 0 && !selectedWorkspaceId) setSelectedWorkspaceId(ws[0].id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load";
      setError(msg);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const hint = /fetch|network|failed/i.test(msg)
        ? " Is the backend running?"
        : "";
      toast.error(`Failed to connect to backend.${hint}`);
    } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  useEffect(() => {
    if (selectedWorkspaceId) loadData();
  }, [selectedWorkspaceId, loadData]);

  const handleRunAnalysis = async () => {
    if (!selectedWorkspaceId) return;
    setActionLoading("analysis");
    try {
      await runAnalysis(selectedWorkspaceId);
      toast.success("Analysis complete");
      loadData();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setActionLoading(null);
    }
  };

  const handleGenerateRecs = async () => {
    if (!selectedWorkspaceId) return;
    setActionLoading("generate");
    try {
      const res = await generateRecommendations(selectedWorkspaceId);
      toast.success(`Generated ${res.count} recommendations`);
      loadData();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Generate failed");
    } finally {
      setActionLoading(null);
    }
  };

  const handleExplain = async (id: number) => {
    setActionLoading(`explain-${id}`);
    try {
      await explainRecommendation(id);
      toast.success("Explanation generated");
      loadData();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Explain failed");
    } finally {
      setActionLoading(null);
    }
  };

  const handleApprove = async (id: number) => {
    setActionLoading(`approve-${id}`);
    try {
      await approveRecommendation(id);
      toast.success("Approved");
      loadData();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDismiss = async (id: number) => {
    setActionLoading(`dismiss-${id}`);
    try {
      await dismissRecommendation(id);
      toast.success("Dismissed");
      loadData();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Dismiss failed");
    } finally {
      setActionLoading(null);
    }
  };

  const handleApply = async (rec: Recommendation) => {
    setActionLoading(`apply-${rec.id}`);
    try {
      let payload: { owner?: string } | undefined;
      if (rec.type === "assign_owner") {
        const owner = window.prompt("Enter owner email:");
        if (!owner?.trim()) {
          toast.error("Owner required");
          setActionLoading(null);
          return;
        }
        payload = { owner: owner.trim() };
      }
      const res = await applyRecommendation(rec.id, payload);
      if (res.idempotent) toast("Already applied", { icon: "ℹ️" });
      else toast.success("Applied");
      loadData();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Apply failed");
    } finally {
      setActionLoading(null);
    }
  };

  const isTaskRunning = !!actionLoading;
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  if (error && workspaces.length === 0) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
        <p className="font-medium">Error</p>
        <p>{error}</p>
        <p className="mt-2 text-sm">Ensure the backend is running at {apiBase}</p>
        <button
          onClick={() => {
            setError(null);
            setLoading(true);
            fetchWorkspaces()
              .then((ws) => {
                setWorkspaces(ws);
                if (ws.length > 0) setSelectedWorkspaceId(ws[0].id);
              })
              .catch((e) => setError(e instanceof Error ? e.message : "Failed to connect"))
              .finally(() => setLoading(false));
          }}
          className="mt-3 rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-2">Workspace</h2>
        <select
          value={selectedWorkspaceId ?? ""}
          onChange={(e) => setSelectedWorkspaceId(Number(e.target.value))}
          disabled={isTaskRunning}
          className="block w-full max-w-xs rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {workspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>
              {ws.name}
            </option>
          ))}
        </select>
      </section>

      {error && selectedWorkspaceId && !loading && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-800">
          <p className="font-medium">Error loading data</p>
          <p className="text-sm">{error}</p>
          <button
            onClick={() => loadData()}
            className="mt-2 rounded-md border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100"
          >
            Retry
          </button>
        </div>
      )}
      {(loading || (selectedWorkspaceId && !score)) ? (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        </div>
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-medium text-slate-500">Health Score</h3>
              <p className="mt-1 text-3xl font-bold text-slate-600">{score?.overall ?? 0}</p>
              <p className="mt-1 text-xs text-slate-400">/ 100</p>
              {score?.last_analysis_at && (
                <p className="mt-2 text-xs text-slate-400">
                  Last analysis: {new Date(score.last_analysis_at).toLocaleString()}
                </p>
              )}
              {score?.subscores && score.subscores.length > 0 && (
                <div className="mt-3 space-y-1">
                  {score.subscores.map((s) => (
                    <div key={s.name} className="flex justify-between text-xs">
                      <span className="text-slate-500">{s.name}</span>
                      <span className="font-medium">{Math.round(s.score)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <button
                onClick={handleRunAnalysis}
                disabled={!!actionLoading}
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
              >
                {actionLoading === "analysis" ? "Running…" : "Run Analysis"}
              </button>
              <button
                onClick={handleGenerateRecs}
                disabled={!!actionLoading}
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
              >
                {actionLoading === "generate" ? "Generating…" : "Generate Recommendations"}
              </button>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">Issues</h2>
            <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <table className="min-w-full divide-y divide-slate-200">
                <thead>
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-slate-500">Type</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-slate-500">Severity</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-slate-500">Page</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-slate-500">Summary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {issues.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-sm text-slate-500">
                        No open issues
                      </td>
                    </tr>
                  ) : (
                    issues.map((i) => (
                      <tr key={i.id}>
                        <td className="px-4 py-2 text-sm font-mono">{i.type}</td>
                        <td className="px-4 py-2">
                          <span className="inline-flex rounded px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-800">
                            {i.severity}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-sm">
                          {i.page_id ? (
                            <Link href={`/pages/${i.page_id}`} className="text-slate-600 hover:underline">
                              #{i.page_id}
                            </Link>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-4 py-2 text-sm text-slate-600">{i.summary}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">Recommendations</h2>
            <div className="space-y-3">
              {recommendations.length === 0 ? (
                <p className="rounded-lg border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
                  No recommendations. Run analysis and generate recommendations.
                </p>
              ) : (
                recommendations.map((rec) => (
                  <div
                    key={rec.id}
                    className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex rounded px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-700">
                            P{rec.priority}
                          </span>
                          <span className="text-xs text-slate-400">{rec.type}</span>
                          <span className="text-xs text-slate-400">{rec.status}</span>
                        </div>
                        <h3 className="mt-1 font-medium text-slate-800">{rec.title}</h3>
                        {rec.rationale && (
                          <p className="mt-1 text-sm text-slate-600">{rec.rationale}</p>
                        )}
                        {rec.why_this_matters && (
                          <p className="mt-2 text-xs text-slate-500">{rec.why_this_matters}</p>
                        )}
                        {DIFF_TYPES.includes(rec.type as (typeof DIFF_TYPES)[number]) && rec.page_id && (
                          <div className="mt-2">
                            <button
                              type="button"
                              onClick={() => toggleDiff(rec)}
                              className="text-xs font-medium text-slate-500 hover:text-slate-700"
                            >
                              {diffRecId === rec.id ? "Hide diff preview" : "Show diff preview"}
                            </button>
                            {diffRecId === rec.id && (
                              <div className="mt-2">
                                {diffLoading ? (
                                  <div className="flex items-center gap-2 py-2 text-xs text-slate-500">
                                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
                                    Loading…
                                  </div>
                                ) : pageForDiff ? (
                                  (() => {
                                    const snippets = getDiffSnippets(rec, pageForDiff);
                                    return snippets ? (
                                      <DiffPreview before={snippets.before} after={snippets.after} />
                                    ) : (
                                      <p className="text-xs text-slate-500">No diff (e.g. already has header)</p>
                                    );
                                  })()
                                ) : (
                                  <p className="text-xs text-slate-500">Could not load page</p>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="flex flex-col gap-1">
                        <button
                          onClick={() => handleExplain(rec.id)}
                          disabled={!!actionLoading}
                          className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                        >
                          {actionLoading === `explain-${rec.id}` ? "…" : "Explain"}
                        </button>
                        {rec.status === "proposed" && (
                          <button
                            onClick={() => handleApprove(rec.id)}
                            disabled={!!actionLoading}
                            className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50 disabled:opacity-50"
                          >
                            {actionLoading === `approve-${rec.id}` ? "…" : "Approve"}
                          </button>
                        )}
                        {(rec.status === "proposed" || rec.status === "approved") && (
                          <button
                            onClick={() => handleApply(rec)}
                            disabled={!!actionLoading}
                            className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 disabled:opacity-50"
                          >
                            {actionLoading === `apply-${rec.id}` ? "…" : "Apply"}
                          </button>
                        )}
                        {(rec.status === "proposed" || rec.status === "approved") && (
                          <button
                            onClick={() => handleDismiss(rec.id)}
                            disabled={!!actionLoading}
                            className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                          >
                            {actionLoading === `dismiss-${rec.id}` ? "…" : "Dismiss"}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>

          <section>
            <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">Audit Log</h2>
            <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
              <ul className="divide-y divide-slate-100">
                {audit.length === 0 ? (
                  <li className="px-4 py-6 text-center text-sm text-slate-500">No actions yet</li>
                ) : (
                  audit.map((a) => (
                    <li key={a.id} className="flex items-center justify-between px-4 py-2 text-sm">
                      <span className="font-mono text-slate-600">{a.action_type}</span>
                      <span className="text-slate-400">{a.actor}</span>
                      <span className="text-xs text-slate-400">
                        {new Date(a.created_at).toLocaleString()}
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
