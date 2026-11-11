"use client";

import { useEffect, useState } from "react";

import { SessionView, when } from "@/components/KcSessionView";
import { ParentFrame } from "@/components/parent/ParentFrame";
import { ParentSummaryPanel } from "@/components/parent/ParentSummaryPanel";
import { api } from "@/lib/api";
import type { ParentChatDetail, ParentChatSummary } from "@/lib/parent";

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function ParentChats({
  parentId,
  parentName,
  studentId,
  studentName,
  learners,
  initialSessions,
  initialError,
}: {
  parentId: string;
  parentName: string;
  studentId: string;
  studentName: string;
  learners: { id: string; display_name: string }[];
  initialSessions: ParentChatSummary[];
  initialError: string | null;
}) {
  const [sessionId, setSessionId] = useState<string | null>(initialSessions[0]?.id ?? null);
  const [session, setSession] = useState<ParentChatDetail | null>(null);
  const [error, setError] = useState(initialError);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setSession(null);
    api<ParentChatDetail>(`/parents/${parentId}/children/${studentId}/sessions/${sessionId}`)
      .then((next) => {
        if (!cancelled) {
          setSession(next);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, [parentId, studentId, sessionId]);

  return (
    <ParentFrame
      parentId={parentId}
      parentName={parentName}
      studentId={studentId}
      learners={learners}
      current="chats"
      sidebar={
        <>
          <p className="parent-side-title">{studentName}</p>
          <ul className="ds-list" aria-label="Chats">
            {initialSessions.length === 0 ? (
              <li className="ds-quiet">No chats yet. They show up here after {studentName} works with the tutor.</li>
            ) : null}
            {initialSessions.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={`ds-row ${item.id === sessionId ? "is-on" : ""}`}
                  aria-current={item.id === sessionId ? "true" : undefined}
                  onClick={() => setSessionId(item.id)}
                >
                  <strong>{item.kc_title}</strong>
                  <small>
                    {item.course_title} · {item.status.replace("_", " ")} · {when(item.updated_at)}
                  </small>
                  <small>{item.message_count} messages</small>
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
      {session ? (
        <>
          <ParentSummaryPanel
            key={session.id}
            parentId={parentId}
            studentId={studentId}
            sessionId={session.id}
            childName={studentName}
          />
          <SessionView session={session} heading="work" />
        </>
      ) : sessionId ? (
        <article className="transcript-view">
          <p className="help">Opening the chat…</p>
        </article>
      ) : (
        <article className="transcript-view">
          <header className="parent-work-head">
            <h1>No chats yet</h1>
            <p>When {studentName} works with the tutor, the conversation appears here.</p>
          </header>
        </article>
      )}
    </ParentFrame>
  );
}
