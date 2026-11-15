"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { RunSummary } from "@/components/harness/RunSummary";
import { downloadHarnessFile } from "@/lib/harness-file";
import { runStatusLine } from "@/lib/harness-background";
import { recentLines, transcriptForChat, type TranscriptLine } from "@/lib/harness-live";

type ChatRow = {
  id: string;
  status: string;
  ended_how: string;
  session_id?: string | null;
  child?: { name?: string };
  tutor_model: string;
  cost_usd: string | null;
  luna_tokens: number;
};

type SessionMessage = { role?: string; content?: string; seq?: number };

type RunRow = {
  id: string;
  status: string;
  chats: number;
  finished: number;
  totals: { priced_cents?: number; luna_tokens?: number; cost_usd?: string | null };
  plan: { concurrency?: number; child_model?: string; judge_model?: string };
};

function LiveLines({ chatId, lines }: { chatId: string; lines: TranscriptLine[] }) {
  const shown = recentLines(lines);
  return (
    <ol className="harness-transcript">
      {shown.map((line) => (
        <li key={`${chatId}-${line.seq}`} value={line.seq}>
          <strong>{line.role === "tutor" ? "Tutor" : "Child"}:</strong> {line.text}
        </li>
      ))}
    </ol>
  );
}

export function RunsTab({
  selected,
  onOpenChat,
  onSelect,
}: {
  selected: string;
  onOpenChat: (runId: string, chatId: string) => void;
  onSelect?: (runId: string) => void;
}) {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [detail, setDetail] = useState<{ id: string; chat_rows?: ChatRow[] } | null>(null);
  const [sessions, setSessions] = useState<Record<string, SessionMessage[]>>({});
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
      const loaded = await api<{ id: string; chat_rows?: ChatRow[] }>(`/kc/harness/runs/${id}`);
      setDetail(loaded);
      const active = (loaded.chat_rows || []).filter(
        (chat) => (chat.status === "running" || chat.status === "queued") && chat.session_id,
      );
      const found = await Promise.all(
        active.map(async (chat) => {
          try {
            const session = await api<{ messages?: SessionMessage[] }>(`/kc/tutor/sessions/${chat.session_id}`);
            return [chat.id, session.messages || []] as const;
          } catch {
            return [chat.id, null] as const;
          }
        }),
      );
      setSessions((current) => {
        const copy = { ...current };
        for (const [chatId, messages] of found) {
          if (messages) copy[chatId] = messages;
        }
        return copy;
      });
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

  async function downloadChat(chatId: string) {
    setError("");
    try {
      await downloadHarnessFile(`/api/kc/harness/chats/${chatId}/download`, `harness-chat-${chatId}.md`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not download the chat.");
    }
  }

  const rows = detail?.chat_rows || [];
  const active = rows.filter((chat) => chat.status === "running" || chat.status === "queued");

  return (
    <section className="harness-panel">
      <h2>Runs</h2>
      {detail?.id ? <RunSummary runId={detail.id} /> : null}
      {rows.length > 0 ? <p className="help">{runStatusLine(rows)}</p> : null}
      {error ? <p className="banner">{error}</p> : null}
      {active.length > 0 ? (
        <div className="harness-live">
          <h3>In progress</h3>
          {active.map((chat) => {
            const lines = transcriptForChat(chat.id, sessions[chat.id], []);
            return (
              <article key={chat.id}>
                <p>
                  <button type="button" onClick={() => onOpenChat(detail?.id || "", chat.id)}>
                    {chat.child?.name || "Test child"} · {chat.status}
                  </button>
                </p>
                {lines.length > 0 ? (
                  <LiveLines chatId={chat.id} lines={lines} />
                ) : (
                  <p className="help">
                    {chat.session_id ? "Waiting for the first tutor message." : "Queued. Press Start to run this chat on the server."}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      ) : null}
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
          {runs.map((run) => (
            <tr key={run.id}>
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
                <button type="button" onClick={() => void act(`/kc/harness/runs/${run.id}/again`)}>
                  Run again
                </button>
                <button type="button" onClick={() => void act(`/kc/harness/runs/${run.id}/trim`)}>
                  Trim stored prompts
                </button>
                <button type="button" onClick={() => void act(`/kc/harness/runs/${run.id}`, "DELETE")}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="help">
        Start runs the chats on the server. Closing this tab does not stop them. Stop keeps the chats already stored. Start again continues the same chat.
      </p>
      <p className="help">
        Trim keeps prompts for the baseline and the newest run of each suite. Older runs keep the transcript, scores, intents, and recommendations.
      </p>
      <ul>
        {(detail?.chat_rows || []).map((chat) => (
          <li key={chat.id}>
            <button type="button" onClick={() => onOpenChat(detail?.id || "", chat.id)}>
              {chat.child?.name} · {chat.tutor_model} · {chat.status} {chat.ended_how} · cost {chat.cost_usd ?? "blank"} · luna {chat.luna_tokens}
            </button>
            <button type="button" onClick={() => void downloadChat(chat.id)}>
              Download
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
