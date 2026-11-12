"use client";

import { useEffect, useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { api } from "@/lib/api";
import type { Student } from "@/lib/types";

type Counts = {
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  total_tokens: number;
};

type ModelUsage = Counts & { model: string; calls: number; cost_usd: string | null };

type UsageReport = {
  all_time: boolean;
  start: string | null;
  end: string | null;
  model: string | null;
  totals: Counts;
  cost_usd: string | null;
  unpriced_models: string[];
  by_child: (Counts & { student_id: string; display_name: string; calls: number })[];
  by_day: (Counts & { day: string })[];
  by_model: ModelUsage[];
};

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function formatCount(value: number) {
  return new Intl.NumberFormat("en").format(value);
}

function formatCost(value: string | null | undefined) {
  if (value == null || value === "") return "—";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  }).format(amount);
}

function leftOutNote(models: string[]) {
  if (models.length === 0) return "";
  return `No published rate for ${models.join(", ")}, so that usage is left out of the cost.`;
}

function UsageChart({ days }: { days: UsageReport["by_day"] }) {
  const width = 560;
  const height = 140;
  const max = Math.max(...days.map((day) => day.total_tokens), 1);
  const step = days.length === 1 ? 0 : width / (days.length - 1);
  const points = days
    .map((day, index) => {
      const x = days.length === 1 ? width / 2 : index * step;
      const y = height - 16 - (day.total_tokens / max) * (height - 28);
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg className="usage-chart" role="img" aria-label="Token usage over time" viewBox={`0 0 ${width} ${height}`}>
      <polyline fill="none" stroke="#263148" strokeWidth="2" points={points} />
      {days.map((day, index) => {
        const x = days.length === 1 ? width / 2 : index * step;
        const y = height - 16 - (day.total_tokens / max) * (height - 28);
        return <circle key={day.day} cx={x} cy={y} r="3" fill="#263148" />;
      })}
    </svg>
  );
}

export function TokenUsage({ initialStudents, initialError }: { initialStudents: Student[]; initialError: string | null }) {
  const [students] = useState(initialStudents);
  const [studentId, setStudentId] = useState("");
  const [model, setModel] = useState("");
  const [allTime, setAllTime] = useState(false);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [filtersReady, setFiltersReady] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has("student_id")) setStudentId(params.get("student_id") || "");
    if (params.has("model")) setModel(params.get("model") || "");
    if (params.get("all_time") === "true") setAllTime(true);
    if (params.has("start")) setStart(params.get("start") || "");
    if (params.has("end")) setEnd(params.get("end") || "");
    setFiltersReady(true);
  }, []);
  const [report, setReport] = useState<UsageReport | null>(null);
  const [error, setError] = useState(initialError);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams();
    if (studentId) params.set("student_id", studentId);
    if (model) params.set("model", model);
    if (allTime) params.set("all_time", "true");
    else {
      if (start) params.set("start", start);
      if (end) params.set("end", end);
    }
    const query = params.toString();
    if (!filtersReady) return undefined;
    let cancelled = false;
    setLoading(true);
    api<UsageReport>(`/kc/token-usage${query ? `?${query}` : ""}`)
      .then((next) => {
        if (cancelled) return;
        setReport(next);
        setError(null);
        if (!allTime) {
          setStart((current) => current || next.start || "");
          setEnd((current) => current || next.end || "");
        }
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filtersReady, studentId, model, allTime, start, end]);

  const totals = report?.totals;
  const empty = !totals || (totals.input_tokens === 0 && totals.output_tokens === 0 && totals.cached_tokens === 0);

  return (
    <AdminFrame
      current="token-usage"
      sidebar={
        <p className="help">
          Input, output, and cached tokens from tutor speak and answer calls. Cost uses the published rate for each
          model.
        </p>
      }
    >
      <article className="editor agent-config-editor">
        <p className="eyebrow">Administration</p>
        <h2>Token usage</h2>
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <div className="usage-filters">
          <label>
            Child
            <select aria-label="Child" value={studentId} onChange={(event) => setStudentId(event.target.value)}>
              <option value="">View all</option>
              {students.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Model
            <select aria-label="Model" value={model} onChange={(event) => setModel(event.target.value)}>
              <option value="">All models</option>
              {model && !(report?.by_model ?? []).some((row) => row.model === model) ? (
                <option value={model}>{model}</option>
              ) : null}
              {(report?.by_model ?? []).map((row) => (
                <option key={row.model} value={row.model}>
                  {row.model}
                </option>
              ))}
            </select>
          </label>
          <label>
            From
            <input
              aria-label="From"
              type="date"
              value={start}
              disabled={allTime}
              onChange={(event) => setStart(event.target.value)}
            />
          </label>
          <label>
            To
            <input
              aria-label="To"
              type="date"
              value={end}
              disabled={allTime}
              onChange={(event) => setEnd(event.target.value)}
            />
          </label>
          <label>
            Range
            <select
              aria-label="Range"
              value={allTime ? "all" : "dates"}
              onChange={(event) => setAllTime(event.target.value === "all")}
            >
              <option value="dates">Date range</option>
              <option value="all">All time</option>
            </select>
          </label>
        </div>
        {loading && !report ? <p className="help">Loading usage.</p> : null}
        {totals ? (
          <>
            <section className="agent-config-card" aria-label="Totals">
              <h3>Total usage</h3>
              <p className="meta">
                In {formatCount(totals.input_tokens)} · out {formatCount(totals.output_tokens)} · cached{" "}
                {formatCount(totals.cached_tokens)} · sum {formatCount(totals.total_tokens)} · cost{" "}
                {formatCost(report?.cost_usd)}
              </p>
              {report && report.unpriced_models.length > 0 ? (
                <p className="help">{leftOutNote(report.unpriced_models)}</p>
              ) : null}
              {empty ? <p className="help">No usage in this range.</p> : null}
            </section>
            <section className="agent-config-card" aria-label="Usage by model">
              <h3>By model</h3>
              {report && report.by_model.length === 0 ? <p className="help">No usage in this range.</p> : null}
              <table className="usage-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Calls</th>
                    <th>Input</th>
                    <th>Output</th>
                    <th>Cached</th>
                    <th>Sum</th>
                    <th>Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {(report?.by_model ?? []).map((row) => (
                    <tr key={row.model}>
                      <td>{row.model}</td>
                      <td>{formatCount(row.calls)}</td>
                      <td>{formatCount(row.input_tokens)}</td>
                      <td>{formatCount(row.output_tokens)}</td>
                      <td>{formatCount(row.cached_tokens)}</td>
                      <td>{formatCount(row.total_tokens)}</td>
                      <td>{formatCost(row.cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <section className="agent-config-card" aria-label="Usage over time">
              <h3>Usage over time</h3>
              {report && report.by_day.length > 0 ? <UsageChart days={report.by_day} /> : null}
              {report && report.by_day.length === 0 ? <p className="help">No usage in this range.</p> : null}
              <table className="usage-table">
                <thead>
                  <tr>
                    <th>Day</th>
                    <th>Input</th>
                    <th>Output</th>
                    <th>Cached</th>
                    <th>Sum</th>
                  </tr>
                </thead>
                <tbody>
                  {(report?.by_day ?? []).map((day) => (
                    <tr key={day.day}>
                      <td>{day.day}</td>
                      <td>{formatCount(day.input_tokens)}</td>
                      <td>{formatCount(day.output_tokens)}</td>
                      <td>{formatCount(day.cached_tokens)}</td>
                      <td>{formatCount(day.total_tokens)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <section className="agent-config-card" aria-label="Usage by child">
              <h3>By child</h3>
              {report && report.by_child.length === 0 ? <p className="help">No usage in this range.</p> : null}
              <table className="usage-table">
                <thead>
                  <tr>
                    <th>Child</th>
                    <th>Calls</th>
                    <th>Input</th>
                    <th>Output</th>
                    <th>Cached</th>
                    <th>Sum</th>
                  </tr>
                </thead>
                <tbody>
                  {(report?.by_child ?? []).map((child) => (
                    <tr key={child.student_id}>
                      <td>{child.display_name}</td>
                      <td>{formatCount(child.calls)}</td>
                      <td>{formatCount(child.input_tokens)}</td>
                      <td>{formatCount(child.output_tokens)}</td>
                      <td>{formatCount(child.cached_tokens)}</td>
                      <td>{formatCount(child.total_tokens)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        ) : null}
      </article>
    </AdminFrame>
  );
}
