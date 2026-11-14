"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

type Turn = {
  seq: number;
  intent: string;
  child_text: string;
  child_prompt?: string;
  tutor_prompt?: string;
  inner_state: { boredom?: number; frustration?: number; confusion?: number };
  session_after?: { tutor_reply?: string };
};

type LiveMessage = { role: string; content: string };

type ChatDetail = {
  id: string;
  status?: string;
  session_id?: string;
  ended_how: string;
  cost_usd: string | null;
  luna_tokens: number;
  child?: { name?: string; description?: string };
  model_prompts?: { seq: number; model: string; system_prompt: string }[];
  turns?: Turn[];
  evaluations?: {
    kind: string;
    checks?: Record<string, unknown>;
    scores?: { dimension: string; score: number; quote: string; turn: number }[];
    tags?: { tag: string; turn: number; quote: string }[];
    child_realism?: number | null;
  }[];
  safety_flags?: { category: string; child_message: string; tutor_reply: string }[];
};

export function ChatTab({ chatId }: { chatId: string }) {
  const [chat, setChat] = useState<ChatDetail | null>(null);
  const [live, setLive] = useState<LiveMessage[]>([]);
  const [openPrompt, setOpenPrompt] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!chatId) return;
    let stop = false;
    let timer = 0;
    async function pull() {
      const next = await api<ChatDetail>(`/kc/harness/chats/${chatId}`);
      if (stop) return;
      setChat(next);
      setError("");
      const active = next.status === "running" || next.status === "queued";
      if (active && next.session_id) {
        const session = await api<{ messages?: LiveMessage[] }>(`/kc/tutor/sessions/${next.session_id}`);
        if (!stop) setLive(session.messages || []);
      } else if (!stop) {
        setLive([]);
      }
      if (active && !stop) timer = window.setTimeout(() => void pull().catch(() => undefined), 2000);
    }
    void pull().catch((err) => {
      if (!stop) setError(err instanceof Error ? err.message : "Could not load the chat.");
    });
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [chatId]);

  if (!chatId) return <p className="help">Open a chat from a run.</p>;
  if (error) return <p className="banner">{error}</p>;
  if (!chat) return <p className="help">Loading the chat.</p>;
  const automatic = chat.evaluations?.find((item) => item.kind === "automatic");
  const judged = chat.evaluations?.find((item) => item.kind === "judged");

  function download() {
    const blob = new Blob([JSON.stringify(chat, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${chat?.child?.name || "chat"}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="harness-panel">
      <header className="harness-panel-head">
        <h2>
          {chat.child?.name} · {chat.ended_how || "in progress"}
        </h2>
        <button type="button" onClick={download}>
          Download JSON
        </button>
      </header>
      <p className="help">
        {chat.child?.description} · priced cost {chat.cost_usd ?? "blank"} · luna tokens {chat.luna_tokens}
        {chat.session_id ? ` · session ${chat.session_id}` : ""}
      </p>
      {live.length > 0 ? (
        <>
          <h3>Live transcript</h3>
          <ol className="harness-transcript">
            {live.map((message, index) => (
              <li key={`${index}-${message.role}`}>
                <strong>{message.role === "assistant" ? "Tutor" : "Child"}:</strong> {message.content}
              </li>
            ))}
          </ol>
        </>
      ) : null}
      <ol className="harness-transcript">
        {(chat.turns || []).map((turn) => (
          <li key={turn.seq}>
            <p>
              <strong>{turn.intent}</strong> · boredom {turn.inner_state?.boredom ?? 0} · frustration {turn.inner_state?.frustration ?? 0}
            </p>
            <p>Child: {turn.child_text}</p>
            <p>Tutor: {turn.session_after?.tutor_reply}</p>
            <button type="button" onClick={() => setOpenPrompt(openPrompt === turn.seq ? null : turn.seq)}>
              {openPrompt === turn.seq ? "Hide prompts" : "Show both prompts"}
            </button>
            {openPrompt === turn.seq ? (
              <>
                <h4>Tutor prompt</h4>
                <pre className="harness-json">{turn.tutor_prompt || "This turn has no stored tutor prompt."}</pre>
                <h4>Child prompt</h4>
                <pre className="harness-json">
                  {turn.child_prompt || "This turn did not call the child model."}
                </pre>
              </>
            ) : null}
          </li>
        ))}
      </ol>
      {(chat.model_prompts || []).length > 0 ? (
        <>
          <h3>Tutor prompts stored for this session</h3>
          {(chat.model_prompts || []).map((prompt) => (
            <details key={prompt.seq}>
              <summary>Tutor prompt {prompt.seq} · {prompt.model || "model"}</summary>
              <pre className="harness-json">{prompt.system_prompt}</pre>
            </details>
          ))}
        </>
      ) : null}
      <h3>Automatic checks</h3>
      <pre className="harness-json">{JSON.stringify(automatic?.checks || {}, null, 2)}</pre>
      <h3>Judge</h3>
      {judged ? (
        <ul>
          {(judged.scores || []).map((score) => (
            <li key={score.dimension}>
              {score.dimension}: {score.score}. Turn {score.turn}. “{score.quote}”
            </li>
          ))}
          <li>Child realism {judged.child_realism ?? "—"}</li>
        </ul>
      ) : (
        <p className="help">No judged scorecard yet.</p>
      )}
      <h3>Safety flags on this chat</h3>
      {(chat.safety_flags || []).length === 0 ? <p className="help">No flags. Flags from a test child stay off the AI Safety queue.</p> : null}
      <ul>
        {(chat.safety_flags || []).map((flag) => (
          <li key={`${flag.category}-${flag.child_message}`}>
            {flag.category}: {flag.child_message}
          </li>
        ))}
      </ul>
      {chat.session_id ? (
        <p>
          <a href={`/admin/kc-chats`}>Open KC View Chats</a> and turn on Show test children to read the stored prompt for session {chat.session_id}.
        </p>
      ) : null}
    </section>
  );
}
