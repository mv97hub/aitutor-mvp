"use client";

import { useEffect, useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { api } from "@/lib/api";
import type { KcChatDetail, KcChatSummary } from "@/lib/kc";
import { promptsOnTranscript } from "@/lib/kc-chat-prompts";
import type { Student } from "@/lib/types";

type KcPrompt = KcChatDetail["prompts"][number];

function when(iso: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
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

export function ViewKcChats({
  initialStudents,
  initialError,
}: {
  initialStudents: Student[];
  initialError: string | null;
}) {
  const [students] = useState(initialStudents);
  const [studentFilter, setStudentFilter] = useState("");
  const [sessions, setSessions] = useState<KcChatSummary[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<KcChatDetail | null>(null);
  const [error, setError] = useState(initialError);

  useEffect(() => {
    const query = studentFilter ? `?student_id=${studentFilter}` : "";
    let cancelled = false;
    api<KcChatSummary[]>(`/kc/sessions${query}`)
      .then((next) => {
        if (!cancelled) {
          setSessions(next);
          if (next.length > 0 && (!sessionId || !next.some((item) => item.id === sessionId))) {
            setSessionId(next[0].id);
          }
        }
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, [studentFilter, sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    api<KcChatDetail>(`/kc/sessions/${sessionId}`)
      .then((next) => {
        if (!cancelled) setSession(next);
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <AdminFrame current="kc-chats">
      <div className="kc-chats-admin-workspace">
        <section className="kc-chats-toolbar" aria-label="KC Chat Sessions">
          <div className="kc-chats-toolbar-top">
            <div>
              <p className="eyebrow">Administration</p>
              <h2>KC View Chats</h2>
              <p className="help">
                Inspect learner component transcripts, scores, and full system prompts sent to the model.
              </p>
            </div>
            <label className="kc-chats-student-filter">
              Student
              <select value={studentFilter} onChange={(event) => setStudentFilter(event.target.value)}>
                <option value="">Everyone</option>
                {students.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.display_name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <ul className="ds-list kc-chats-session-strip" aria-label="KC chats">
            {sessions.length === 0 ? <li className="ds-quiet">No chats yet. Open a learner on KC Tutor.</li> : null}
            {sessions.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={`ds-row kc-chat-pill-row ${item.id === sessionId ? "is-on" : ""}`}
                  onClick={() => setSessionId(item.id)}
                >
                  <strong>{item.student_display_name}</strong>
                  <small>
                    {item.kc_title} · {item.course_title} · {item.status.replace("_", " ")} · {when(item.updated_at)}
                  </small>
                  <small>
                    {item.message_count} messages · {item.score == null ? "no score" : "1 score"}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {error ? (
          <div className="banner" role="alert" style={{ margin: "18px 0" }}>
            <p>{error}</p>
          </div>
        ) : null}
        {session ? (
          <SessionView session={session} />
        ) : (
          <article className="transcript-view">
            <h2>Pick a chat</h2>
            <p className="help">The transcript opens here. This page does not edit components.</p>
          </article>
        )}
      </div>
    </AdminFrame>
  );
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

function scoreCountLabel(score: number | null) {
  return score == null ? "None yet" : "1 score";
}

function SessionView({ session }: { session: KcChatDetail }) {
  const [prompt, setPrompt] = useState<KcPrompt | null>(null);
  const [scoresOpen, setScoresOpen] = useState(false);
  const { placed, leftover } = promptsOnTranscript(session.messages, session.prompts ?? []);
  useEffect(() => {
    setPrompt(null);
    setScoresOpen(false);
  }, [session.id]);
  const now = session.status === "completed" ? "component finished" : `now on ${session.step_label}`;
  return (
    <article className="transcript-view">
      <p className="eyebrow">{session.student.display_name}</p>
      <h2>{session.component.title}</h2>
      <p className="meta">
        {session.component.code} · {session.course.title} · {session.status.replaceAll("_", " ")} · opened{" "}
        {when(session.created_at)}
        {` · ${now}`}
      </p>
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
