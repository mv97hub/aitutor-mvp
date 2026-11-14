"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ClaimedChat, HarnessTransport, SessionSnap } from "@/lib/harness-runner";
import { driveRun } from "@/lib/harness-runner";

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
  const [detail, setDetail] = useState<{ id: string; chat_rows?: { id: string; status: string; ended_how: string; child?: { name?: string }; tutor_model: string; cost_usd: string | null; luna_tokens: number }[] } | null>(null);
  const [error, setError] = useState("");
  const [driving, setDriving] = useState("");

  async function refresh() {
    const next = await api<RunRow[]>("/kc/harness/runs");
    setRuns(next);
    const id = selected || next[0]?.id;
    if (id) setDetail(await api(`/kc/harness/runs/${id}`));
  }

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : "Could not load runs."));
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

  return (
    <section className="harness-panel">
      <h2>Runs</h2>
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
