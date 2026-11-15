"use client";

import { useEffect, useState } from "react";

import { RunSummary } from "@/components/harness/RunSummary";
import { api } from "@/lib/api";

type DimensionDelta = { dimension: string; before: number | null; after: number | null; delta: number | null; clear: boolean };

type Report = {
  chats: number;
  usable_chats: number;
  by_child: { name: string; chats: number; completion_rate: number; mean_score: number | null; false_passes: number; stuck: number }[];
  by_block_type: { name: string; chats: number; completion_rate: number; mean_score: number | null }[];
  by_model: { name: string; chats: number; completion_rate: number; mean_score: number | null }[];
  top_problems: { tag: string; count: number }[];
  grid: { child: string; block: string; score: number | null }[];
  findings: { title: string; count: number; place: string; block_label?: string }[];
  summary?: { text?: string };
  baseline?: {
    verdict: string;
    band: string;
    mean_score_delta: number | null;
    dimension_deltas?: DimensionDelta[];
    new_false_passes?: { child?: string }[];
    new_empty_replies?: { child?: string }[];
    new_hard_stops?: { kind?: string }[];
  };
};

type Comparison = {
  verdict: string;
  band: string;
  matched: number;
  mean_score_delta: number | null;
  dimension_deltas?: DimensionDelta[];
  new_false_passes?: { child?: string }[];
  new_empty_replies?: { child?: string }[];
  new_hard_stops?: { kind?: string }[];
};

export function ResultsTab({ runId }: { runId: string }) {
  const [report, setReport] = useState<Report | null>(null);
  const [other, setOther] = useState("");
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!runId) return;
    api<Report>(`/kc/harness/runs/${runId}/report`)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load the report."));
  }, [runId]);

  async function compare() {
    const body = await api<typeof comparison>("/kc/harness/compare", {
      method: "POST",
      body: JSON.stringify({ left: runId, right: other }),
    });
    setComparison(body);
  }

  if (!runId) return <p className="help">Open a run to see the roll-up.</p>;
  if (error) return <p className="banner">{error}</p>;
  if (!report) return <p className="help">Loading results.</p>;

  return (
    <section className="harness-panel">
      <h2>Results</h2>
      {report.summary?.text ? <RunSummary text={report.summary.text} /> : null}
      <p className="help">
        {report.usable_chats} of {report.chats} chats are in the roll-up. A chat counts only when it was judged and its child realism is 3 or higher. A missing score is not judged.
        {report.baseline ? ` Baseline: ${report.baseline.band}, ${report.baseline.verdict}. Score change ${report.baseline.mean_score_delta ?? "—"}.` : ""}
      </p>
      {report.baseline?.dimension_deltas?.length ? <DeltaList rows={report.baseline.dimension_deltas} /> : null}
      <ScoreTable title="By child" rows={report.by_child} />
      <ScoreTable title="By block type" rows={report.by_block_type} />
      <ScoreTable title="By tutor model" rows={report.by_model} />
      <h3>Top problems</h3>
      <ul>
        {report.top_problems.map((problem) => (
          <li key={problem.tag}>
            {problem.tag}: {problem.count}
          </li>
        ))}
      </ul>
      <h3>Child by block</h3>
      <ul className="harness-grid-scores">
        {report.grid.map((cell) => (
          <li key={`${cell.child}-${cell.block}`} data-score={cell.score ?? ""}>
            {cell.child} · {cell.block} · {cell.score ?? "not judged"}
          </li>
        ))}
      </ul>
      <h3>Findings</h3>
      <ul>
        {report.findings.map((finding) => (
          <li key={finding.title}>
            {finding.title} ({finding.count}). Block type: {finding.block_label || "an unknown block"}. {finding.place}
          </li>
        ))}
      </ul>
      <label>
        Compare with run id
        <input value={other} onChange={(event) => setOther(event.target.value)} />
      </label>
      <button type="button" onClick={() => void compare()}>
        Compare
      </button>
      {comparison ? (
        <div>
          <p>
            {comparison.verdict} ({comparison.band}). Matched {comparison.matched}. Score change {comparison.mean_score_delta ?? "—"}.
          </p>
          <DeltaList rows={comparison.dimension_deltas || []} />
          {comparison.new_hard_stops?.length ? <p>New hard stop: {comparison.new_hard_stops.map((row) => row.kind).filter(Boolean).join(", ")}.</p> : null}
          {comparison.new_false_passes?.length ? <p>New false pass: {comparison.new_false_passes.length}.</p> : null}
          {comparison.new_empty_replies?.length ? <p>New empty reply: {comparison.new_empty_replies.length}.</p> : null}
        </div>
      ) : null}
    </section>
  );
}

function DeltaList({ rows }: { rows: DimensionDelta[] }) {
  if (rows.length === 0) return null;
  return (
    <ul className="harness-deltas">
      {rows.map((row) => (
        <li key={row.dimension}>
          {row.dimension.replaceAll("_", " ")}: {row.delta ?? "—"}
          {row.clear ? "" : " (no clear difference)"}
        </li>
      ))}
    </ul>
  );
}

function ScoreTable({
  title,
  rows,
}: {
  title: string;
  rows: { name: string; chats: number; completion_rate: number; mean_score: number | null; false_passes?: number; stuck?: number }[];
}) {
  return (
    <>
      <h3>{title}</h3>
      <table className="harness-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Chats</th>
            <th>Completed</th>
            <th>Score</th>
            <th>False passes</th>
            <th>Stuck</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <td>{row.name}</td>
              <td>{row.chats}</td>
              <td>{row.completion_rate}</td>
              <td>{row.mean_score ?? "not judged"}</td>
              <td>{row.false_passes ?? ""}</td>
              <td>{row.stuck ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
