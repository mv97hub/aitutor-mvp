"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type {
  AdminCheckpoint,
  AdminTopic,
  LessonPlan,
  LessonPlanSummary,
  SessionDetail,
  SessionSummary,
  Student,
} from "@/lib/types";

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

export function AdminApp({
  initialPlans,
  initialStudents,
  initialPlan,
  initialError,
}: {
  initialPlans: LessonPlanSummary[];
  initialStudents: Student[];
  initialPlan: LessonPlan | null;
  initialError: string | null;
}) {
  const [plans, setPlans] = useState(initialPlans);
  const [students] = useState(initialStudents);
  const [planId, setPlanId] = useState<string | null>(
    initialPlan?.id ?? initialPlans.find((plan) => plan.is_active)?.id ?? initialPlans[0]?.id ?? null,
  );
  const [plan, setPlan] = useState<LessonPlan | null>(initialPlan);
  const [studentFilter, setStudentFilter] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [view, setView] = useState<"plan" | "session">("plan");
  const [error, setError] = useState(initialError);

  async function refreshPlans(selectId?: string) {
    const next = await api<LessonPlanSummary[]>("/lesson-plans");
    setPlans(next);
    const id = selectId ?? planId ?? next.find((item) => item.is_active)?.id ?? next[0]?.id ?? null;
    setPlanId(id);
    if (id) setPlan(await api<LessonPlan>(`/lesson-plans/${id}`));
    else setPlan(null);
  }

  useEffect(() => {
    if (!planId) return;
    let cancelled = false;
    api<LessonPlan>(`/lesson-plans/${planId}`)
      .then((next) => {
        if (!cancelled) setPlan(next);
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, [planId]);

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

  function applyPlan(next: LessonPlan) {
    setPlan(next);
    setPlanId(next.id);
    setPlans((current) =>
      current.map((item) => {
        if (item.id === next.id) {
          return {
            ...item,
            title: next.title,
            is_active: next.is_active,
            topic_count: next.topics.length,
            updated_at: next.updated_at,
          };
        }
        return next.is_active ? { ...item, is_active: false } : item;
      }),
    );
  }

  async function createPlan() {
    setError(null);
    try {
      const created = await api<LessonPlan>("/lesson-plans", {
        method: "POST",
        body: JSON.stringify({
          title: "New lesson",
          preamble: "You are a warm, patient tutor. One step at a time.",
          is_active: false,
        }),
      });
      await refreshPlans(created.id);
      setView("plan");
    } catch (err) {
      setError(messageOf(err));
    }
  }

  return (
    <main className="desk">
      <aside className="side">
        <div className="side-head">
          <p className="eyebrow">Admin</p>
          <Link className="top-link" href="/">Kid session</Link>
        </div>
        <h1>Lesson desk</h1>
        <p className="lede">Edit the path the tutor follows, then open a session to read the transcript and scores.</p>
        <div className="row-actions" style={{ marginTop: 16 }}>
          <button type="button" className="button" onClick={() => void createPlan()}>New plan</button>
        </div>
        <div className="stack">
          {plans.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`choice ${view === "plan" && item.id === planId ? "is-on" : ""}`}
              onClick={() => {
                setPlanId(item.id);
                setView("plan");
              }}
            >
              <strong>{item.title}</strong>
              {item.is_active ? <span className="pill">Active</span> : null}
              <small style={{ display: "block" }}>{item.topic_count} topics</small>
            </button>
          ))}
        </div>
        <h2 style={{ marginTop: 28 }}>Sessions</h2>
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
          {sessions.length === 0 ? <p className="help">No sessions yet. Open a learner on the kid page.</p> : null}
          {sessions.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`session-choice ${view === "session" && item.id === sessionId ? "is-on" : ""}`}
              onClick={() => {
                setSessionId(item.id);
                setView("session");
              }}
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
        {view === "session" && session ? (
          <SessionView session={session} />
        ) : plan ? (
          <PlanEditor
            plan={plan}
            onChange={applyPlan}
            onError={setError}
            onDeleted={async () => {
              setPlanId(null);
              setPlan(null);
              await refreshPlans();
            }}
          />
        ) : planId ? (
          <article className="editor">
            <h2>Loading the plan…</h2>
          </article>
        ) : (
          <article className="editor">
            <h2>No lesson plan yet</h2>
            <p className="help">Create one, or start the API and run the seed script.</p>
          </article>
        )}
      </section>
    </main>
  );
}

