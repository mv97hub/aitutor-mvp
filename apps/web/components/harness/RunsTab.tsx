"use client";

import { Fragment, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { downloadHarnessFile } from "@/lib/harness-file";
import { runStatusLine } from "@/lib/harness-background";
import {
  HARNESS_RUN_IDENTITY_FIELDS,
  harnessRunIdentity,
  type HarnessPersonaRef,
  type HarnessRunPlan,
} from "@/lib/harness-run-identity";

type ChatRow = {
  id: string;
  status: string;
  ended_how: string;
  child?: { name?: string };
  tutor_model: string;
  cost_usd: string | null;
  luna_tokens: number;
};

type RunRow = {
  id: string;
  status: string;
  chats: number;
  finished: number;
  created_at?: string | null;
  plan?: HarnessRunPlan | null;
  totals: { priced_cents?: number; luna_tokens?: number; cost_usd?: string | null };
};

export function RunsTab({
  selected,
  personas = [],
  onSelect,
}: {
  selected: string;
  personas?: HarnessPersonaRef[];
  onSelect?: (runId: string) => void;
}) {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [detail, setDetail] = useState<{ id: string; chat_rows?: ChatRow[] } | null>(null);
  const [error, setError] = useState("");
  const [driving, setDriving] = useState("");

  async function refresh() {
    let next: RunRow[] = [];
    try {
      const body = await api<unknown>("/kc/harness/runs");
      if (!Array.isArray(body)) {
        setError("The run list did not come back as a list.");
        return;
      }
      next = body as RunRow[];
      setRuns(next);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load runs.");
      return;
    }
    const id = selected || next[0]?.id;
    if (id && id !== selected) onSelect?.(id);
    if (!id) {
      setDetail(null);
      return;
    }
    try {
      setDetail(await api<{ id: string; chat_rows?: ChatRow[] }>(`/kc/harness/runs/${id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this run.");
    }
  }

  useEffect(() => {
    let stop = false;
    void refresh().catch((err) => {
      if (!stop) setError(err instanceof Error ? err.message : "Could not load runs.");
    });
    const timer = window.setInterval(() => {
      if (!stop) void refresh();
    }, 3000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [selected]);

  async function act(path: string, method = "POST") {
    setError("");
    try {
      await api(path, { method });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That action failed.");
    }
  }

  async function start(run: RunRow) {
    setDriving(run.id);
    setError("");
    try {
      const response = await fetch(`/api/kc/harness/runs/${run.id}/start`, { method: "POST" });
      if (!response.ok) throw new Error((await response.text()) || "Could not start the run.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the run.");
    } finally {
      setDriving("");
    }
  }

  async function stop(runId: string) {
    setError("");
    try {
      const response = await fetch(`/api/kc/harness/runs/${runId}/stop`, { method: "POST" });
      if (!response.ok) throw new Error((await response.text()) || "Could not stop the run.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not stop the run.");
    }
  }

  async function downloadRun(runId: string) {
    setError("");
    try {
      await downloadHarnessFile(`/api/kc/harness/runs/${runId}/download`, `harness-run-${runId}.md`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not download the run.");
    }
  }

  const rows = detail?.chat_rows || [];

  return (
    <section className="harness-panel">
      <h2>Runs</h2>
      {rows.length > 0 ? <p className="help">{runStatusLine(rows)}</p> : null}
      {error ? <p className="banner">{error}</p> : null}
      <table className="harness-table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Progress</th>
            <th>Priced cost</th>
            <th>Luna tokens</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => {
            const identity = harnessRunIdentity(run, personas);
            return (
              <Fragment key={run.id}>
                <tr>
                  <td>{run.status}</td>
                  <td>
                    {run.finished}/{run.chats}
                  </td>
                  <td>{run.totals?.cost_usd ?? "—"}</td>
                  <td>{run.totals?.luna_tokens ?? 0}</td>
                  <td className="harness-actions">
                    <button type="button" disabled={driving === run.id} onClick={() => void start(run)}>
                      {driving === run.id ? "Starting" : "Start"}
                    </button>
                    <button type="button" onClick={() => void act(`/kc/harness/runs/${run.id}/pause`)}>
                      Pause
                    </button>
                    <button type="button" onClick={() => void stop(run.id)}>
                      Stop
                    </button>
                    <button type="button" onClick={() => void downloadRun(run.id)}>
                      Download
                    </button>
                    <button type="button" onClick={() => void act(`/kc/harness/runs/${run.id}`, "DELETE")}>
                      Delete
                    </button>
                  </td>
                </tr>
                <tr>
                  <td colSpan={5}>
                    <dl className="harness-run-identity">
                      {HARNESS_RUN_IDENTITY_FIELDS.map((field) => (
                        <Fragment key={field.key}>
                          <dt>{field.label}</dt>
                          <dd>{identity[field.key]}</dd>
                        </Fragment>
                      ))}
                    </dl>
                  </td>
                </tr>
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <p className="help">
        Start runs the chats on the server. Closing this tab does not stop them. Stop keeps the chats already stored. Start again continues the same chat. Download is one file for the whole run. Course ids go in courses. Each child name goes in child_profiles. Cost limit is cents, the same field as cost_limit. A blank cost limit means the run had no run cap.
      </p>
      <ul>
        {rows.map((chat) => (
          <li key={chat.id}>
            {chat.child?.name} · {chat.tutor_model} · {chat.status} {chat.ended_how} · cost {chat.cost_usd ?? "blank"} · luna {chat.luna_tokens}
          </li>
        ))}
      </ul>
    </section>
  );
}
