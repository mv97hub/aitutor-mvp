"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { BrandMark } from "@/components/BrandMark";
import { BlockStepper, ChoiceWidget } from "@/components/LessonBlocks";
import { api } from "@/lib/api";
import { KICKOFF } from "@/lib/kickoff";
import type {
  Board,
  CourseSummary,
  CurrentBlock,
  ProfileDefaults,
  QuestListItem,
  SessionSummary,
  Student,
  StoredMessage,
} from "@/lib/types";

const greeted = new Set<string>();

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
      return (
        <p key={key} className={`result-card ${passed ? "pass" : "miss"}`}>
          Beat result: {passed ? "Passed" : "Not yet"}
          {output.score != null ? ` · ${output.score}/100` : ""}
          {output.feedback ? <span>{output.feedback}</span> : null}
        </p>
      );
    }
    return null;
  });
  if (pieces.every((piece) => piece == null)) return null;
  return (
    <article className={`bubble ${message.role}`} aria-label={message.role === "user" ? studentName : "Tutor"}>
      {pieces}
    </article>
  );
}

function questScore(board: Board) {
  const earned = board.beats.reduce((sum, beat) => sum + (beat.latest_result?.score ?? 0), 0);
  return { earned, possible: board.beats.length * 100 };
}

function classDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

type ChildDraft = {
  name: string;
  age: string;
  reading_level: string;
  modality: string;
  interests: string;
  tutor_persona: string;
  tutor_lexicon: string;
  tutor_metaphors: string;
  tutor_sidekick: string;
  tutor_socratic_strictness: string;
  tutor_struggle_window: string;
  tutor_anti_spoiler: boolean;
  tutor_pacing: string;
};

