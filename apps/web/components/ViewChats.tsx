"use client";

import { useEffect, useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
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
    <AdminFrame
      current="chats"
      sidebar={
        <>
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
                  {item.quest_title} · {item.status.replace("_", " ")} · {when(item.updated_at)}
                </small>
                <small>{item.message_count} messages · {item.result_count} scores</small>
              </button>
            </li>
          ))}
        </ul>
        </>
      }
    >
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
    </AdminFrame>
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
            <h2 id="prompt-title">View full prompt to debug</h2>
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
          {prompt.messages.filter((message) => !isRequestNote(message)).length === 0 ? (
            <p className="help">No messages were attached to this call.</p>
          ) : null}
          <ol className="prompt-messages">
            {prompt.messages.filter((message) => !isRequestNote(message)).map((message, index) => (
              <li key={`${prompt.id}-${index}`}>
                <strong>{messageRole(message)}</strong>
                <pre className="prompt-pre">{messageBody(message)}</pre>
              </li>
            ))}
          </ol>
          {prompt.messages.filter(isRequestNote).map((message, index) => (
            <div key={`${prompt.id}-request-${index}`}>
              <h3>Also sent to the model</h3>
              <pre className="prompt-pre">{messageBody(message)}</pre>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function scoreCountLabel(count: number) {
  if (count === 0) return "None yet";
  if (count === 1) return "1 score";
  return `${count} scores`;
}

function SessionView({ session }: { session: SessionDetail }) {
  const [prompt, setPrompt] = useState<ModelPrompt | null>(null);
  const [scoresOpen, setScoresOpen] = useState(false);
  const icons = promptOnRow(session);
  useEffect(() => {
    setPrompt(null);
    setScoresOpen(false);
  }, [session.id]);
  const current = session.beats.find((beat) => beat.id === session.current_beat_id);
  const roleLabel: Record<string, string> = {
    engage: "engage",
    try: "try",
    name: "name",
    show: "show",
    teach_back: "teach-back",
  };
  return (
    <article className="transcript-view">
      <p className="eyebrow">{session.student.display_name}</p>
      <h2>{session.quest.title}</h2>
      <p className="meta">
        {session.quest.code} · {session.quest.course_title} · {session.status.replaceAll("_", " ")} · opened {when(session.created_at)}
        {current ? ` · now on ${roleLabel[current.role] ?? current.role}` : " · quest finished"}
      </p>
      <div className="score-fold">
        <h3>
          <button
            type="button"
            className="score-toggle"
            aria-expanded={scoresOpen}
            aria-controls="session-scores"
            onClick={() => setScoresOpen((open) => !open)}
          >
            <span>Scores</span>
            <span className="score-toggle-meta">
              {scoreCountLabel(session.results.length)}
              <span className="score-toggle-action">{scoresOpen ? "Hide" : "Show"}</span>
              <span className="score-chevron" aria-hidden="true">{scoresOpen ? "▴" : "▾"}</span>
            </span>
          </button>
        </h3>
        <div id="session-scores" hidden={!scoresOpen}>
          {session.results.length === 0 ? <p className="help">No beat scores stored yet.</p> : null}
          <ul className="score-list">
            {session.results.map((result) => (
              <li key={result.id}>
                <strong className={result.passed ? "pass" : "miss"}>
                  {result.passed ? "Passed" : "Not yet"} · {result.score}/100
                </strong>
                <span className="quiet">
                  {result.quest_title} · {roleLabel[result.beat_role] ?? result.beat_role} {result.beat_position} · {when(result.created_at)}
                  {result.hint_tier ? ` · hint ${result.hint_tier}` : ""}
                </span>
                <span>{result.feedback}</span>
                {result.misconception ? <span className="quiet">Misconception: {result.misconception}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
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
                    className="ds-debug"
                    onClick={() => setPrompt(turnPrompt)}
                  >
                    View full prompt to debug
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
          subtitle={`${session.student.display_name} · ${session.quest.title}`}
          onClose={() => setPrompt(null)}
        />
      ) : null}
    </article>
  );
}
