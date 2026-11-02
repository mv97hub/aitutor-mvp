"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type {
  AdminCheckpoint,
  AdminTopic,
  HintLadder,
  LessonPlan,
  LessonPlanSummary,
  QuizChoiceInput,
  QuizInput,
  RubricRowInput,
} from "@/lib/types";

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function AdminApp({
  initialPlans,
  initialPlan,
  initialError,
}: {
  initialPlans: LessonPlanSummary[];
  initialPlan: LessonPlan | null;
  initialError: string | null;
}) {
  const [plans, setPlans] = useState(initialPlans);
  const [planId, setPlanId] = useState<string | null>(
    initialPlan?.id ?? initialPlans.find((plan) => plan.is_active)?.id ?? initialPlans[0]?.id ?? null,
  );
  const [plan, setPlan] = useState<LessonPlan | null>(initialPlan);
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
    } catch (err) {
      setError(messageOf(err));
    }
  }

  return (
    <main className="desk">
      <aside className="side">
        <div className="side-head">
          <p className="eyebrow">Admin</p>
          <span className="top-links">
            <Link className="top-link" href="/viewchats">View chats</Link>
            <Link className="top-link" href="/">Kid session</Link>
          </span>
        </div>
        <h1>Lesson desk</h1>
        <p className="lede">Edit the blocks the tutor follows. Transcripts and scores live on View chats.</p>
        <div className="row-actions" style={{ marginTop: 16 }}>
          <button type="button" className="button" onClick={() => void createPlan()}>New plan</button>
        </div>
        <div className="stack">
          {plans.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`choice ${item.id === planId ? "is-on" : ""}`}
              onClick={() => setPlanId(item.id)}
            >
              <strong>{item.title}</strong>
              {item.is_active ? <span className="pill">Active</span> : null}
              <small style={{ display: "block" }}>{item.topic_count} topics</small>
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
        {plan ? (
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
  const [ageMin, setAgeMin] = useState(plan.age_min == null ? "" : String(plan.age_min));
  const [ageMax, setAgeMax] = useState(plan.age_max == null ? "" : String(plan.age_max));
  const [note, setNote] = useState("");

  useEffect(() => {
    setTitle(plan.title);
    setPreamble(plan.preamble);
    setIsActive(plan.is_active);
    setAgeMin(plan.age_min == null ? "" : String(plan.age_min));
    setAgeMax(plan.age_max == null ? "" : String(plan.age_max));
  }, [plan]);

  async function savePlan() {
    onError(null);
    try {
      const next = await api<LessonPlan>(`/lesson-plans/${plan.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title,
          preamble,
          is_active: isActive,
          age_min: ageMin.trim() === "" ? null : Number(ageMin),
          age_max: ageMax.trim() === "" ? null : Number(ageMax),
        }),
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
      <div className="age-row">
        <label>
          Youngest age
          <input value={ageMin} onChange={(event) => setAgeMin(event.target.value)} inputMode="numeric" />
        </label>
        <label>
          Oldest age
          <input value={ageMax} onChange={(event) => setAgeMax(event.target.value)} inputMode="numeric" />
        </label>
      </div>
      <p className="help">Leave oldest blank for no upper limit. A lesson with youngest 15 or more stays off the shelf for a 9–11 learner.</p>
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
          kind: "discovery",
          tutor_prompt: "Ask one short question and wait.",
          rubric: "",
          pass_criteria: "",
          objective: "What this block is for.",
          rubric_rows: [{ id: "r1", text: "The answer matches the goal.", weight: 100 }],
          hint_ladder: {
            nudge: "Look again at the question.",
            analogy: "Try a simpler picture.",
            scaffold: "Say the first step out loud.",
          },
          pass_score: 70,
          quiz: null,
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

const BLOCK_KINDS = [
  ["discovery", "Discovery"],
  ["quiz", "Quiz"],
  ["teach_back", "Teach the bot"],
  ["teach", "Teach"],
  ["practice", "Practice"],
] as const;

function emptyChoice(index: number): QuizChoiceInput {
  return { id: String.fromCharCode(97 + index), text: "", misconception: "" };
}

function quizFrom(checkpoint: AdminCheckpoint): QuizInput | null {
  const quiz = checkpoint.quiz;
  if (!quiz) return null;
  const answer = Array.isArray(quiz.answer) ? quiz.answer.map(String) : String(quiz.answer ?? "");
  return {
    type: quiz.type,
    prompt: quiz.prompt ?? "",
    choices: (quiz.choices ?? []).map((choice, index) => ({
      id: choice.id || emptyChoice(index).id,
      text: choice.text ?? "",
      misconception: choice.misconception ?? "",
    })),
    answer,
    explain: Boolean(quiz.explain),
    misconception: quiz.misconception ?? "",
  };
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
  const [objective, setObjective] = useState(checkpoint.objective ?? "");
  const [prompt, setPrompt] = useState(checkpoint.tutor_prompt);
  const [rubric, setRubric] = useState(checkpoint.rubric ?? "");
  const [criteria, setCriteria] = useState(checkpoint.pass_criteria ?? "");
  const [passScore, setPassScore] = useState(String(checkpoint.pass_score ?? 70));
  const [rows, setRows] = useState<RubricRowInput[]>(checkpoint.rubric_rows ?? []);
  const [hints, setHints] = useState<HintLadder>(checkpoint.hint_ladder ?? { nudge: "", analogy: "", scaffold: "" });
  const [widget, setWidget] = useState<"none" | QuizInput["type"]>(checkpoint.quiz?.type ?? "none");
  const [quiz, setQuiz] = useState<QuizInput | null>(quizFrom(checkpoint));
  const [note, setNote] = useState("");

  useEffect(() => {
    setKind(checkpoint.kind);
    setObjective(checkpoint.objective ?? "");
    setPrompt(checkpoint.tutor_prompt);
    setRubric(checkpoint.rubric ?? "");
    setCriteria(checkpoint.pass_criteria ?? "");
    setPassScore(String(checkpoint.pass_score ?? 70));
    setRows(checkpoint.rubric_rows ?? []);
    setHints(checkpoint.hint_ladder ?? { nudge: "", analogy: "", scaffold: "" });
    setWidget(checkpoint.quiz?.type ?? "none");
    setQuiz(quizFrom(checkpoint));
  }, [checkpoint]);

  function ensureQuiz(type: QuizInput["type"]) {
    setWidget(type);
    setQuiz((current) => {
      const choices = current?.choices?.length ? current.choices : [emptyChoice(0), emptyChoice(1)];
      const answer = type === "multi" || type === "order"
        ? (Array.isArray(current?.answer) ? current.answer : choices.map((choice) => choice.id))
        : (typeof current?.answer === "string" && current.answer ? current.answer : choices[0]?.id ?? "a");
      return {
        type,
        prompt: current?.prompt ?? "",
        choices,
        answer,
        explain: current?.explain ?? false,
        misconception: current?.misconception ?? "",
      };
    });
  }

  async function save() {
    onError(null);
    setNote("");
    const score = Number(passScore);
    try {
      onChange(await api<LessonPlan>(`/checkpoints/${checkpoint.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          kind,
          tutor_prompt: prompt,
          rubric,
          pass_criteria: criteria,
          objective,
          rubric_rows: rows.filter((row) => row.text.trim()),
          hint_ladder: hints,
          pass_score: Number.isFinite(score) ? score : 70,
          quiz: widget === "none" || !quiz ? null : { ...quiz, type: widget },
        }),
      }));
      setNote("Saved. The tutor uses this the next time it teaches the block.");
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
        <h3>Block {checkpoint.position}</h3>
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
          {BLOCK_KINDS.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </label>
      <label>
        Objective
        <input value={objective} onChange={(event) => setObjective(event.target.value)} />
      </label>
      <label>
        Tutor prompt
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
      </label>
      <label>
        Pass score
        <input value={passScore} onChange={(event) => setPassScore(event.target.value)} inputMode="numeric" />
      </label>
      <div className="rubric-editor">
        <p className="eyebrow">Rubric rows</p>
        {rows.map((row, index) => (
          <div key={`${row.id}-${index}`} className="rubric-edit-row">
            <input
              value={row.text}
              aria-label={`Rubric row ${index + 1}`}
              onChange={(event) => setRows(rows.map((item, itemIndex) => itemIndex === index ? { ...item, text: event.target.value } : item))}
            />
            <input
              value={String(row.weight)}
              aria-label={`Weight ${index + 1}`}
              inputMode="numeric"
              onChange={(event) => setRows(rows.map((item, itemIndex) => itemIndex === index ? { ...item, weight: Number(event.target.value) || 0 } : item))}
            />
            <button type="button" className="ghost" onClick={() => setRows(rows.filter((_, itemIndex) => itemIndex !== index))}>Remove</button>
          </div>
        ))}
        <button
          type="button"
          className="ghost"
          onClick={() => setRows([...rows, { id: `r${rows.length + 1}`, text: "", weight: 1 }])}
        >
          Add row
        </button>
      </div>
      <div className="hint-editor">
        <p className="eyebrow">Hint ladder</p>
        {(["nudge", "analogy", "scaffold"] as const).map((tier) => (
          <label key={tier}>
            {tier}
            <input value={hints[tier] ?? ""} onChange={(event) => setHints({ ...hints, [tier]: event.target.value })} />
          </label>
        ))}
      </div>
      <label>
        Widget
        <select
          value={widget}
          onChange={(event) => {
            const next = event.target.value as "none" | QuizInput["type"];
            if (next === "none") {
              setWidget("none");
              setQuiz(null);
              return;
            }
            ensureQuiz(next);
          }}
        >
          <option value="none">None</option>
          <option value="single">Single answer</option>
          <option value="multi">Multi-select</option>
          <option value="flaw">Spot the flaw</option>
          <option value="order">Ordering</option>
        </select>
      </label>
      {quiz && widget !== "none" ? (
        <div className="quiz-editor">
          <label>
            Widget prompt
            <textarea value={quiz.prompt} onChange={(event) => setQuiz({ ...quiz, prompt: event.target.value })} />
          </label>
          {quiz.choices.map((choice, index) => (
            <div key={`${choice.id}-${index}`} className="choice-edit">
              <input
                value={choice.id}
                aria-label={`Choice id ${index + 1}`}
                onChange={(event) => {
                  const choices = quiz.choices.map((item, itemIndex) => itemIndex === index ? { ...item, id: event.target.value } : item);
                  setQuiz({ ...quiz, choices });
                }}
              />
              <input
                value={choice.text}
                aria-label={`Choice text ${index + 1}`}
                onChange={(event) => {
                  const choices = quiz.choices.map((item, itemIndex) => itemIndex === index ? { ...item, text: event.target.value } : item);
                  setQuiz({ ...quiz, choices });
                }}
              />
              <input
                value={choice.misconception}
                aria-label={`Misconception ${index + 1}`}
                placeholder="Misconception if they pick this"
                onChange={(event) => {
                  const choices = quiz.choices.map((item, itemIndex) => itemIndex === index ? { ...item, misconception: event.target.value } : item);
                  setQuiz({ ...quiz, choices });
                }}
              />
            </div>
          ))}
          <button
            type="button"
            className="ghost"
            onClick={() => setQuiz({ ...quiz, choices: [...quiz.choices, emptyChoice(quiz.choices.length)] })}
          >
            Add choice
          </button>
          {widget === "single" || widget === "flaw" ? (
            <label>
              Correct choice
              <select
                value={typeof quiz.answer === "string" ? quiz.answer : ""}
                onChange={(event) => setQuiz({ ...quiz, answer: event.target.value })}
              >
                {quiz.choices.map((choice) => (
                  <option key={choice.id} value={choice.id}>{choice.id}: {choice.text || "Untitled"}</option>
                ))}
              </select>
            </label>
          ) : null}
          {widget === "multi" ? (
            <div>
              <p className="eyebrow">Correct choices</p>
              {quiz.choices.map((choice) => {
                const selected = Array.isArray(quiz.answer) ? quiz.answer : [];
                const on = selected.includes(choice.id);
                return (
                  <label key={choice.id} className="check">
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => {
                        const next = on ? selected.filter((id) => id !== choice.id) : [...selected, choice.id];
                        setQuiz({ ...quiz, answer: next });
                      }}
                    />
                    {choice.text || choice.id}
                  </label>
                );
              })}
            </div>
          ) : null}
          {widget === "order" ? (
            <div>
              <p className="eyebrow">Correct order</p>
              {(Array.isArray(quiz.answer) ? quiz.answer : quiz.choices.map((choice) => choice.id)).map((id, index, answer) => (
                <div key={`${id}-${index}`} className="row-actions">
                  <span>{quiz.choices.find((choice) => choice.id === id)?.text || id}</span>
                  <button
                    type="button"
                    className="ghost"
                    disabled={index === 0}
                    onClick={() => {
                      const next = [...answer];
                      [next[index - 1], next[index]] = [next[index], next[index - 1]];
                      setQuiz({ ...quiz, answer: next });
                    }}
                  >
                    Up
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={index === answer.length - 1}
                    onClick={() => {
                      const next = [...answer];
                      [next[index + 1], next[index]] = [next[index], next[index + 1]];
                      setQuiz({ ...quiz, answer: next });
                    }}
                  >
                    Down
                  </button>
                </div>
              ))}
            </div>
          ) : null}
          <label className="check">
            <input
              type="checkbox"
              checked={quiz.explain}
              onChange={(event) => setQuiz({ ...quiz, explain: event.target.checked })}
            />
            Ask for a short written explanation
          </label>
          <label>
            Misconception if the set or the order is wrong
            <input
              value={quiz.misconception}
              onChange={(event) => setQuiz({ ...quiz, misconception: event.target.value })}
            />
          </label>
        </div>
      ) : null}
      <label>
        Notes
        <textarea value={rubric} onChange={(event) => setRubric(event.target.value)} />
      </label>
      <label>
        Pass criteria
        <textarea value={criteria} onChange={(event) => setCriteria(event.target.value)} />
      </label>
    </section>
  );
}
