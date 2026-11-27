"use client";

import { useEffect, useState, type FormEvent } from "react";

import { api } from "@/lib/api";
import { downloadHarnessFile } from "@/lib/harness-file";
import { readerPracticeChecks, READER_PRACTICE, type PracticeTurn } from "@/lib/harness-reader-practice";
import { blockMarks } from "@/lib/harness-blocks";
import { agreementLabel, DIMENSIONS } from "@/lib/harness-judge";
import { childPromptText } from "@/lib/harness-policy";

type Turn = PracticeTurn & {
  seq: number;
  intent: string;
  child_text: string;
  child_prompt?: string;
  tutor_prompt?: string;
  child_tokens?: { input_tokens?: number; output_tokens?: number };
  inner_state: { boredom?: number; frustration?: number; confusion?: number };
  session_after?: { tutor_reply?: string; block_id?: string; block_type?: string; block_title?: string };
  loop_decision?: string;
};

type LiveMessage = { role: string; content: string; seq?: number };

type Score = { dimension: string; score: number; quote: string; turn: number };

type ChatDetail = {
  id: string;
  run_id?: string;
  status?: string;
  session_id?: string;
  ended_how: string;
  cost_usd: string | null;
  luna_tokens: number;
  child?: { name?: string; description?: string; scenario?: string };
  model_prompts?: { seq: number; model: string; system_prompt: string }[];
  turns?: Turn[];
  evaluations?: {
    kind: string;
    checks?: Record<string, unknown>;
    scores?: Score[];
    tags?: { tag: string; turn: number; quote: string }[];
    child_realism?: number | null;
    error?: string;
  }[];
  component_score?: number | null;
  block_outcomes?: { title: string; outcome: string }[];
  safety_flags?: { category: string; child_message: string; tutor_reply: string }[];
};

type SavedChat = {
  id: string;
  run_id?: string;
  status?: string;
  ended_how?: string;
  tutor_model?: string;
  created_at?: string;
  child?: { name?: string };
};

