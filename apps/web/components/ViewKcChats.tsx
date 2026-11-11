"use client";

import { useEffect, useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { SessionView, when } from "@/components/KcSessionView";
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
import type { Student } from "@/lib/types";

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
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
        <SessionView session={session} debug />
      ) : (
        <article className="transcript-view">
          <h2>Pick a chat</h2>
          <p className="help">The transcript opens here. This page does not edit components.</p>
        </article>
      )}
    </AdminFrame>
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
