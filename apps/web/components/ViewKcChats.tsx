"use client";

import { useEffect, useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { api } from "@/lib/api";
import {
  eventsForChat,
  filterChatsWithUnreviewed,
  safetyCategoryLabel,
  showSafetyTag,
  unreviewedChatTotal,
  unreviewedEvents,
  type SafetyEvent,
  type SafetyEventPage,
} from "@/lib/ai-safety";
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
  const [unreviewedOnly, setUnreviewedOnly] = useState(false);
  const [sessions, setSessions] = useState<KcChatSummary[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<KcChatDetail | null>(null);
  const [safetyChat, setSafetyChat] = useState<KcChatSummary | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
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
  }, [studentFilter, sessionId, refreshKey]);

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
    <AdminFrame
      current="kc-chats"
      sidebar={
        <>
          <label>
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
          <p className="safety-list-head" aria-live="polite">
            {unreviewedChatTotal(sessions)} unreviewed
          </p>
          <label className="safety-filter">
            <input
              type="checkbox"
              checked={unreviewedOnly}
              onChange={(event) => setUnreviewedOnly(event.target.checked)}
            />
            Chats with unreviewed safety
          </label>
          <ul className="ds-list" aria-label="KC chats">
            {sessions.length === 0 ? <li className="ds-quiet">No chats yet. Open a learner on KC Tutor.</li> : null}
            {sessions.length > 0 && filterChatsWithUnreviewed(sessions, unreviewedOnly).length === 0 ? (
              <li className="ds-quiet">No chats with unreviewed safety.</li>
            ) : null}
            {filterChatsWithUnreviewed(sessions, unreviewedOnly).map((item) => (
              <li key={item.id} className="ds-chat-item">
                <button
                  type="button"
                  className={`ds-row ${item.id === sessionId ? "is-on" : ""}`}
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
                {showSafetyTag(item.safety_event_count ?? 0) ? (
                  <button type="button" className="safety-tag" onClick={() => setSafetyChat(item)}>
                    Safety {item.safety_event_count}
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
          {safetyChat ? (
            <SafetyDialog
              chat={safetyChat}
              onClose={() => setSafetyChat(null)}
              onReviewed={() => setRefreshKey((value) => value + 1)}
            />
          ) : null}
        </>
      }
    >
      {error ? (
        <div className="banner" role="alert" style={{ margin: 18 }}>
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

function SafetyDialog({
  chat,
  onClose,
  onReviewed,
}: {
  chat: KcChatSummary;
  onClose: () => void;
  onReviewed: () => void;
}) {
  const [events, setEvents] = useState<SafetyEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const rows = eventsForChat(events, chat.id);
  const open = unreviewedEvents(rows);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    api<SafetyEventPage>(`/safety-events?session_id=${chat.id}&limit=100`)
      .then((page) => {
        if (!cancelled) setEvents(page.events);
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, [chat.id]);

  async function markReviewed(eventId: string) {
    setPendingId(eventId);
    setError(null);
    try {
      const updated = await api<SafetyEvent>(`/safety-events/${eventId}/review`, {
        method: "POST",
        body: JSON.stringify({ reviewed_by: "admin" }),
      });
      setEvents((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      onReviewed();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="prompt-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="kc-safety-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="kc-safety-title">Safety</h2>
            <p>
              {chat.student_display_name} · {chat.kc_title} · {open.length} unreviewed
            </p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="prompt-body">
          {error ? (
            <div className="banner" role="alert">
              <p>{error}</p>
            </div>
          ) : null}
          {rows.length === 0 ? <p className="help">No safety events for this chat.</p> : null}
          <ul className="safety-event-list">
            {rows.map((event) => (
              <li key={event.id}>
                <p className="meta">
                  {when(event.created_at)} · {safetyCategoryLabel(event.category)}
                </p>
                <p>
                  {event.course_title} · {event.component_title}
                </p>
                <p>
                  <strong>Child</strong> {event.child_message || "—"}
                </p>
                <p>
                  <strong>Tutor</strong> {event.tutor_reply || "—"}
                </p>
                {event.reviewed_at ? (
                  <p className="help">Reviewed{event.reviewed_by ? ` by ${event.reviewed_by}` : ""}</p>
                ) : (
                  <button
                    type="button"
                    className="button"
                    disabled={pendingId === event.id}
                    onClick={() => void markReviewed(event.id)}
                  >
                    Mark reviewed
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
