"use client";

/**
 * Simple line-based diff: highlights additions in the "after" text.
 * No external lib required.
 */
function computeLineDiff(before: string, after: string): { line: string; added: boolean }[] {
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");
  let i = 0;
  let j = 0;
  const result: { line: string; added: boolean }[] = [];
  while (i < afterLines.length) {
    if (j < beforeLines.length && afterLines[i] === beforeLines[j]) {
      result.push({ line: afterLines[i], added: false });
      i++;
      j++;
    } else {
      result.push({ line: afterLines[i], added: true });
      i++;
    }
  }
  return result;
}

function truncateSnippet(text: string, maxLines = 20): string {
  const lines = text.split("\n");
  if (lines.length <= maxLines) return text;
  return lines.slice(0, maxLines).join("\n") + "\n...";
}

interface DiffPreviewProps {
  before: string;
  after: string;
  beforeLabel?: string;
  afterLabel?: string;
}

export function DiffPreview({
  before,
  after,
  beforeLabel = "Before",
  afterLabel = "After",
}: DiffPreviewProps) {
  const beforeSnippet = truncateSnippet(before);
  const afterSnippet = truncateSnippet(after);
  const diffLines = computeLineDiff(beforeSnippet, afterSnippet);

  return (
    <div className="mt-3 space-y-2 rounded border border-slate-200 bg-slate-50 p-3 text-sm">
      <div>
        <span className="text-xs font-medium text-slate-500">{beforeLabel}</span>
        <pre className="mt-1 overflow-x-auto rounded bg-white p-2 font-mono text-xs text-slate-700 whitespace-pre-wrap">
          {beforeSnippet || "(empty)"}
        </pre>
      </div>
      <div>
        <span className="text-xs font-medium text-slate-500">{afterLabel}</span>
        <pre className="mt-1 overflow-x-auto rounded bg-white p-2 font-mono text-xs text-slate-700 whitespace-pre-wrap">
          {diffLines.map(({ line, added }, idx) => (
            <span
              key={idx}
              className={added ? "block bg-green-100 text-green-800" : "block"}
            >
              {line || " "}
            </span>
          ))}
        </pre>
      </div>
    </div>
  );
}
