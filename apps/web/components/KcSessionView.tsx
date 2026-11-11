"use client";

import { useEffect, useState, type ReactNode } from "react";

import type { KcChatDetail, KcTokenTurn, KcTokenUsage } from "@/lib/kc";
import { promptsOnTranscript } from "@/lib/kc-chat-prompts";

type KcPrompt = KcChatDetail["prompts"][number];

/** What a transcript needs. The parent view has no prompts key at all. */
export type ChatViewData = Pick<
  KcChatDetail,
  "id" | "status" | "step_label" | "score" | "created_at" | "updated_at" | "messages"
> & {
  tutor_model?: string;
  student: { display_name: string; tutor_model?: string };
  course: { title: string };
  component: { code: string; title: string };
  prompts?: KcPrompt[];
  token_usage?: KcTokenUsage;
};

export function when(iso: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}


function messageRole(message: unknown) {
  if (message && typeof message === "object" && "role" in message && typeof message.role === "string") {
    return message.role;
  }
  return "message";
}

function messageBody(message: unknown) {
  const content =
    message && typeof message === "object" && "content" in message
      ? (message as { content: unknown }).content
      : message;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "text" in part && typeof part.text === "string") return part.text;
        return JSON.stringify(part, null, 2);
      })
      .join("\n");
  }
  return JSON.stringify(content, null, 2);
}

function isRequestNote(message: unknown) {
  return messageRole(message) === "request";
}

function PromptDialog({
  prompt,
  subtitle,
  onClose,
}: {
  prompt: KcPrompt;
  subtitle: string;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="prompt-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="kc-prompt-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="kc-prompt-title">View full prompt to debug</h2>
            <p>{subtitle}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="prompt-body">
          <p className="meta">
            {prompt.model || "Model"} · {when(prompt.created_at)}
          </p>
          <h3>System prompt</h3>
          <pre className="prompt-pre">{prompt.system_prompt}</pre>
          <h3>Messages sent to the model</h3>
          {prompt.messages.filter((message) => !isRequestNote(message)).length === 0 ? (
            <p className="help">No messages were attached to this call.</p>
          ) : null}
          <ol className="prompt-messages">
            {prompt.messages
              .filter((message) => !isRequestNote(message))
              .map((message, index) => (
                <li key={`${prompt.id}-${index}`}>
                  <strong>{messageRole(message)}</strong>
                  <pre className="prompt-pre">{messageBody(message)}</pre>
                </li>
              ))}
          </ol>
          {prompt.messages
            .filter(isRequestNote)
            .map((message, index) => (
              <div key={`${prompt.id}-request-${index}`}>
                <h3>Also sent to the model</h3>
                <pre className="prompt-pre">{messageBody(message)}</pre>
              </div>
            ))}
          {prompt.rubric_met && prompt.rubric_met.length > 0 ? (
            <p className="meta">Rubric points met: {prompt.rubric_met.join(", ")}</p>
          ) : null}
          {prompt.misconception ? <p className="meta">Misconception: {prompt.misconception}</p> : null}
        </div>
      </div>
    </div>
  );
}

function tokenSummary(turn: KcTokenTurn) {
  return `${turn.kind} · in ${turn.input_tokens} · out ${turn.output_tokens} · cached ${turn.cached_tokens} · total ${turn.total_tokens}`;
}

function scoreCountLabel(score: number | null) {
  return score == null ? "None yet" : "1 score";
}

