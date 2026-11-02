"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { SessionDetail, SessionSummary, Student } from "@/lib/types";

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
            <button
              key={item.id}
              type="button"
              className={`session-choice ${item.id === sessionId ? "is-on" : ""}`}
              onClick={() => setSessionId(item.id)}
            >
              <strong>{item.student_display_name}</strong>
              <small style={{ display: "block" }}>
                {item.lesson_title} · {item.status.replace("_", " ")} · {when(item.updated_at)}
              </small>
              <small>{item.message_count} messages · {item.result_count} scores</small>
            </button>
          ))}
        </div>
      </aside>
      <section>
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