export function ChatTab({ chatId }: { chatId: string }) {
  const [saved, setSaved] = useState<SavedChat[]>([]);
  const [openId, setOpenId] = useState(chatId);
  const [chat, setChat] = useState<ChatDetail | null>(null);
  const [live, setLive] = useState<LiveMessage[]>([]);
  const [openPrompt, setOpenPrompt] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [handDraft, setHandDraft] = useState<Record<string, string>>({});
  const [savingHand, setSavingHand] = useState(false);

  useEffect(() => {
    if (chatId) setOpenId(chatId);
  }, [chatId]);

  useEffect(() => {
    let stop = false;
    api<SavedChat[]>("/kc/harness/chats")
      .then((rows) => {
        if (!stop) setSaved(Array.isArray(rows) ? rows : []);
      })
      .catch(() => {
        if (!stop) setSaved([]);
      });
    return () => {
      stop = true;
    };
  }, [openId]);

  useEffect(() => {
    if (!openId) return;
    let stop = false;
    let timer = 0;
    async function pull() {
      const next = await api<ChatDetail>(`/kc/harness/chats/${openId}`);
      if (stop) return;
      setChat(next);
      setError("");
      const hand = next.evaluations?.find((item) => item.kind === "hand");
      const draft: Record<string, string> = {};
      for (const score of hand?.scores || []) {
        if (score.dimension) draft[score.dimension] = String(score.score);
      }
      setHandDraft(draft);
      const active = next.status === "running" || next.status === "queued";
      if ((active || (next.ended_how === "scenario_not_reached" && !next.turns?.length)) && next.session_id) {
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
  }, [openId]);

  async function saveHand(event: FormEvent) {
    event.preventDefault();
    if (!openId || savingHand) return;
    const scores = DIMENSIONS.flatMap((dimension) => {
      const raw = handDraft[dimension];
      if (!raw) return [];
      const score = Number(raw);
      if (score < 1 || score > 5) return [];
      return [{ dimension, score }];
    });
    setSavingHand(true);
    try {
      const next = await api<ChatDetail>(`/kc/harness/chats/${openId}/hand-scores`, {
        method: "POST",
        body: JSON.stringify({ scores }),
      });
      setChat(next);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your scores.");
    } finally {
      setSavingHand(false);
    }
  }

  const automatic = chat?.evaluations?.find((item) => item.kind === "automatic");
  const judged = chat?.evaluations?.find((item) => item.kind === "judged");
  const hand = chat?.evaluations?.find((item) => item.kind === "hand");
  const handByDimension = new Map((hand?.scores || []).map((score) => [score.dimension, score.score]));
  const marks = blockMarks(chat?.turns || []);

  async function download() {
    if (!chat) return;
    setError("");
    try {
      await downloadHarnessFile(`/api/kc/harness/chats/${chat.id}/download`, `harness-chat-${chat.id}.md`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not download the chat.");
    }
  }

  return (
    <section className="harness-panel">
      <h2>Saved chats</h2>
      <p className="help">Every test chat the harness has stored. Open one from any run.</p>
      {saved.length === 0 ? <p className="help">No saved chats yet.</p> : null}
      <ul className="harness-saved-chats">
        {saved.map((row) => (
          <li key={row.id}>
            <button type="button" className={row.id === openId ? "is-active" : ""} onClick={() => setOpenId(row.id)}>
              {row.child?.name || "Test child"} · {row.tutor_model || "model"} · {row.ended_how || row.status || "saved"} ·{" "}
              {(row.created_at || "").slice(0, 16).replace("T", " ")} · run {String(row.run_id || "").slice(0, 8)}
            </button>
          </li>
        ))}
      </ul>
      {!openId ? <p className="help">Choose a saved chat.</p> : null}
      {error ? <p className="banner">{error}</p> : null}
      {openId && !chat && !error ? <p className="help">Loading the chat.</p> : null}
      {chat ? (
        <>
          <header className="harness-panel-head">
            <h2>
              {chat.child?.name} · {chat.ended_how || "in progress"}
            </h2>
            <button type="button" onClick={() => void download()}>
              Download
            </button>
          </header>
          <p className="help">
            {chat.child?.description} · priced cost {chat.cost_usd ?? "blank"} · luna tokens {chat.luna_tokens}
            {chat.session_id ? ` · session ${chat.session_id}` : ""}
            {chat.component_score != null || (chat.block_outcomes || []).length
              ? ` · score ${chat.component_score ?? "not finished"}. ${(chat.block_outcomes || []).map((item) => `${item.title} (${item.outcome})`).join(", ") || "no block outcomes"}.`
              : ""}
          </p>
          {live.length > 0 ? (
            <>
              <h3>{chat.ended_how === "scenario_not_reached" ? "Tutor opening" : "Live transcript"}</h3>
              <ol className="harness-transcript">
                {live.map((message, index) => (
                  <li key={`${message.seq ?? index}-${message.role}`}>
                    <strong>
                      {typeof message.seq === "number" ? `${message.seq}. ` : ""}
                      {message.role === "assistant" ? "Tutor" : "Child"}:
                    </strong>{" "}
                    {message.content}
                  </li>
                ))}
              </ol>
            </>
          ) : null}
          {chat.child?.scenario === READER_PRACTICE ? (
            <section>
              <h3>River roads practice</h3>
              <dl>
                {readerPracticeChecks(chat.turns || []).map((outcome, index) => (
                  <div key={index}>
                    <dt>{index === 0 ? "Request for an example" : "Answer to the boat question"}</dt>
                    <dd>{outcome}</dd>
                  </div>
                ))}
              </dl>
              {chat.ended_how === "scenario_not_reached" ? (
                <p className="help">The expected question did not match the script. Check the tutor’s wording below.</p>
              ) : null}
            </section>
          ) : null}
          <h3>Transcript</h3>
          <ol className="harness-transcript">
            {(chat.turns || []).map((turn) => {
              const starts = marks.filter((mark) => mark.seq === turn.seq && mark.edge === "start");
              const ends = marks.filter((mark) => mark.seq === turn.seq && mark.edge === "end");
              return (
                <li key={turn.seq}>
                  {starts.map((mark) => (
                    <p key={`start-${mark.seq}`} className="harness-block-mark" data-block-edge="start">
                      Start of block: {mark.label}
                    </p>
                  ))}
                  <p>
                    <strong>Intent:</strong> {turn.intent} · boredom {turn.inner_state?.boredom ?? 0} · frustration{" "}
                    {turn.inner_state?.frustration ?? 0}
                  </p>
                  <p>Child: {turn.child_text}</p>
                  <p>Tutor: {turn.session_after?.tutor_reply}</p>
                  <p>Loop decision: {turn.loop_decision || "not stored"}</p>
                  {ends.map((mark) => (
                    <p key={`end-${mark.seq}`} className="harness-block-mark" data-block-edge="end">
                      End of block: {mark.label}
                    </p>
                  ))}
                  <button type="button" onClick={() => setOpenPrompt(openPrompt === turn.seq ? null : turn.seq)}>
                    {openPrompt === turn.seq ? "Hide prompts" : "Show both prompts"}
                  </button>
                  {openPrompt === turn.seq ? (
                    <>
                      <h4>Tutor prompt</h4>
                      <pre className="harness-json">{turn.tutor_prompt || "This turn has no stored tutor prompt."}</pre>
                      <h4>Child prompt</h4>
                      <pre className="harness-json">{childPromptText(turn)}</pre>
                    </>
                  ) : null}
                </li>
              );
            })}
          </ol>
          {(chat.model_prompts || []).length > 0 ? (
            <>
              <h3>Tutor prompts stored for this session</h3>
              {(chat.model_prompts || []).map((prompt) => (
                <details key={prompt.seq}>
                  <summary>
                    Tutor prompt {prompt.seq} · {prompt.model || "model"}
                  </summary>
                  <pre className="harness-json">{prompt.system_prompt}</pre>
                </details>
              ))}
            </>
          ) : null}
          <h3>Automatic checks</h3>
          <pre className="harness-json">{JSON.stringify(automatic?.checks || {}, null, 2)}</pre>
          <h3>Judge</h3>
          {judged?.error || (judged && judged.child_realism == null && !(judged.scores || []).length) ? (
            <p className="help">not judged</p>
          ) : judged ? (
            <ul>
              {(judged.scores || []).map((score) => {
                const handScore = handByDimension.get(score.dimension);
                return (
                  <li key={score.dimension}>
                    {score.dimension}: {score.score}. Turn {score.turn}. “{score.quote}”
                    {handScore != null ? ` Hand ${handScore}, ${agreementLabel(score.score, handScore)}.` : ""}
                  </li>
                );
              })}
              <li>Child realism {judged.child_realism ?? "not judged"}</li>
              {(judged.tags || []).map((tag) => (
                <li key={`${tag.tag}-${tag.turn}`}>
                  {tag.tag} on turn {tag.turn}. “{tag.quote}”
                </li>
              ))}
            </ul>
          ) : (
            <p className="help">No judged scorecard yet.</p>
          )}
          <h3>Your scores</h3>
          <p className="help">Empty until you enter a 1 to 5 on the same dimensions. Agreement shows next to the judge after you save.</p>
          <form className="harness-hand" onSubmit={(event) => void saveHand(event)}>
            {DIMENSIONS.map((dimension) => (
              <label key={dimension}>
                {dimension.replaceAll("_", " ")}
                <select
                  aria-label={dimension.replaceAll("_", " ")}
                  value={handDraft[dimension] ?? ""}
                  onChange={(event) => setHandDraft((current) => ({ ...current, [dimension]: event.target.value }))}
                >
                  <option value=""> </option>
                  {[1, 2, 3, 4, 5].map((score) => (
                    <option key={score} value={score}>
                      {score}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <button type="submit" disabled={savingHand}>
              {savingHand ? "Saving" : "Save your scores"}
            </button>
          </form>
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
        </>
      ) : null}
    </section>
  );
}
