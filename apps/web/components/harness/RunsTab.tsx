"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { transcriptForChat } from "@/lib/harness-live";
import type { ClaimedChat, HarnessTransport, LiveLine, SessionSnap } from "@/lib/harness-runner";
import { driveRun } from "@/lib/harness-runner";

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

type SessionMessage = { role?: string; content?: string };

type RunRow = {
  id: string;
  status: string;
  chats: number;
  finished: number;
  totals: { priced_cents?: number; luna_tokens?: number; cost_usd?: string | null };
  plan: { concurrency?: number; child_model?: string; judge_model?: string };
};

async function readSnap(sessionId: string): Promise<SessionSnap> {
  const session = await api<SessionSnap>(`/kc/tutor/sessions/${sessionId}`);
  let prompt = "";
  let safety = "none";
  let passed = false;
  try {
    const detail = await api<{ prompts?: { system_prompt?: string; decision?: { safety_flag?: string; substep_passed?: boolean; block_complete?: boolean } }[] }>(
      `/kc/sessions/${sessionId}`,
    );
    const latest = detail.prompts?.[detail.prompts.length - 1];
    prompt = latest?.system_prompt || "";
    safety = latest?.decision?.safety_flag || "none";
    passed = Boolean(latest?.decision?.substep_passed || latest?.decision?.block_complete);
  } catch {
    prompt = "";
  }
  return { ...session, id: sessionId, prompt, safety_flag: safety, passed, messages: session.messages || [] };
}

function transport(runId: string): HarnessTransport {
  return {
    runStatus: () => api(`/kc/harness/runs/${runId}`),
    session: readSnap,
    speak: async (sessionId, model) => {
      const response = await fetch("/api/kc/tutor/speak", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, model }),
      });
      if (!response.ok) throw new Error(await response.text());
      return readSnap(sessionId);
    },
    answer: async (sessionId, text, model) => {
      const response = await fetch("/api/kc/tutor/answer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, answer: text, model }),
      });
      if (!response.ok) throw new Error(await response.text());
      return readSnap(sessionId);
    },
    answerKey: (chatId) => api(`/kc/harness/chats/${chatId}/answer-key`),
    childText: async (input) => {
      const response = await fetch("/api/kc/harness/child", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...input, needsModel: true }),
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    recordTurn: (chatId, body) => api(`/kc/harness/chats/${chatId}/turns`, { method: "POST", body: JSON.stringify(body) }),
    finish: async (chatId, reason) => {
      await api(`/kc/harness/chats/${chatId}/finish`, { method: "POST", body: JSON.stringify({ reason }) });
    },
  };
}

async function judgeChat(chatId: string, model: string) {
  const detail = await api<{
    child?: { description?: string };
    turns?: { seq: number; intent: string; child_text: string; session_after?: { tutor_reply?: string } }[];
  }>(`/kc/harness/chats/${chatId}`);
  const transcript = (detail.turns || [])
    .map((turn) => `${turn.seq}. child (${turn.intent}): ${turn.child_text}\ntutor: ${turn.session_after?.tutor_reply || ""}`)
    .join("\n");
  const response = await fetch("/api/kc/harness/judge", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ model, transcript, child: detail.child?.description || "" }),
  });
  if (!response.ok) return;
  const judged = await response.json();
  await api(`/kc/harness/chats/${chatId}/evaluations`, {
    method: "POST",
    body: JSON.stringify({
      scores: judged.scores,
      tags: judged.tags,
      child_realism: judged.child_realism,
      rubric_version: judged.rubric_version,
      judge_model: judged.judge_model,
      usage: judged.usage,
    }),
  });
}

