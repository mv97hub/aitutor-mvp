"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";
import { KICKOFF } from "@/lib/kickoff";
import type { Board, BoardCheckpoint, Student, StoredMessage } from "@/lib/types";

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

function kindLabel(kind: string) {
  if (kind === "teach") return "Teach";
  if (kind === "practice") return "Practice";
  if (kind === "quiz") return "Quiz";
  return kind;
}

function railState(board: Board, checkpointId: string) {
  const flat = board.topics.flatMap((topic) => topic.checkpoints);
  const index = flat.findIndex((item) => item.id === checkpointId);
  const currentIndex = flat.findIndex((item) => item.id === board.current_checkpoint_id);
  const checkpoint = flat[index];
  const result = checkpoint?.latest_result;
  if (!checkpoint) return "upcoming";
  if (board.current_checkpoint_id == null) {
    if (result?.passed) return "passed";
    if (result) return "failed";
    return "done";
  }
  if (checkpoint.id === board.current_checkpoint_id) return "current";
  if (currentIndex !== -1 && index > currentIndex) return "upcoming";
  if (result?.passed) return "passed";
  if (result) return "failed";
  return "done";
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

function CheckpointRow({ board, checkpoint }: { board: Board; checkpoint: BoardCheckpoint }) {
  const state = railState(board, checkpoint.id);
  const result = checkpoint.latest_result;
  return (
    <li className={`step is-${state}`}>
      <div className="step-kind">
        <span>{kindLabel(checkpoint.kind)}</span>
        <span>{state === "current" ? "Now" : state === "passed" ? "Passed" : state === "failed" ? "Not yet" : state === "done" ? "Done" : "Later"}</span>
      </div>
      {result ? (
        <p className={`score ${result.passed ? "pass" : "miss"}`}>
          {result.passed ? "Passed" : "Not yet"} · {result.score}/100
          <span>{result.feedback}</span>
        </p>
      ) : null}
    </li>
  );
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

export function KidSession({
  initialStudents,
  initialError,
}: {
  initialStudents: Student[];
  initialError: string | null;
}) {
  const [students, setStudents] = useState(initialStudents);
  const [error, setError] = useState(initialError);
  const [board, setBoard] = useState<Board | null>(null);
  const [opening, setOpening] = useState(false);

  async function openStudent(studentId: string, fresh: boolean) {
    setOpening(true);
    setError(null);
    try {
      const next = await api<Board>("/sessions", {
        method: "POST",
        body: JSON.stringify({ student_id: studentId, fresh }),
      });
      setBoard(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open the lesson.");
    } finally {
      setOpening(false);
    }
  }

  async function reloadStudents() {
    try {
      setStudents(await api<Student[]>("/students"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The tutor service is not reachable.");
    }
  }

  if (!board) {
    return (
      <main className="gate">
        <section className="gate-card">
          <div className="rail-head">
            <p className="eyebrow">Kid session</p>
            <Link className="top-link" href="/admin">Lesson desk</Link>
          </div>
          <h1>Who&apos;s learning today?</h1>
          <p className="lede">Pick a name. The tutor starts at the current step and stays there until you are ready.</p>
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
                  onClick={() => void openStudent(student.id, false)}
                >
                  <span className="mark" style={{ background: look.ink }}>{look.mark}</span>
                  <span>
                    <strong>{student.display_name}</strong>
                    <span className="hint">Open the active lesson</span>
                  </span>
                </button>
              );
            })}
          </div>
          {error ? (
            <div className="banner" role="alert">
              <p>{error}</p>
              <button type="button" className="ghost" onClick={() => void reloadStudents()}>Try again</button>
            </div>
          ) : null}
        </section>
      </main>
    );
  }

  const look = lookFor(board.student.slug);
  return (
    <main className="shell" style={{ ["--wash" as string]: look.wash, ["--ink-color" as string]: look.ink }}>
      <aside className="rail">
        <div className="rail-head">
          <p className="eyebrow">Today&apos;s path</p>
          <Link className="top-link" href="/admin">Lesson desk</Link>
        </div>
        <div className="who-pill">
          <span className="mark" style={{ background: look.ink }}>{look.mark}</span>
          <div>
            <strong>{board.student.display_name}</strong>
            <p className="lesson-name">{board.lesson_title}</p>
          </div>
        </div>
        {board.status === "completed" ? <p className="score pass">You finished this lesson.</p> : null}
        <ol className="path">
          {board.topics.map((topic) => (
            <li key={topic.id} className="topic-block">
              <h2>{topic.position}. {topic.title}</h2>
              <ul className="path">
                {topic.checkpoints.map((checkpoint) => (
                  <CheckpointRow key={checkpoint.id} board={board} checkpoint={checkpoint} />
                ))}
              </ul>
            </li>
          ))}
        </ol>
        <div className="rail-actions">
          <button type="button" className="ghost" onClick={() => setBoard(null)}>Switch learner</button>
          <button type="button" className="ghost" onClick={() => void openStudent(board.student.id, true)}>
            New session
          </button>
        </div>
      </aside>
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
    </main>
  );
}
