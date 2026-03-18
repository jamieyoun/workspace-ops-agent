"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import {
  fetchPage,
  fetchPageMetrics,
  fetchPageIssues,
  fetchPageRecommendations,
  type PageDetail,
  type PageMetric,
  type Issue,
  type Recommendation,
} from "@/lib/api";

export default function PageDetailClient({ pageId: pageIdStr }: { pageId: string }) {
  const pageId = parseInt(pageIdStr, 10);
  const [page, setPage] = useState<PageDetail | null>(null);
  const [metrics, setMetrics] = useState<PageMetric[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (isNaN(pageId)) return;
    try {
      const [pageRes, metricsRes, issuesRes, recsRes] = await Promise.all([
        fetchPage(pageId),
        fetchPageMetrics(pageId),
        fetchPageIssues(pageId),
        fetchPageRecommendations(pageId),
      ]);
      setPage(pageRes);
      setMetrics(metricsRes);
      setIssues([...issuesRes].sort((a, b) => b.severity - a.severity));
      setRecommendations(recsRes);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [pageId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (isNaN(pageId)) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
        Invalid page ID
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
      </div>
    );
  }

  if (error || !page) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
        <p>{error ?? "Page not found"}</p>
        <Link href="/" className="mt-2 inline-block text-sm underline">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const metric = metrics[0];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/" className="text-sm text-slate-500 hover:text-slate-700">
            ← Dashboard
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-slate-800">{page.title}</h1>
          <div className="mt-1 flex gap-4 text-sm text-slate-500">
            <span>Owner: {page.owner ?? "—"}</span>
            <span>Updated: {new Date(page.last_updated_at).toLocaleDateString()}</span>
            {page.archived_at && (
              <span className="text-amber-600">Archived {new Date(page.archived_at).toLocaleDateString()}</span>
            )}
          </div>
        </div>
      </div>

      {metric && (
        <section>
          <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">Metrics</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs text-slate-500">Words</p>
              <p className="text-lg font-semibold">{metric.word_count}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs text-slate-500">Blocks</p>
              <p className="text-lg font-semibold">{metric.block_count}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs text-slate-500">Embeds</p>
              <p className="text-lg font-semibold">{metric.embed_count}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs text-slate-500">DB Refs</p>
              <p className="text-lg font-semibold">{metric.database_refs_count}</p>
            </div>
          </div>
        </section>
      )}

      <section>
        <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">Content</h2>
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          {page.content_markdown ? (
            <div className="prose prose-slate max-w-none text-sm">
              <ReactMarkdown>{page.content_markdown}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-slate-500">No content</p>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">Issues</h2>
        {issues.length === 0 ? (
          <p className="rounded-lg border border-slate-200 bg-white p-4 text-center text-sm text-slate-500">
            No issues for this page
          </p>
        ) : (
          <div className="space-y-2">
            {issues.map((i) => (
              <div
                key={i.id}
                className="rounded-lg border border-slate-200 bg-white p-4"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-500">{i.type}</span>
                  <span className="rounded px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-800">
                    {i.severity}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-700">{i.summary}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">Recommendations</h2>
        {recommendations.length === 0 ? (
          <p className="rounded-lg border border-slate-200 bg-white p-4 text-center text-sm text-slate-500">
            No recommendations for this page
          </p>
        ) : (
          <div className="space-y-2">
            {recommendations.map((rec) => (
              <div
                key={rec.id}
                className="rounded-lg border border-slate-200 bg-white p-4"
              >
                <div className="flex items-center gap-2">
                  <span className="rounded px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-700">
                    P{rec.priority}
                  </span>
                  <span className="text-xs text-slate-400">{rec.type}</span>
                  <span className="text-xs text-slate-400">{rec.status}</span>
                </div>
                <h3 className="mt-1 font-medium text-slate-800">{rec.title}</h3>
                {rec.rationale && (
                  <p className="mt-1 text-sm text-slate-600">{rec.rationale}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