export function RunsTab({
  selected,
  onOpenChat,
}: {
  selected: string;
  onOpenChat: (runId: string, chatId: string) => void;
}) {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [detail, setDetail] = useState<{ id: string; chat_rows?: ChatRow[] } | null>(null);
  const [sessions, setSessions] = useState<Record<string, SessionMessage[]>>({});
  const [error, setError] = useState("");
  const [driving, setDriving] = useState("");
  const [live, setLive] = useState<LiveLine[]>([]);

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
    const gate = { aborted: false };
    try {
      await api(`/kc/harness/runs/${run.id}/resume`, { method: "POST" });
      const client = transport(run.id);
      await driveRun(
        run.id,
        async () => {
          const claimed = await api<{ chat: ClaimedChat | null }>(`/kc/harness/runs/${run.id}/claim`, { method: "POST" });
          return claimed.chat;
        },
        client,
        run.plan?.concurrency || 3,
        gate,
        (line) => {
          setLive((current) => {
            const last = current[current.length - 1];
            if (last && last.role === line.role && last.text === line.text && last.chatId === line.chatId) return current;
            return [...current, line].slice(-40);
          });
        },
      );
      const latest = await api<{ chat_rows?: { id: string; status: string }[]; plan?: { judge_model?: string } }>(`/kc/harness/runs/${run.id}`);
      const judgeModel = latest.plan?.judge_model || "gpt-6.1-sol";
      for (const chat of latest.chat_rows || []) {
        if (chat.status === "completed" || chat.status === "failed") {
          try {
            await judgeChat(chat.id, judgeModel);
          } catch {
            setError("A chat finished, and the judge did not score it.");
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "The run stopped.");
    } finally {
      setDriving("");
      await refresh();
    }
  }

  const rows = detail?.chat_rows || [];
  const active = rows.filter((chat) => chat.status === "running" || chat.status === "queued");
  const known = new Set(active.map((chat) => chat.id));
  const pendingOnly = [...new Set(live.map((line) => line.chatId))].filter((chatId) => !known.has(chatId));
  const showLive = active.length > 0 || pendingOnly.length > 0;

  return (
    <section className="harness-panel">
      <h2>Runs</h2>
      {error ? <p className="banner">{error}</p> : null}
      {showLive ? (
        <div className="harness-live">
          <h3>In progress</h3>
          {active.map((chat) => {
            const lines = transcriptForChat(chat.id, sessions[chat.id], live);
            return (
              <article key={chat.id}>
                <p>
                  <button type="button" onClick={() => onOpenChat(detail?.id || "", chat.id)}>
                    {chat.child?.name || "Test child"} · {chat.status}
                  </button>
                </p>
                {lines.length > 0 ? (
                  <ol className="harness-transcript">
                    {lines.map((line, index) => (
                      <li key={`${chat.id}-${index}`}>
                        <strong>{line.role === "tutor" ? "Tutor" : "Child"}:</strong> {line.text}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="help">
                    {chat.session_id ? "Waiting for the first tutor message." : "Queued. Press Resume to start this chat."}
                  </p>
                )}
              </article>
            );
          })}
          {pendingOnly.map((chatId) => {
            const lines = transcriptForChat(chatId, [], live);
            return (
              <article key={chatId}>
                <p>Running chat</p>
                <ol className="harness-transcript">
                  {lines.map((line, index) => (
                    <li key={`${chatId}-${index}`}>
                      <strong>{line.role === "tutor" ? "Tutor" : "Child"}:</strong> {line.text}
                    </li>
                  ))}
                </ol>
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
                  {driving === run.id ? "Running" : "Resume"}
                </button>
                <button type="button" onClick={() => void act(`/kc/harness/runs/${run.id}/pause`)}>
                  Pause
                </button>
                <button type="button" onClick={() => void act(`/kc/harness/runs/${run.id}/cancel`)}>
                  Cancel
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
        Trim keeps prompts for the baseline and the newest run of each suite. Older runs keep the transcript, scores, intents, and recommendations.
      </p>
      <ul>
        {(detail?.chat_rows || []).map((chat) => (
          <li key={chat.id}>
            <button type="button" onClick={() => onOpenChat(detail?.id || "", chat.id)}>
              {chat.child?.name} · {chat.tutor_model} · {chat.status} {chat.ended_how} · cost {chat.cost_usd ?? "blank"} · luna {chat.luna_tokens}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
