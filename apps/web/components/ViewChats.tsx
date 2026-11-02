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
    <main className="ds-shell ds-desk">
      <aside className="ds-side">
        <div className="ds-logo">
          <span className="ds-logo-name">View chats</span>
        </div>
        <label>
          Student
          <select value={studentFilter} onChange={(event) => setStudentFilter(event.target.value)}>
            <option value="">Everyone</option>
            {students.map((student) => (
              <option key={student.id} value={student.id}>{student.display_name}</option>
            ))}
          </select>
        </label>
        <ul className="ds-list" aria-label="Classes">
          {sessions.length === 0 ? <li className="ds-quiet">No classes yet. Open a learner on the kid page.</li> : null}
          {sessions.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`ds-row ${item.id === sessionId ? "is-on" : ""}`}
                onClick={() => setSessionId(item.id)}
              >
                <strong>{item.student_display_name}</strong>
                <small>
                  {item.lesson_title} · {item.status.replace("_", " ")} · {when(item.updated_at)}
                </small>
                <small>{item.message_count} messages · {item.result_count} scores</small>
              </button>
            </li>
          ))}
        </ul>
        <div className="ds-foot">
          <Link className="ds-settings" href="/admin">Edit lessons</Link>
          <Link className="ds-settings" href="/">Kid session</Link>
        </div>
      </aside>
      <section className="ds-work">
        {error ? (
          <div className="banner" role="alert" style={{ margin: 18 }}>
            <p>{error}</p>
          </div>
        ) : null}
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

function promptForMessage(session: SessionDetail): Map<string, ModelPrompt> {
  const linked = new Map<string, ModelPrompt>();
  const unlinked: ModelPrompt[] = [];
  for (const prompt of [...(session.prompts ?? [])].sort((left, right) => left.seq - right.seq)) {
    if (prompt.message_id) {
      const current = linked.get(prompt.message_id);
      if (!current || prompt.seq >= current.seq) linked.set(prompt.message_id, prompt);
    } else {
      unlinked.push(prompt);
    }
  }
  let spare = 0;
  for (const message of session.messages) {
    if (message.role !== "user" || linked.has(message.id)) continue;
    const prompt = unlinked[spare];
    if (!prompt) break;
    linked.set(message.id, prompt);
    spare += 1;
  }
  return linked;
}

function promptOnRow(session: SessionDetail): Map<string, ModelPrompt> {
  const linked = promptForMessage(session);
  const placed = new Map<string, ModelPrompt>();
  session.messages.forEach((message, index) => {
    if (message.role !== "user") return;
    const prompt = linked.get(message.id);
    if (!prompt) return;
    const next = session.messages[index + 1];
    placed.set(next && next.role === "assistant" ? next.id : message.id, prompt);
  });
  return placed;
}

function PromptDialog({
  prompt,
  subtitle,
  onClose,
}: {
  prompt: ModelPrompt;
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
        aria-labelledby="prompt-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="prompt-title">Prompt for this turn</h2>
            <p>{subtitle}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>Close</button>
        </header>
        <div className="prompt-body">
          <p className="meta">
            {prompt.model || "Model"} · {when(prompt.created_at)}
          </p>
          <h3>System prompt</h3>
          <pre className="prompt-pre">{prompt.system_prompt}</pre>
          <h3>Messages sent to the model</h3>
          {prompt.messages.length === 0 ? <p className="help">No messages were attached to this call.</p> : null}
          <ol className="prompt-messages">
            {prompt.messages.map((message, index) => (
              <li key={`${prompt.id}-${index}`}>
                <strong>{messageRole(message)}</strong>
                <pre className="prompt-pre">{messageBody(message)}</pre>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}

function SessionView({ session }: { session: SessionDetail }) {
  const [prompt, setPrompt] = useState<ModelPrompt | null>(null);
  const icons = promptOnRow(session);
  useEffect(() => {
    setPrompt(null);
  }, [session.id]);
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
        {session.messages.map((message) => {
          const turnPrompt = icons.get(message.id);
          return (
            <li key={message.id} className={message.role}>
              <div className="transcript-line">
                <div>
                  <strong>{message.role === "user" ? session.student.display_name : "Tutor"}</strong>
                  <span className="quiet">{when(message.created_at)}</span>
                  <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap" }}>{message.content}</p>
                </div>
                {turnPrompt ? (
                  <button
                    type="button"
                    className="prompt-icon"
                    aria-label="View the prompt for this turn"
                    onClick={() => setPrompt(turnPrompt)}
                  >
                    <PromptIcon />
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
      {prompt ? (
        <PromptDialog
          prompt={prompt}
          subtitle={`${session.student.display_name} · ${session.lesson_plan.title}`}
          onClose={() => setPrompt(null)}
        />
      ) : null}
    </article>
  );
}