export function SessionView({
  session,
  debug = false,
  actions = null,
  heading = "desk",
}: {
  session: ChatViewData;
  /** Admin only. A parent view passes false and never receives prompts. */
  debug?: boolean;
  /** Optional control for the admin chat. The parent view leaves this unset. */
  actions?: ReactNode;
  /** Parent chats use the shared work-area heading. Admin keeps the desk title. */
  heading?: "desk" | "work";
}) {
  const [prompt, setPrompt] = useState<KcPrompt | null>(null);
  const [scoresOpen, setScoresOpen] = useState(false);
  const { placed, leftover } = debug
    ? promptsOnTranscript(session.messages, session.prompts ?? [])
    : { placed: new Map<string, KcPrompt>(), leftover: [] as KcPrompt[] };
  const usage = debug ? session.token_usage : undefined;
  const usageByMessage = new Map<string, KcTokenTurn[]>();
  const usageUnmatched: KcTokenTurn[] = [];
  for (const turn of usage?.turns ?? []) {
    if (turn.message_id && session.messages.some((message) => message.id === turn.message_id)) {
      const list = usageByMessage.get(turn.message_id) ?? [];
      list.push(turn);
      usageByMessage.set(turn.message_id, list);
    } else {
      usageUnmatched.push(turn);
    }
  }
  useEffect(() => {
    setPrompt(null);
    setScoresOpen(false);
  }, [session.id]);
  const now = session.status === "completed" ? "component finished" : `now on ${session.step_label}`;
  const deskTitle = (
    <>
      <p className="eyebrow">{session.student.display_name}</p>
      <h2>{session.component.title}</h2>
    </>
  );
  const workTitle = (
    <header className="parent-work-head">
      <h1>{session.student.display_name}</h1>
      <p>
        {session.component.title} · {session.course.title} · {session.status.replaceAll("_", " ")}
      </p>
    </header>
  );
  const title = heading === "work" ? workTitle : deskTitle;
  return (
    <article className="transcript-view">
      {actions ? (
        <div className="transcript-actions">
          <div>{title}</div>
          {actions}
        </div>
      ) : (
        title
      )}
      <p className="meta">
        {heading === "work"
          ? `${session.component.code} · opened ${when(session.created_at)} · ${now}`
          : `${session.component.code} · ${session.course.title} · ${session.status.replaceAll("_", " ")} · opened ${when(session.created_at)} · ${now}`}
      </p>
      {debug && (session.student.tutor_model || session.tutor_model) ? (
        <p className="meta">
          AI Model {session.student.tutor_model || session.tutor_model}
          {session.tutor_model ? ` · latest turn ${session.tutor_model}` : ""}
        </p>
      ) : null}
      <div className="score-fold">
        <h3>
          <button
            type="button"
            className="score-toggle"
            aria-expanded={scoresOpen}
            aria-controls="kc-session-scores"
            onClick={() => setScoresOpen((open) => !open)}
          >
            <span>Scores</span>
            <span className="score-toggle-meta">
              {scoreCountLabel(session.score)}
              <span className="score-toggle-action">{scoresOpen ? "Hide" : "Show"}</span>
              <span className="score-chevron" aria-hidden="true">
                {scoresOpen ? "▴" : "▾"}
              </span>
            </span>
          </button>
        </h3>
        <div id="kc-session-scores" hidden={!scoresOpen}>
          {session.score == null ? (
            <p className="help">No scores stored yet.</p>
          ) : (
            <ul className="score-list">
              <li>
                <strong className={session.score >= 100 ? "pass" : "miss"}>
                  {session.score >= 100 ? "Passed" : "Not yet"} · {session.score}/100
                </strong>
                <span className="quiet">
                  {session.component.title} · {session.step_label} · {when(session.updated_at)}
                </span>
              </li>
            </ul>
          )}
        </div>
      </div>
      {usage ? (
        <div className="score-fold">
          <h3>Token usage</h3>
          <p className="meta">
            Session total · in {usage.total.input_tokens} · out {usage.total.output_tokens} · cached{" "}
            {usage.total.cached_tokens} · total {usage.total.total_tokens}
          </p>
          {usage.turns.length === 0 ? <p className="help">No token usage stored for this chat.</p> : null}
        </div>
      ) : null}
      <h3>Transcript</h3>
      {session.messages.length === 0 ? <p className="help">No messages stored yet.</p> : null}
      <ol className="transcript-list">
        {session.messages.map((message) => {
          const turnPrompt = placed.get(message.id);
          return (
            <li key={message.id} className={message.role}>
              <div className="transcript-line">
                <div>
                  <strong>{message.role === "user" ? session.student.display_name : "Tutor"}</strong>
                  <span className="quiet">{when(message.created_at)}</span>
                  <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap" }}>{message.content}</p>
                  {(usageByMessage.get(message.id) ?? []).map((turn) => (
                    <p key={turn.id} className="quiet">
                      {tokenSummary(turn)}
                    </p>
                  ))}
                </div>
                {turnPrompt ? (
                  <button type="button" className="ds-debug" onClick={() => setPrompt(turnPrompt)}>
                    View full prompt to debug
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
      {usageUnmatched.length > 0 ? (
        <div>
          <h3>Token usage without a matching turn</h3>
          <ul className="score-list">
            {usageUnmatched.map((turn) => (
              <li key={turn.id}>
                <span className="quiet">
                  {tokenSummary(turn)} · {turn.model || "Model"} · {when(turn.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {leftover.length > 0 ? (
        <div>
          <h3>Other model calls</h3>
          <ul className="score-list">
            {leftover.map((item) => (
              <li key={item.id}>
                <button type="button" className="ds-debug" onClick={() => setPrompt(item)}>
                  View full prompt to debug
                </button>
                <span className="quiet">
                  {item.model || "Model"} · {when(item.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {prompt ? (
        <PromptDialog
          prompt={prompt}
          subtitle={`${session.student.display_name} · ${session.component.title}`}
          onClose={() => setPrompt(null)}
        />
      ) : null}
    </article>
  );
}
