"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";
import { KICKOFF } from "@/lib/kickoff";
import type { Board, LessonPlanSummary, SessionSummary, Student, StoredMessage } from "@/lib/types";

const LOOKS: Record<string, { ink: string; wash: string; mark: string }> = {
  "iron-man": { ink: "#7c2d12", wash: "#f6d7a8", mark: "IM" },
  storm: { ink: "#3d3470", wash: "#ddd6f3", mark: "ST" },
  "spider-man": { ink: "#8f1d1d", wash: "#f6cfc8", mark: "SM" },
  wolverine: { ink: "#8a5b00", wash: "#f6e3a8", mark: "W" },
};

const greeted = new Set<string>();

function lookFor(slug: string) {
  return LOOKS[slug] ?? { ink: "#0f6e6b", wash: "#e7f3f2", mark: slug.slice(0, 1).toUpperCase() };
}

function toUiMessages(messages: StoredMessage[]): UIMessage[] {
  return messages.map((message) => ({
    id: message.client_id || message.id,
    role: message.role,
    parts: [{ type: "text", text: message.content }],
  }));
}

type LoosePart = {
  type: string;
  text?: string;
  state?: string;
  output?: unknown;
  toolCallId?: string;
};

function readOutput(output: unknown) {
  if (!output || typeof output !== "object") return null;
  const record = output as Record<string, unknown>;
  return {
    ok: typeof record.ok === "boolean" ? record.ok : undefined,
    passed: typeof record.passed === "boolean" ? record.passed : undefined,
    score: typeof record.score === "number" ? record.score : undefined,
    feedback: typeof record.feedback === "string" ? record.feedback : undefined,
    kind: typeof record.kind === "string" ? record.kind : undefined,
    reason: typeof record.reason === "string" ? record.reason : undefined,
  };
}

function MessageView({ message, studentName }: { message: UIMessage; studentName: string }) {
  const parts = message.parts as LoosePart[];
  const pieces = parts.map((part, index) => {
    const key = part.toolCallId || `${message.id}-${index}`;
    if (part.type === "text" && part.text?.trim()) {
      return <p key={key}>{part.text}</p>;
    }
    if (part.type === "tool-record_checkpoint_result") {
      if (part.state === "output-error") {
        return <p key={key} className="result-card miss">That score did not save.</p>;
      }
      const output = readOutput(part.output);
      if (!output || part.state !== "output-available") {
        return <p key={key} className="result-card">Checking that answer…</p>;
      }
      if (output.ok === false) {
        return <p key={key} className="result-card miss">{output.reason}</p>;
      }
      const passed = output.passed === true;
      const label = output.kind === "quiz" ? "Quiz result" : "Practice result";
      return (
        <p key={key} className={`result-card ${passed ? "pass" : "miss"}`}>
          {label}: {passed ? "Passed" : "Not yet"}
          {output.score != null ? ` · ${output.score}/100` : ""}
          {output.feedback ? <span>{output.feedback}</span> : null}
        </p>
      );
    }
    if (part.type === "tool-advance_checkpoint" && part.state === "output-available") {
      const output = readOutput(part.output);
      if (output?.ok === false && output.reason) {
        return <p key={key} className="advance-note">{output.reason}</p>;
      }
    }
    return null;
  });
  if (pieces.every((piece) => piece == null)) return null;
  return (
    <article className={`bubble ${message.role}`}>
      <span className="who">{message.role === "user" ? studentName : "Tutor"}</span>
      {pieces}
    </article>
  );
}

function lessonScore(board: Board) {
  const scored = board.topics
    .flatMap((topic) => topic.checkpoints)
    .filter((checkpoint) => checkpoint.kind === "practice" || checkpoint.kind === "quiz");
  const earned = scored.reduce((sum, checkpoint) => sum + (checkpoint.latest_result?.score ?? 0), 0);
  return { earned, possible: scored.length * 100 };
}

function classDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function ChatPanel({
  sessionId,
  lessonStatus,
  initialMessages,
  studentName,
  wash,
  onTurn,
}: {
  sessionId: string;
  lessonStatus: string;
  initialMessages: StoredMessage[];
  studentName: string;
  wash: string;
  onTurn: () => void;
}) {
  const [seed] = useState(initialMessages);
  const transport = useMemo(
    () => new DefaultChatTransport({ api: "/api/chat", body: { sessionId } }),
    [sessionId],
  );
  const { messages, sendMessage, status, error, clearError } = useChat({
    id: sessionId,
    messages: toUiMessages(seed),
    transport,
    onFinish: () => onTurn(),
  });
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const busy = status === "submitted" || status === "streaming";

  useEffect(() => {
    if (seed.length > 0 || lessonStatus === "completed") return;
    let cancelled = false;
    const handle = window.setTimeout(() => {
      if (cancelled || greeted.has(sessionId)) return;
      greeted.add(sessionId);
      void sendMessage({ text: KICKOFF });
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [lessonStatus, seed.length, sendMessage, sessionId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, status]);

  return (
    <>
      <div className="transcript" role="log" aria-live="polite" aria-relevant="additions">
        {messages.map((message) => (
          <MessageView key={message.id} message={message} studentName={studentName} />
        ))}
        <div ref={endRef} />
      </div>
      {busy ? <p className="typing">Tutor is writing…</p> : null}
      {error ? (
        <div className="banner" role="alert">
          <p>{error.message}</p>
          <button
            type="button"
            className="ghost"
            onClick={() => {
              clearError();
              const text = input.trim() || KICKOFF;
              setInput("");
              void sendMessage({ text });
            }}
          >
            Try again
          </button>
        </div>
      ) : null}
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          const text = input.trim();
          if (!text || busy) return;
          clearError();
          setInput("");
          void sendMessage({ text });
        }}
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Type your answer"
          aria-label="Your answer"
          disabled={busy}
          maxLength={2000}
          style={{ background: wash }}
        />
        <button className="button" type="submit" disabled={busy || input.trim().length === 0}>
          Send
        </button>
      </form>
    </>
  );
}

function startablePlans(plans: LessonPlanSummary[]): LessonPlanSummary[] {
  return plans.filter((plan) => plan.topic_count > 0);
}

export function KidSession({
  initialStudents,
  initialPlans,
  initialError,
}: {
  initialStudents: Student[];
  initialPlans: LessonPlanSummary[];
  initialError: string | null;
}) {
  const [students, setStudents] = useState(initialStudents);
  const [plans, setPlans] = useState(initialPlans);
  const [learner, setLearner] = useState<Student | null>(null);
  const [notebooks, setNotebooks] = useState<SessionSummary[]>([]);
  const [making, setMaking] = useState(false);
  const [error, setError] = useState(initialError);
  const [board, setBoard] = useState<Board | null>(null);
  const [opening, setOpening] = useState(false);
  const choices = startablePlans(plans);

  async function loadNotebooks(studentId: string) {
    const rows = await api<SessionSummary[]>(`/sessions?student_id=${studentId}`);
    setNotebooks(rows);
  }

  async function chooseStudent(student: Student) {
    setOpening(true);
    setError(null);
    setBoard(null);
    setMaking(false);
    try {
      await loadNotebooks(student.id);
      setLearner(student);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open this learner's classes.");
    } finally {
      setOpening(false);
    }
  }

  async function startClass(lessonPlanId: string) {
    if (!learner) return;
    setOpening(true);
    setError(null);
    try {
      const next = await api<Board>("/sessions", {
        method: "POST",
        body: JSON.stringify({ student_id: learner.id, lesson_plan_id: lessonPlanId, fresh: true }),
      });
      setBoard(next);
      setMaking(false);
      await loadNotebooks(learner.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start that class.");
    } finally {
      setOpening(false);
    }
  }

  async function openNotebook(sessionId: string) {
    setOpening(true);
    setError(null);
    try {
      const next = await api<Board>(`/sessions/${sessionId}/board`);
      setBoard(next);
      setMaking(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open that class.");
    } finally {
      setOpening(false);
    }
  }

  async function backToClasses() {
    setBoard(null);
    setMaking(false);
    if (!learner) return;
    try {
      await loadNotebooks(learner.id);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load classes.");
    }
  }

  async function reloadRoster() {
    try {
      const [nextStudents, nextPlans] = await Promise.all([
        api<Student[]>("/students"),
        api<LessonPlanSummary[]>("/lesson-plans"),
      ]);
      setStudents(nextStudents);
      setPlans(nextPlans);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The tutor service is not reachable.");
    }
  }

  if (!learner) {
    return (
      <main className="gate">
        <section className="gate-card">
          <div className="rail-head">
            <p className="eyebrow">Kid session</p>
            <Link className="top-link" href="/admin">Edit lessons</Link>
          </div>
          <h1>Who&apos;s learning today?</h1>
          <p className="lede">Pick a name. Then choose a class, or start a new one.</p>
          {students.length === 0 ? <p className="lede">Loading the class list…</p> : null}
          <div className="name-grid">
            {students.map((student) => {
              const look = lookFor(student.slug);
              return (
                <button
                  key={student.id}
                  type="button"
                  className="name-card"
                  disabled={opening}
                  style={{ ["--wash" as string]: look.wash, ["--ink-color" as string]: look.ink }}
                  onClick={() => void chooseStudent(student)}
                >
                  <span className="mark" style={{ background: look.ink }}>{look.mark}</span>
                  <span>
                    <strong>{student.display_name}</strong>
                    <span className="hint">Open their classes</span>
                  </span>
                </button>
              );
            })}
          </div>
          {error ? (
            <div className="banner" role="alert">
              <p>{error}</p>
              <button type="button" className="ghost" onClick={() => void reloadRoster()}>Try again</button>
            </div>
          ) : null}
        </section>
      </main>
    );
  }

  const look = lookFor(learner.slug);
  const score = board ? lessonScore(board) : null;

  return (
    <main
      className={`shell ${board ? "is-class" : "is-shelf"}`}
      style={{ ["--wash" as string]: look.wash, ["--ink-color" as string]: look.ink }}
    >
      <aside className={`rail ${board ? "lesson-desk" : ""}`}>
        <div className="desk-top">
          <div className="rail-head">
            <p className="eyebrow">{board ? "Lesson desk" : "Learner"}</p>
            <Link className="top-link" href="/admin">Edit lessons</Link>
          </div>
          {score ? (
            <div className="desk-score" aria-label={`Score so far ${score.earned} of ${score.possible}`}>
              <p className="eyebrow">Score so far</p>
              <p className="desk-score-value">{score.earned}</p>
              <p className="quiet">of {score.possible} in {board?.lesson_title}</p>
            </div>
          ) : (
            <p className="lede">Classes are on the right. Start a new one, or open a notebook you already began.</p>
          )}
          <div className="who-pill">
            <span className="mark" style={{ background: look.ink }}>{look.mark}</span>
            <div>
              <strong>{learner.display_name}</strong>
              <p className="lesson-name">{board ? board.lesson_title : "No class open"}</p>
            </div>
          </div>
        </div>
        {board ? (
          <div className="desk-goals">
            <p className="eyebrow">Lesson goals</p>
            <ul className="goal-list">
              {board.topics.map((topic) => (
                <li key={topic.id}>
                  <strong>{topic.position}. {topic.title}</strong>
                  <span>{topic.learning_goal}</span>
                </li>
              ))}
            </ul>
            <div className="rail-actions">
              <button type="button" className="ghost" onClick={() => void backToClasses()}>Classes</button>
              <button type="button" className="ghost" onClick={() => { setLearner(null); setBoard(null); setMaking(false); }}>
                Switch learner
              </button>
            </div>
          </div>
        ) : (
          <div className="rail-actions">
            <button type="button" className="ghost" onClick={() => { setLearner(null); setMaking(false); }}>
              Switch learner
            </button>
          </div>
        )}
      </aside>
      {board ? (
        <section className="stage">
          <div className="stage-head">
            <h1>{board.lesson_title}</h1>
            <p className="quiet">{board.status === "completed" ? "Finished" : "One step at a time"}</p>
          </div>
          <ChatPanel
            key={board.id}
            sessionId={board.id}
            lessonStatus={board.status}
            initialMessages={board.messages}
            studentName={board.student.display_name}
            wash={look.wash}
            onTurn={() => {
              void api<Board>(`/sessions/${board.id}/board`).then(setBoard).catch(() => undefined);
            }}
          />
        </section>
      ) : (
        <section className="stage shelf">
          <div className="stage-head">
            <h1>Classes</h1>
            <p className="quiet">{learner.display_name}</p>
          </div>
          {making ? (
            <div className="lesson-pick">
              <p className="eyebrow">New class</p>
              <p className="lede">Choose the lesson for this notebook.</p>
              <div className="lesson-row" role="group" aria-label="Choose a lesson">
                {choices.map((plan) => (
                  <button
                    key={plan.id}
                    type="button"
                    className="choice lesson-choice"
                    disabled={opening}
                    onClick={() => void startClass(plan.id)}
                  >
                    {plan.title}
                  </button>
                ))}
              </div>
              {choices.length === 0 ? <p className="lede">No lessons yet.</p> : null}
              <div className="rail-actions">
                <button type="button" className="ghost" onClick={() => setMaking(false)}>Cancel</button>
              </div>
            </div>
          ) : (
            <div className="notebook-grid">
              <button
                type="button"
                className="notebook notebook-new"
                aria-label="New class"
                disabled={opening}
                onClick={() => setMaking(true)}
              >
                <span className="plus" aria-hidden="true">+</span>
                <span>New class</span>
              </button>
              {notebooks.map((session) => (
                <button
                  key={session.id}
                  type="button"
                  className="notebook"
                  disabled={opening}
                  onClick={() => void openNotebook(session.id)}
                >
                  <strong>{session.lesson_title}</strong>
                  <span className="notebook-meta">{classDate(session.updated_at)}</span>
                  <span className="notebook-meta">{session.status === "completed" ? "Finished" : "In progress"}</span>
                </button>
              ))}
            </div>
          )}
          {error ? (
            <div className="banner" role="alert">
              <p>{error}</p>
              <button type="button" className="ghost" onClick={() => void backToClasses()}>Try again</button>
            </div>
          ) : null}
        </section>
      )}
    </main>
  );
}
