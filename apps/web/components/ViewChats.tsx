"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ModelPrompt, SessionDetail, SessionSummary, Student } from "@/lib/types";

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

function PromptIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M5.2 3.2 2.4 8l2.8 4.8M10.8 3.2 13.6 8l-2.8 4.8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
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

export function ViewChats({ initialStudents, initialError }: { initialStudents: Student[]; initialError: string | null }) {
  const [students] = useState(initialStudents);
  const [studentFilter, setStudentFilter] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [error, setError] = useState(initialError);
  const [promptChat, setPromptChat] = useState<SessionSummary | null>(null);

  useEffect(() => {
    const query = studentFilter ? `?student_id=${studentFilter}` : "";
    let cancelled = false;
    api<SessionSummary[]>(`/sessions${query}`)
      .then((next) => {
        if (!cancelled) setSessions(next);
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, [studentFilter]);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    api<SessionDetail>(`/sessions/${sessionId}`)
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
    <main className="desk">
      <aside className="side">
        <div className="side-head">
          <p className="eyebrow">Transcripts</p>
          <span className="top-links">
            <Link className="top-link" href="/admin">Edit lessons</Link>
            <Link className="top-link" href="/">Kid session</Link>
          </span>
        </div>
        <h1>View chats</h1>
        <p className="lede">Filter by student, open a class, and read the messages and checkpoint scores.</p>
        <label>
          Student
          <select value={studentFilter} onChange={(event) => setStudentFilter(event.target.value)}>
            <option value="">Everyone</option>
            {students.map((student) => (
              <option key={student.id} value={student.id}>{student.display_name}</option>
            ))}
          </select>
        </label>
        <div className="stack">
          {sessions.length === 0 ? <p className="help">No classes yet. Open a learner on the kid page.</p> : null}
          {sessions.map((item) => (
            <div key={item.id} className={`session-choice ${item.id === sessionId ? "is-on" : ""}`}>
              <button type="button" className="session-open" onClick={() => setSessionId(item.id)}>
                <strong>{item.student_display_name}</strong>
                <small style={{ display: "block" }}>
                  {item.lesson_title} · {item.status.replace("_", " ")} · {when(item.updated_at)}
                </small>
                <small>{item.message_count} messages · {item.result_count} scores</small>
              </button>
              <button
                type="button"
                className="prompt-icon"
                aria-label={`View the full prompt for ${item.student_display_name}, ${item.lesson_title}`}
                onClick={() => setPromptChat(item)}
              >
                <PromptIcon />
              </button>
            </div>
          ))}
        </div>
      </aside>
      <section>
        {error ? (
          <div className="banner" role="alert" style={{ margin: 18 }}>
            <p>{error}</p>
          </div>
        ) : null}
        {promptChat ? <PromptDialog chat={promptChat} onClose={() => setPromptChat(null)} /> : null}
        {session ? <SessionView session={session} /> : (
          <article className="transcript-view">
            <h2>Pick a class</h2>
            <p className="help">The transcript opens here. This page does not edit blocks.</p>
          </article>
        )}
      </section>
    </main>
  );
}

function PromptDialog({ chat, onClose }: { chat: SessionSummary; onClose: () => void }) {
  const [prompts, setPrompts] = useState<ModelPrompt[] | null>(null);
  const [turn, setTurn] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPrompts(null);
    setTurn(0);
    setLoadError(null);
    api<ModelPrompt[]>(`/sessions/${chat.id}/model-prompts`)
      .then((rows) => {
        if (!cancelled) setPrompts(rows);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, [chat.id]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const current = prompts && prompts.length > 0 ? prompts[Math.min(turn, prompts.length - 1)] : null;

  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="prompt-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="prompt-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="prompt-title">Full prompt</h2>
            <p>{chat.student_display_name} · {chat.lesson_title}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>Close</button>
        </header>
        <div className="prompt-body">
          {loadError ? <p className="help">{loadError}</p> : null}
          {prompts == null && !loadError ? <p className="help">Loading the prompt…</p> : null}
          {prompts && prompts.length === 0 ? <p className="help">No prompt was stored for this chat.</p> : null}
          {current ? (
            <>
              {prompts && prompts.length > 1 ? (
                <label className="prompt-turn">
                  Turn
                  <select value={current.seq} onChange={(event) => {
                    const seq = Number(event.target.value);
                    const index = (prompts ?? []).findIndex((row) => row.seq === seq);
                    if (index >= 0) setTurn(index);
                  }}>
                    {prompts.map((row, index) => (
                      <option key={row.id} value={row.seq}>
                        {index + 1} of {prompts.length} · {when(row.created_at)}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <p className="meta">
                {current.model || "Model"} · {when(current.created_at)}
              </p>
              <h3>System prompt</h3>
              <pre className="prompt-pre">{current.system_prompt}</pre>
              <h3>Messages sent to the model</h3>
              {current.messages.length === 0 ? <p className="help">No messages were attached to this call.</p> : null}
              <ol className="prompt-messages">
                {current.messages.map((message, index) => (
                  <li key={`${current.id}-${index}`}>
                    <strong>{messageRole(message)}</strong>
                    <pre className="prompt-pre">{messageBody(message)}</pre>
                  </li>
                ))}
              </ol>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SessionView({ session }: { session: SessionDetail }) {
  const current = session.lesson_plan.topics
    .flatMap((topic) => topic.checkpoints.map((checkpoint) => ({ topic, checkpoint })))
    .find((item) => item.checkpoint.id === session.current_checkpoint_id);
  return (
    <article className="transcript-view">
      <p className="eyebrow">{session.student.display_name}</p>
      <h2>{session.lesson_plan.title}</h2>
      <p className="meta">
        {session.status.replaceAll("_", " ")} · opened {when(session.created_at)}
        {current ? ` · now on ${current.topic.title}, ${current.checkpoint.kind}` : " · lesson finished"}
      </p>
      <h3>Scores</h3>
      {session.results.length === 0 ? <p className="help">No checkpoint scores stored yet.</p> : null}
      <ul className="score-list">
        {session.results.map((result) => (
          <li key={result.id}>
            <strong className={result.passed ? "pass" : "miss"}>
              {result.passed ? "Passed" : "Not yet"} · {result.score}/100
            </strong>
            <span className="quiet">
              {result.topic_title} · {result.checkpoint_kind} {result.checkpoint_position} · {when(result.created_at)}
              {result.hint_tier ? ` · hint ${result.hint_tier}` : ""}
            </span>
            <span>{result.feedback}</span>
            {result.misconception ? <span className="quiet">Misconception: {result.misconception}</span> : null}
          </li>
        ))}
      </ul>
      <h3>Transcript</h3>
      {session.messages.length === 0 ? <p className="help">No messages stored yet.</p> : null}
      <ol className="transcript-list">
        {session.messages.map((message) => (
          <li key={message.id} className={message.role}>
            <strong>{message.role === "user" ? session.student.display_name : "Tutor"}</strong>
            <span className="quiet">{when(message.created_at)}</span>
            <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap" }}>{message.content}</p>
          </li>
        ))}
      </ol>
    </article>
  );
}