function blankChild(): ChildDraft {
  return {
    name: "",
    age: "10",
    reading_level: "",
    modality: "",
    interests: "",
    tutor_persona: "",
    tutor_lexicon: "",
    tutor_metaphors: "",
    tutor_sidekick: "",
    tutor_socratic_strictness: "balanced",
    tutor_struggle_window: "minimum",
    tutor_anti_spoiler: true,
    tutor_pacing: "short-turns-one-question",
  };
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M8 13V3M8 3 3.5 7.5M8 3l4.5 4.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="2.1" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M8 1.8v1.7M8 12.5v1.7M1.8 8h1.7M12.5 8h1.7M3.4 3.4l1.2 1.2M11.4 11.4l1.2 1.2M12.6 3.4l-1.2 1.2M4.6 11.4l-1.2 1.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ChatPanel({
  sessionId,
  lessonStatus,
  initialMessages,
  studentName,
  block,
  quizLocked,
  onTurn,
}: {
  sessionId: string;
  lessonStatus: string;
  initialMessages: StoredMessage[];
  studentName: string;
  block: CurrentBlock | null;
  quizLocked: boolean;
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
  const draftRef = useRef<HTMLTextAreaElement>(null);
  const awaitingReply = useRef(false);
  const busy = status === "submitted" || status === "streaming";

  function growDraft(element: HTMLTextAreaElement) {
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 336)}px`;
  }

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
  }, [messages, status, block?.id]);

  useEffect(() => {
    if (busy) {
      awaitingReply.current = true;
      return;
    }
    if (!awaitingReply.current) return;
    awaitingReply.current = false;
    const field = draftRef.current;
    if (!field || field.disabled) return;
    const active = document.activeElement;
    if (active instanceof HTMLElement && active !== field && isTyping(active)) return;
    field.focus({ preventScroll: true });
  }, [busy]);

  return (
    <>
      <div className="ds-scroll" role="log" aria-live="polite" aria-relevant="additions">
        <div className="ds-column">
          {messages.map((message) => (
            <MessageView key={message.id} message={message} studentName={studentName} />
          ))}
          {block?.quiz && lessonStatus !== "completed" && !quizLocked ? (
            <ChoiceWidget
              key={block.id}
              quiz={block.quiz}
              busy={busy}
              onSubmit={(choice, explanation, transcript) => {
                clearError();
                void sendMessage({ text: transcript }, { body: { widget: { choice, explanation } } });
              }}
            />
          ) : null}
          <div ref={endRef} />
        </div>
      </div>
      {busy ? <p className="ds-typing">Tutor is writing…</p> : null}
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
              if (draftRef.current) draftRef.current.style.height = "auto";
              void sendMessage({ text });
            }}
          >
            Try again
          </button>
        </div>
      ) : null}
      <form
        className="ds-composer-seat"
        onSubmit={(event) => {
          event.preventDefault();
          const text = input.trim();
          if (!text || busy) return;
          clearError();
          setInput("");
          if (draftRef.current) draftRef.current.style.height = "auto";
          void sendMessage({ text });
        }}
      >
        <div className="ds-card">
          <textarea
            ref={draftRef}
            className="ds-draft"
            value={input}
            rows={1}
            onChange={(event) => {
              setInput(event.target.value);
              growDraft(event.target);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Message"
            aria-label="Your answer"
            disabled={busy}
            maxLength={2000}
          />
          <div className="ds-card-row">
            <button className="ds-send" type="submit" aria-label="Send" disabled={busy || input.trim().length === 0}>
              <SendIcon />
            </button>
          </div>
        </div>
      </form>
    </>
  );
}

function isTyping(element: HTMLElement) {
  if (element.isContentEditable) return true;
  return element.tagName === "INPUT" || element.tagName === "TEXTAREA" || element.tagName === "SELECT";
}

function childLabel(student: Student) {
  return student.age == null ? student.display_name : `${student.display_name} · age ${student.age}`;
}

export function KidSession({
  initialStudents,
  initialError,
}: {
  initialStudents: Student[];
  initialError: string | null;
}) {
  const [students, setStudents] = useState(initialStudents);
  const [learner, setLearner] = useState<Student | null>(null);
  const [notebooks, setNotebooks] = useState<SessionSummary[]>([]);
  const [making, setMaking] = useState(false);
  const [error, setError] = useState(initialError);
  const [board, setBoard] = useState<Board | null>(null);
  const [opening, setOpening] = useState(false);
  const [adding, setAdding] = useState(false);
  const [child, setChild] = useState<ChildDraft>(blankChild);
  const [savingChild, setSavingChild] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [quests, setQuests] = useState<QuestListItem[]>([]);
  const [courseId, setCourseId] = useState("");
  const [questId, setQuestId] = useState("");
  const settingsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!settingsOpen) return;
    function onPointer(event: PointerEvent) {
      if (!settingsRef.current?.contains(event.target as Node)) setSettingsOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setSettingsOpen(false);
    }
    window.addEventListener("pointerdown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, [settingsOpen]);

  useEffect(() => {
    if (!adding) return;
    const age = Number(child.age);
    if (!Number.isInteger(age) || age < 4 || age > 18) return;
    let cancelled = false;
    api<ProfileDefaults>(`/profile-defaults?age=${age}`)
      .then((profile) => {
        if (cancelled) return;
        setChild((current) => ({
          ...current,
          reading_level: profile.reading_level,
          modality: profile.modality,
          tutor_persona: profile.tutor_persona,
          tutor_lexicon: profile.tutor_lexicon,
          tutor_metaphors: profile.tutor_metaphors,
          tutor_sidekick: profile.tutor_sidekick,
          tutor_socratic_strictness: profile.tutor_socratic_strictness,
          tutor_struggle_window: profile.tutor_struggle_window,
          tutor_anti_spoiler: profile.tutor_anti_spoiler,
          tutor_pacing: profile.tutor_pacing,
        }));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [adding, child.age]);

  useEffect(() => {
    if (!making || !learner) return;
    let cancelled = false;
    api<CourseSummary[]>(`/courses?age_band=${encodeURIComponent(learner.age_band)}`)
      .then((rows) => {
        if (cancelled) return;
        setCourses(rows);
        setCourseId(rows[0]?.id ?? "");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load courses.");
      });
    return () => {
      cancelled = true;
    };
  }, [making, learner]);

  useEffect(() => {
    if (!courseId) {
      setQuests([]);
      setQuestId("");
      return;
    }
    let cancelled = false;
    api<QuestListItem[]>(`/courses/${courseId}/quests`)
      .then((rows) => {
        if (cancelled) return;
        setQuests(rows);
        setQuestId(rows[0]?.id ?? "");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load quests.");
      });
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  async function loadNotebooks(studentId: string) {
    const rows = await api<SessionSummary[]>(`/sessions?student_id=${studentId}`);
    setNotebooks(rows);
  }

  async function chooseStudent(student: Student) {
    setOpening(true);
    setError(null);
    setBoard(null);
    setMaking(false);
    setAdding(false);
    try {
      await loadNotebooks(student.id);
      setLearner(student);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open this learner's classes.");
    } finally {
      setOpening(false);
    }
  }

  async function startClass(event: FormEvent) {
    event.preventDefault();
    if (!learner || !questId) return;
    setOpening(true);
    setError(null);
    try {
      const next = await api<Board>("/sessions", {
        method: "POST",
        body: JSON.stringify({ student_id: learner.id, quest_id: questId, fresh: true }),
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

  async function createChild(event: FormEvent) {
    event.preventDefault();
    const name = child.name.trim();
    const age = Number(child.age);
    if (!name || !Number.isInteger(age) || age < 4 || age > 18) {
      setError("Enter a name and an age from 4 to 18.");
      return;
    }
    setSavingChild(true);
    setError(null);
    try {
      const student = await api<Student>("/students", {
        method: "POST",
        body: JSON.stringify({
          display_name: name,
          age,
          reading_level: child.reading_level,
          modality: child.modality,
          interests: child.interests.split(",").map((item) => item.trim()).filter(Boolean),
          tutor_persona: child.tutor_persona,
          tutor_lexicon: child.tutor_lexicon,
          tutor_metaphors: child.tutor_metaphors,
          tutor_sidekick: child.tutor_sidekick,
          tutor_socratic_strictness: child.tutor_socratic_strictness,
          tutor_struggle_window: child.tutor_struggle_window,
          tutor_anti_spoiler: child.tutor_anti_spoiler,
          tutor_pacing: child.tutor_pacing,
        }),
      });
      const nextStudents = await api<Student[]>("/students");
      setStudents(nextStudents);
      setChild(blankChild());
      await chooseStudent(student);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add that child.");
    } finally {
      setSavingChild(false);
    }
  }

  async function reloadRoster() {
    try {
      setStudents(await api<Student[]>("/students"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The tutor service is not reachable.");
    }
  }

  const selectedQuest = quests.find((item) => item.id === questId) ?? null;

  if (!learner) {
    return (
      <main className="ds-landing">
        <nav className="ds-landing-links" aria-label="Site">
          <Link href="/admin">Configure Lessons</Link>
          <Link href="/viewchats">View Chats / Debug</Link>
        </nav>
        <section className={`ds-landing-card${adding ? " is-wide" : ""}`}>
          <BrandMark />
          <h1>Who&apos;s learning today?</h1>
          <p>Choose a child, or add a new one. Then open a class.</p>
          <label>
            Child
            <select
              aria-label="Choose a child"
              value=""
              disabled={opening || students.length === 0}
              onChange={(event) => {
                const student = students.find((row) => row.id === event.target.value);
                if (student) void chooseStudent(student);
              }}
            >
              <option value="">{students.length === 0 ? "No children yet" : "Choose a child"}</option>
              {students.map((student) => (
                <option key={student.id} value={student.id}>{childLabel(student)}</option>
              ))}
            </select>
          </label>
          <div className="rail-actions">
            <button
              type="button"
              className="button ds-add-child"
              onClick={() => {
                setAdding((open) => !open);
                setError(null);
              }}
            >
              Add child
            </button>
          </div>
          {adding ? (
            <form className="child-form" onSubmit={(event) => void createChild(event)}>
              <h2>Student</h2>
              <label>
                Name
                <input
                  value={child.name}
                  onChange={(event) => setChild({ ...child, name: event.target.value })}
                  required
                  maxLength={120}
                  autoComplete="off"
                />
              </label>
              <label>
                Age
                <input
                  type="number"
                  inputMode="numeric"
                  min={4}
                  max={18}
                  required
                  value={child.age}
                  onChange={(event) => setChild({ ...child, age: event.target.value })}
                />
              </label>
              <label>
                Reading level
                <input
                  value={child.reading_level}
                  onChange={(event) => setChild({ ...child, reading_level: event.target.value })}
                />
              </label>
              <label>
                Modality
                <input
                  value={child.modality}
                  onChange={(event) => setChild({ ...child, modality: event.target.value })}
                />
              </label>
              <label>
                Interests
                <input
                  value={child.interests}
                  onChange={(event) => setChild({ ...child, interests: event.target.value })}
                  placeholder="cities, fairness"
                />
              </label>
              <div className="tutor-group">
                <h2>Tutor agent settings</h2>
                <label>
                  Persona
                  <input
                    value={child.tutor_persona}
                    onChange={(event) => setChild({ ...child, tutor_persona: event.target.value })}
                  />
                </label>
                <label>
                  Lexicon
                  <textarea
                    value={child.tutor_lexicon}
                    onChange={(event) => setChild({ ...child, tutor_lexicon: event.target.value })}
                  />
                </label>
                <label>
                  Metaphors
                  <textarea
                    value={child.tutor_metaphors}
                    onChange={(event) => setChild({ ...child, tutor_metaphors: event.target.value })}
                  />
                </label>
                <label>
                  Sidekick
                  <textarea
                    value={child.tutor_sidekick}
                    onChange={(event) => setChild({ ...child, tutor_sidekick: event.target.value })}
                  />
                </label>
                <label>
                  Socratic strictness
                  <input
                    value={child.tutor_socratic_strictness}
                    onChange={(event) => setChild({ ...child, tutor_socratic_strictness: event.target.value })}
                  />
                </label>
                <label>
                  Struggle window
                  <input
                    value={child.tutor_struggle_window}
                    onChange={(event) => setChild({ ...child, tutor_struggle_window: event.target.value })}
                  />
                </label>
                <label>
                  Pacing
                  <input
                    value={child.tutor_pacing}
                    onChange={(event) => setChild({ ...child, tutor_pacing: event.target.value })}
                  />
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={child.tutor_anti_spoiler}
                    onChange={(event) => setChild({ ...child, tutor_anti_spoiler: event.target.checked })}
                  />
                  Do not state the answer before the gate is passed
                </label>
              </div>
              <div className="rail-actions">
                <button className="button" type="submit" disabled={savingChild}>Save child</button>
                <button type="button" className="ghost" onClick={() => setAdding(false)}>Cancel</button>
              </div>
            </form>
          ) : null}
          {error ? (
            <div className="banner" role="alert">
              <p>{error}</p>
              <button type="button" className="ghost" onClick={() => void reloadRoster()}>Try again</button>
            </div>
          ) : null}
        </section>
        <p className="ds-placeholder">PLACEHOLDER PAGE</p>
      </main>
    );
  }

  const score = board && !making ? questScore(board) : null;
  const crumb = board && !making ? board.quest_title : making ? "New class" : "Classes";

  return (
    <main className="ds-shell">
      <aside className="ds-side">
        <div className="ds-logo">
          <BrandMark />
        </div>
        <p className="ds-learner">{learner.display_name}</p>
        <button
          type="button"
          className={`ds-new ${making ? "is-on" : ""}`}
          disabled={opening}
          onClick={() => setMaking(true)}
        >
          <span aria-hidden="true">+</span>
          New class
        </button>
        <ul className="ds-list" aria-label="This child's classes">
          {notebooks.length === 0 ? <li className="ds-quiet">No classes yet.</li> : null}
          {notebooks.map((session) => (
            <li key={session.id}>
              <button
                type="button"
                className={`ds-session ${board?.id === session.id && !making ? "is-on" : ""}`}
                disabled={opening}
                onClick={() => void openNotebook(session.id)}
              >
                <span className="ds-session-title">{session.quest_title}</span>
                <span className="ds-session-time">{classDate(session.updated_at)}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="ds-foot" ref={settingsRef}>
          {settingsOpen ? (
            <div className="ds-menu" role="menu">
              <p className="ds-menu-name">
                {learner.display_name}
                {learner.age == null ? "" : ` · age ${learner.age}`}
              </p>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setSettingsOpen(false);
                  setLearner(null);
                  setBoard(null);
                  setMaking(false);
                }}
              >
                Switch child
              </button>
              <Link role="menuitem" href="/admin" onClick={() => setSettingsOpen(false)}>
                Edit lessons
              </Link>
              {board && !making ? (
                <div className="ds-menu-goals">
                  <p>Enduring understanding</p>
                  <span>{board.enduring_understanding}</span>
                </div>
              ) : null}
            </div>
          ) : null}
          <button
            type="button"
            className="ds-settings"
            aria-expanded={settingsOpen}
            aria-haspopup="menu"
            onClick={() => setSettingsOpen((open) => !open)}
          >
            <GearIcon />
            Settings
          </button>
        </div>
      </aside>
      <section className="ds-stage">
        <header className="ds-header">
          <div className="ds-crumbs">
            <span className="ds-crumb">{learner.display_name}</span>
            <span className="ds-crumb-sep" aria-hidden="true">/</span>
            <span className="ds-crumb is-current">{crumb}</span>
          </div>
          {score ? (
            <span className="ds-score" aria-label={`Score so far ${score.earned} of ${score.possible}`}>
              {score.earned} / {score.possible}
            </span>
          ) : null}
          {board && !making ? (
            <p className="ds-objective">
              {board.status === "completed" ? "Finished" : board.current_block?.objective || "One step at a time"}
            </p>
          ) : null}
        </header>
        {board && !making ? (
          <>
            <div className="ds-steps">
              <BlockStepper steps={board.steps ?? []} />
            </div>
            <ChatPanel
              key={board.id}
              sessionId={board.id}
              lessonStatus={board.status}
              initialMessages={board.messages}
              studentName={board.student.display_name}
              block={board.current_block}
              quizLocked={
                board.beats.find((beat) => beat.id === board.current_beat_id)?.latest_result?.passed === true
              }
              onTurn={() => {
                void api<Board>(`/sessions/${board.id}/board`).then(setBoard).catch(() => undefined);
              }}
            />
          </>
        ) : making ? (
          <form className="ds-picker" onSubmit={(event) => void startClass(event)}>
            <h1>New class</h1>
            <p>Choose a course, then a quest. Other classes stay in the list.</p>
            <label>
              Course
              <select
                aria-label="Choose a course"
                value={courseId}
                onChange={(event) => setCourseId(event.target.value)}
              >
                {courses.length === 0 ? <option value="">No courses for this age</option> : null}
                {courses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Quest
              <select
                aria-label="Choose a quest"
                value={questId}
                disabled={quests.length === 0}
                onChange={(event) => setQuestId(event.target.value)}
              >
                {quests.length === 0 ? <option value="">No quests in this course</option> : null}
                {quests.map((quest) => (
                  <option key={quest.id} value={quest.id}>
                    {quest.code} · {quest.title}
                  </option>
                ))}
              </select>
            </label>
            {selectedQuest && selectedQuest.prerequisite_codes.length > 0 ? (
              <p>Comes after {selectedQuest.prerequisite_codes.join(", ")}. You can still start here.</p>
            ) : null}
            <div className="rail-actions">
              <button className="button" type="submit" disabled={opening || !questId}>Start class</button>
              <button type="button" className="ds-text" onClick={() => setMaking(false)}>Cancel</button>
            </div>
          </form>
        ) : (
          <div className="ds-empty">
            <p>Choose a class, or start a new one.</p>
          </div>
        )}
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
            <button type="button" className="ghost" onClick={() => void backToClasses()}>Try again</button>
          </div>
        ) : null}
      </section>
    </main>
  );
}