function PlanEditor({
  plan,
  onChange,
  onError,
  onDeleted,
}: {
  plan: LessonPlan;
  onChange: (plan: LessonPlan) => void;
  onError: (message: string | null) => void;
  onDeleted: () => Promise<void>;
}) {
  const [title, setTitle] = useState(plan.title);
  const [preamble, setPreamble] = useState(plan.preamble);
  const [isActive, setIsActive] = useState(plan.is_active);
  const [note, setNote] = useState("");

  useEffect(() => {
    setTitle(plan.title);
    setPreamble(plan.preamble);
    setIsActive(plan.is_active);
  }, [plan]);

  async function savePlan() {
    onError(null);
    try {
      const next = await api<LessonPlan>(`/lesson-plans/${plan.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title, preamble, is_active: isActive }),
      });
      onChange(next);
      setNote("Plan saved. Students open whichever plan is active.");
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function removePlan() {
    if (!window.confirm(`Delete “${plan.title}”?`)) return;
    onError(null);
    try {
      await api(`/lesson-plans/${plan.id}`, { method: "DELETE" });
      await onDeleted();
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function addTopic() {
    onError(null);
    try {
      onChange(await api<LessonPlan>(`/lesson-plans/${plan.id}/topics`, {
        method: "POST",
        body: JSON.stringify({
          title: "New topic",
          learning_goal: "Say what the student should understand.",
          tutor_instructions: "How the tutor should handle this topic.",
        }),
      }));
    } catch (err) {
      onError(messageOf(err));
    }
  }

  return (
    <article className="editor">
      <div className="inline-title">
        <h2>{plan.title}</h2>
        <div className="row-actions">
          <button type="button" className="button" onClick={() => void savePlan()}>Save plan</button>
          <button type="button" className="danger" onClick={() => void removePlan()}>Delete</button>
        </div>
      </div>
      <p className="help">Checkpoint text is read the next time the tutor speaks on that step. Start a new kid session after a big edit.</p>
      {note ? <p className="note">{note}</p> : null}
      <label>
        Title
        <input value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label>
        Preamble
        <textarea value={preamble} onChange={(event) => setPreamble(event.target.value)} />
      </label>
      <label className="check">
        <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />
        Active lesson. Only one plan can be active.
      </label>
      {plan.topics.map((topic, index) => (
        <TopicEditor
          key={topic.id}
          topic={topic}
          first={index === 0}
          last={index === plan.topics.length - 1}
          onChange={onChange}
          onError={onError}
        />
      ))}
      <div className="row-actions" style={{ marginTop: 18 }}>
        <button type="button" className="ghost" onClick={() => void addTopic()}>Add topic</button>
      </div>
    </article>
  );
}

function TopicEditor({
  topic,
  first,
  last,
  onChange,
  onError,
}: {
  topic: AdminTopic;
  first: boolean;
  last: boolean;
  onChange: (plan: LessonPlan) => void;
  onError: (message: string | null) => void;
}) {
  const [title, setTitle] = useState(topic.title);
  const [goal, setGoal] = useState(topic.learning_goal);
  const [instructions, setInstructions] = useState(topic.tutor_instructions);

  useEffect(() => {
    setTitle(topic.title);
    setGoal(topic.learning_goal);
    setInstructions(topic.tutor_instructions);
  }, [topic]);

  async function save() {
    onError(null);
    try {
      onChange(await api<LessonPlan>(`/topics/${topic.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title, learning_goal: goal, tutor_instructions: instructions }),
      }));
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function move(direction: "up" | "down") {
    onError(null);
    try {
      onChange(await api<LessonPlan>(`/topics/${topic.id}/move`, {
        method: "POST",
        body: JSON.stringify({ direction }),
      }));
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function remove() {
    if (!window.confirm(`Delete topic “${topic.title}”?`)) return;
    onError(null);
    try {
      onChange(await api<LessonPlan>(`/topics/${topic.id}`, { method: "DELETE" }));
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function addCheckpoint() {
    onError(null);
    try {
      onChange(await api<LessonPlan>(`/topics/${topic.id}/checkpoints`, {
        method: "POST",
        body: JSON.stringify({
          kind: "teach",
          tutor_prompt: "Explain this idea, ask one short question, then wait.",
          rubric: "",
          pass_criteria: "",
        }),
      }));
    } catch (err) {
      onError(messageOf(err));
    }
  }

  return (
    <section className="topic-editor">
      <div className="inline-title">
        <h3>Topic {topic.position}</h3>
        <div className="row-actions">
          <button type="button" className="ghost" disabled={first} onClick={() => void move("up")}>Up</button>
          <button type="button" className="ghost" disabled={last} onClick={() => void move("down")}>Down</button>
          <button type="button" className="ghost" onClick={() => void save()}>Save topic</button>
          <button type="button" className="danger" onClick={() => void remove()}>Delete</button>
        </div>
      </div>
      <label>
        Title
        <input value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label>
        Learning goal
        <textarea value={goal} onChange={(event) => setGoal(event.target.value)} />
      </label>
      <label>
        Tutor instructions
        <textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} />
      </label>
      {topic.checkpoints.map((checkpoint, index) => (
        <CheckpointEditor
          key={checkpoint.id}
          checkpoint={checkpoint}
          first={index === 0}
          last={index === topic.checkpoints.length - 1}
          onChange={onChange}
          onError={onError}
        />
      ))}
      <div className="row-actions" style={{ marginTop: 10 }}>
        <button type="button" className="ghost" onClick={() => void addCheckpoint()}>Add checkpoint</button>
      </div>
    </section>
  );
}

function CheckpointEditor({
  checkpoint,
  first,
  last,
  onChange,
  onError,
}: {
  checkpoint: AdminCheckpoint;
  first: boolean;
  last: boolean;
  onChange: (plan: LessonPlan) => void;
  onError: (message: string | null) => void;
}) {
  const [kind, setKind] = useState(checkpoint.kind);
  const [prompt, setPrompt] = useState(checkpoint.tutor_prompt);
  const [rubric, setRubric] = useState(checkpoint.rubric ?? "");
  const [criteria, setCriteria] = useState(checkpoint.pass_criteria ?? "");
  const [note, setNote] = useState("");

  useEffect(() => {
    setKind(checkpoint.kind);
    setPrompt(checkpoint.tutor_prompt);
    setRubric(checkpoint.rubric ?? "");
    setCriteria(checkpoint.pass_criteria ?? "");
  }, [checkpoint]);

  async function save() {
    onError(null);
    setNote("");
    try {
      onChange(await api<LessonPlan>(`/checkpoints/${checkpoint.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          kind,
          tutor_prompt: prompt,
          rubric,
          pass_criteria: criteria,
        }),
      }));
      setNote("Saved. The tutor uses this the next time it teaches the step.");
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function move(direction: "up" | "down") {
    onError(null);
    try {
      onChange(await api<LessonPlan>(`/checkpoints/${checkpoint.id}/move`, {
        method: "POST",
        body: JSON.stringify({ direction }),
      }));
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function remove() {
    if (!window.confirm("Delete this checkpoint?")) return;
    onError(null);
    try {
      onChange(await api<LessonPlan>(`/checkpoints/${checkpoint.id}`, { method: "DELETE" }));
    } catch (err) {
      onError(messageOf(err));
    }
  }

  return (
    <section className="checkpoint-editor">
      <div className="inline-title">
        <h3>Checkpoint {checkpoint.position}</h3>
        <div className="row-actions">
          <button type="button" className="ghost" disabled={first} onClick={() => void move("up")}>Up</button>
          <button type="button" className="ghost" disabled={last} onClick={() => void move("down")}>Down</button>
          <button type="button" className="button" onClick={() => void save()} disabled={prompt.trim().length === 0}>Save</button>
          <button type="button" className="danger" onClick={() => void remove()}>Delete</button>
        </div>
      </div>
      {note ? <p className="note">{note}</p> : null}
      <label>
        Kind
        <select value={kind} onChange={(event) => setKind(event.target.value)}>
          <option value="teach">Teach</option>
          <option value="practice">Practice</option>
          <option value="quiz">Quiz</option>
        </select>
      </label>
      <label>
        Tutor prompt
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
      </label>
      <label>
        Rubric
        <textarea value={rubric} onChange={(event) => setRubric(event.target.value)} />
      </label>
      <label>
        Pass criteria
        <textarea value={criteria} onChange={(event) => setCriteria(event.target.value)} />
      </label>
    </section>
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
            </span>
            <span>{result.feedback}</span>
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
