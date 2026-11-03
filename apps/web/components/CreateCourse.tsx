"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { BrandMark } from "@/components/BrandMark";
import { api } from "@/lib/api";
import {
  DEPTHS,
  closeSummary,
  describeOperation,
  type StudioClose,
  type StudioCourse,
  type StudioMessage,
  type StudioPhaseName,
  type StudioSettings,
  type StudioSummary,
} from "@/lib/studio";

type Prefs = {
  title: string;
  audience: string;
  focus: string;
  theme: string;
  depth: StudioCourse["depth"];
  sources: string;
  close_style: StudioClose["close_style"];
  answer_style: StudioClose["answer_style"];
  choice_mode: "predefined" | "dynamic";
  itemsText: string;
  intent: string;
};

function prefsFrom(course: StudioCourse): Prefs {
  return {
    title: course.title,
    audience: course.audience,
    focus: course.focus,
    theme: course.theme,
    depth: course.depth,
    sources: course.sources,
    close_style: course.close_default.close_style,
    answer_style: course.close_default.answer_style,
    choice_mode: course.close_default.choice_mode ?? "dynamic",
    itemsText: course.close_default.items.map((item) => item.text).join("\n"),
    intent: course.close_default.intent,
  };
}

function closeFrom(prefs: Prefs): StudioClose {
  if (prefs.answer_style === "essay") {
    return {
      close_style: prefs.close_style,
      answer_style: "essay",
      choice_mode: null,
      items: [],
      intent: "",
    };
  }
  if (prefs.choice_mode === "predefined") {
    return {
      close_style: prefs.close_style,
      answer_style: prefs.answer_style,
      choice_mode: "predefined",
      items: prefs.itemsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((text) => ({ text })),
      intent: "",
    };
  }
  return {
    close_style: prefs.close_style,
    answer_style: prefs.answer_style,
    choice_mode: "dynamic",
    items: [],
    intent: prefs.intent.trim(),
  };
}

function readError(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "The studio could not answer.";
  try {
    const body = JSON.parse(trimmed) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    return trimmed;
  }
  return trimmed;
}

function listedCodes(course: StudioCourse): string[] {
  if (course.view.name === course.phase.name) return course.phase.open_codes;
  return course.view.codes;
}

function waveLabel(course: StudioCourse, code: string): string | null {
  const listed = listedCodes(course);
  if (!listed.includes(code)) return null;
  if (course.view.name === "goals" && course.gaps.includes(`${code}: no learning goal`)) return "Needs a learning goal";
  if (course.view.name === "close" && course.gaps.includes(`${code}: no close style`)) return "Needs a close style";
  if (course.view.name === "structure") {
    const unit = course.units.find((item) => item.code === code);
    if (unit && unit.quests.length === 0) return "Needs a quest";
  }
  return null;
}

function Tier({
  code,
  title,
  marks,
  wave,
  open,
  onToggle,
  children,
}: {
  code: string;
  title: string;
  marks: string[];
  wave: boolean;
  open: boolean;
  onToggle: () => void;
  children?: ReactNode;
}) {
  return (
    <li className="studio-tier">
      <button type="button" className={`studio-tier-row${wave ? " is-wave" : ""}`} aria-expanded={open} onClick={onToggle}>
        <span aria-hidden="true">{open ? "▾" : "▸"}</span>
        <span className="studio-code">{code}</span>
        <span className="studio-title">{title}</span>
        {marks.map((mark) => (
          <span key={mark} className="studio-gap">{mark}</span>
        ))}
      </button>
      {open ? <div className="studio-detail">{children}</div> : null}
    </li>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <p className="studio-fact">
      <span>{label}</span>
      {value}
    </p>
  );
}

export function CreateCourse() {
  const [courses, setCourses] = useState<StudioSummary[]>([]);
  const [course, setCourse] = useState<StudioCourse | null>(null);
  const [messages, setMessages] = useState<StudioMessage[]>([]);
  const [settings, setSettings] = useState<StudioSettings | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [creating, setCreating] = useState(false);
  const [draftCode, setDraftCode] = useState("");
  const [draftTitle, setDraftTitle] = useState("");
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [coursesOpen, setCoursesOpen] = useState(false);
  const [modelDraft, setModelDraft] = useState("gpt-4o-mini");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [rows, nextSettings] = await Promise.all([
          api<StudioSummary[]>("/studio/courses"),
          api<StudioSettings>("/studio/settings"),
        ]);
        if (cancelled) return;
        setCourses(rows);
        setSettings(nextSettings);
        setModelDraft(nextSettings.model);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "The studio service is not reachable.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setPrefs(course ? prefsFrom(course) : null);
  }, [course]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, busy]);

  function toggle(code: string) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  async function openCourse(id: string) {
    setError(null);
    setSavedNote(null);
    const [next, history] = await Promise.all([
      api<StudioCourse>(`/studio/courses/${id}`),
      api<StudioMessage[]>(`/studio/courses/${id}/messages`),
    ]);
    setCourse(next);
    setMessages(history);
    setOpen(new Set(next.units.map((unit) => unit.code)));
  }

  async function createCourse(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api<StudioCourse>("/studio/courses", {
        method: "POST",
        body: JSON.stringify({ code: draftCode, title: draftTitle }),
      });
      setCourses((prev) => [
        { id: created.id, code: created.code, title: created.title, updated_at: created.updated_at },
        ...prev.filter((row) => row.id !== created.id),
      ]);
      setCourse(created);
      setMessages([]);
      setOpen(new Set());
      setCreating(false);
      setDraftCode("");
      setDraftTitle("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create that course.");
    } finally {
      setBusy(false);
    }
  }

  async function savePrefs(event: FormEvent) {
    event.preventDefault();
    if (!course || !prefs) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<StudioCourse>(`/studio/courses/${course.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: prefs.title,
          audience: prefs.audience,
          focus: prefs.focus,
          theme: prefs.theme,
          depth: prefs.depth,
          sources: prefs.sources.trim() || "none",
          close_default: closeFrom(prefs),
        }),
      });
      setCourse(next);
      setCourses((rows) =>
        rows.map((row) => (row.id === next.id ? { ...row, title: next.title, updated_at: next.updated_at } : row)),
      );
      setSavedNote("Saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save those preferences.");
    } finally {
      setBusy(false);
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!course || !text || busy) return;
    setBusy(true);
    setError(null);
    setInput("");
    try {
      const response = await fetch("/api/studio/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ courseId: course.id, content: text }),
      });
      const raw = await response.text();
      if (!response.ok) throw new Error(readError(raw));
      const body = JSON.parse(raw) as { user: StudioMessage; assistant: StudioMessage };
      setMessages((prev) => [...prev, body.user, body.assistant]);
    } catch (err) {
      setInput(text);
      setError(err instanceof Error ? err.message : "The studio could not answer.");
    } finally {
      setBusy(false);
    }
  }

  async function accept(message: StudioMessage) {
    if (!course) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ course: StudioCourse; message: StudioMessage }>(
        `/studio/courses/${course.id}/messages/${message.id}/accept`,
        { method: "POST" },
      );
      setCourse(result.course);
      setMessages((prev) => prev.map((item) => (item.id === result.message.id ? result.message : item)));
      setOpen((prev) => {
        const next = new Set(prev);
        for (const unit of result.course.units) next.add(unit.code);
        return next;
      });
      setSavedNote("Course updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save that change.");
    } finally {
      setBusy(false);
    }
  }

  async function dismiss(message: StudioMessage) {
    if (!course) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<StudioMessage>(
        `/studio/courses/${course.id}/messages/${message.id}/dismiss`,
        { method: "POST" },
      );
      setMessages((prev) => prev.map((item) => (item.id === next.id ? next : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not dismiss that change.");
    } finally {
      setBusy(false);
    }
  }

  async function choosePhase(name: StudioPhaseName) {
    if (!course || busy) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<StudioCourse>(`/studio/courses/${course.id}/phase`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setCourse(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open that phase.");
    } finally {
      setBusy(false);
    }
  }

  async function markReady() {
    if (!course || course.ready || course.phase.name !== "ready") return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<StudioCourse>(`/studio/courses/${course.id}/ready`, { method: "POST" });
      setCourse(next);
      setSavedNote("Marked ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not mark this course ready.");
    } finally {
      setBusy(false);
    }
  }

  async function saveModel(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const next = await api<StudioSettings>("/studio/settings", {
        method: "PUT",
        body: JSON.stringify({ model: modelDraft }),
      });
      setSettings(next);
      setModelDraft(next.model);
      setSettingsOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save that model.");
    } finally {
      setBusy(false);
    }
  }

  const choicesOpen = prefs != null && prefs.answer_style !== "essay";

  return (
    <main className="ds-shell studio-shell">
      <aside className="ds-side">
        <div className="ds-logo">
          <BrandMark />
        </div>
        <p className="ds-learner">Create course</p>
        <Link href="/manage-courses" className="studio-manage-link">Manage courses</Link>
        <button type="button" className="button studio-new" onClick={() => setCreating((openForm) => !openForm)}>
          New course
        </button>
        {creating ? (
          <form className="studio-new-form" onSubmit={(event) => void createCourse(event)}>
            <label>
              Code
              <input
                value={draftCode}
                onChange={(event) => setDraftCode(event.target.value)}
                placeholder="GEO"
                maxLength={16}
                required
                autoComplete="off"
              />
            </label>
            <label>
              Title
              <input
                value={draftTitle}
                onChange={(event) => setDraftTitle(event.target.value)}
                placeholder="Triangles"
                maxLength={240}
                required
              />
            </label>
            <div className="rail-actions">
              <button className="button" type="submit" disabled={busy}>Create</button>
              <button type="button" className="ghost" onClick={() => setCreating(false)}>Cancel</button>
            </div>
          </form>
        ) : null}
        <button
          type="button"
          className="studio-courses-toggle"
          aria-expanded={coursesOpen}
          aria-controls="studio-course-list"
          onClick={() => setCoursesOpen((open) => !open)}
        >
          Courses
          <span aria-hidden="true">{coursesOpen ? "▴" : "▾"}</span>
        </button>
        <ul
          id="studio-course-list"
          className={`studio-courses${coursesOpen ? " is-open" : ""}`}
          aria-label="Saved courses"
        >
          {courses.length === 0 ? <li className="ds-quiet">No saved courses</li> : null}
          {courses.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                className={`ds-row${course?.id === row.id ? " is-on" : ""}`}
                aria-current={course?.id === row.id ? "true" : undefined}
                onClick={() => void openCourse(row.id).catch((err: unknown) => {
                  setError(err instanceof Error ? err.message : "Could not open that course.");
                })}
              >
                <strong>{row.title}</strong>
                <small>{row.code}</small>
              </button>
            </li>
          ))}
        </ul>
        <div className="ds-side-spacer" />
        <div className="ds-foot">
          <button
            type="button"
            className="ds-settings"
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
            onClick={() => {
              setModelDraft(settings?.model ?? "gpt-4o-mini");
              setSettingsOpen(true);
            }}
          >
            Model · {settings?.model ?? "gpt-4o-mini"}
          </button>
        </div>
      </aside>
      <section className="studio-stage">
        {!course || !prefs ? (
          <div className="ds-empty">
            <p>Create a course, then describe the focus in the chat.</p>
          </div>
        ) : (
          <>
            <form className="studio-prefs" onSubmit={(event) => void savePrefs(event)}>
              <div className="studio-prefs-head">
                <h1>
                  <span className="studio-code">{course.code}</span>
                  {prefs.title || course.title}
                  <span className="studio-draft">{course.ready ? "Ready" : "Draft"}</span>
                  <span className="studio-phase-name">{course.view.label}</span>
                </h1>
                <div className="rail-actions">
                  {savedNote ? <span className="studio-saved">{savedNote}</span> : null}
                  <button className="button" type="submit" disabled={busy}>Save preferences</button>
                </div>
              </div>
              <div className="studio-grid">
                <label>
                  Title
                  <input value={prefs.title} maxLength={240} required onChange={(event) => setPrefs({ ...prefs, title: event.target.value })} />
                </label>
                <label>
                  Audience
                  <input
                    value={prefs.audience}
                    placeholder="Grade 6, new to polygons"
                    onChange={(event) => setPrefs({ ...prefs, audience: event.target.value })}
                  />
                </label>
                <label>
                  Focus
                  <input
                    value={prefs.focus}
                    placeholder="triangles"
                    onChange={(event) => setPrefs({ ...prefs, focus: event.target.value })}
                  />
                </label>
                <label>
                  Theme
                  <input
                    value={prefs.theme}
                    placeholder="city planning, or no theme"
                    onChange={(event) => setPrefs({ ...prefs, theme: event.target.value })}
                  />
                </label>
                <label>
                  Depth
                  <select
                    value={prefs.depth}
                    onChange={(event) => setPrefs({ ...prefs, depth: event.target.value as Prefs["depth"] })}
                  >
                    {DEPTHS.map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Framework to honor
                  <input
                    value={prefs.sources}
                    placeholder="None"
                    onChange={(event) => setPrefs({ ...prefs, sources: event.target.value })}
                  />
                </label>
                <label>
                  Close default
                  <select
                    value={prefs.close_style}
                    onChange={(event) =>
                      setPrefs({ ...prefs, close_style: event.target.value as Prefs["close_style"] })
                    }
                  >
                    <option value="one">One question</option>
                    <option value="several">Several questions</option>
                  </select>
                </label>
                <label>
                  Answer style
                  <select
                    value={prefs.answer_style}
                    onChange={(event) =>
                      setPrefs({ ...prefs, answer_style: event.target.value as Prefs["answer_style"] })
                    }
                  >
                    <option value="multiple_choice">Multiple choice</option>
                    <option value="essay">Essay</option>
                    <option value="mixed">Mixed</option>
                  </select>
                </label>
                {choicesOpen ? (
                  <label>
                    Multiple choice
                    <select
                      value={prefs.choice_mode}
                      onChange={(event) =>
                        setPrefs({ ...prefs, choice_mode: event.target.value as Prefs["choice_mode"] })
                      }
                    >
                      <option value="predefined">Predefined</option>
                      <option value="dynamic">Dynamic</option>
                    </select>
                  </label>
                ) : null}
                {choicesOpen && prefs.choice_mode === "predefined" ? (
                  <label className="studio-span">
                    Predefined choices
                    <textarea
                      value={prefs.itemsText}
                      placeholder={"One choice per line"}
                      onChange={(event) => setPrefs({ ...prefs, itemsText: event.target.value })}
                    />
                  </label>
                ) : null}
                {choicesOpen && prefs.choice_mode === "dynamic" ? (
                  <label className="studio-span">
                    Dynamic intent
                    <input
                      value={prefs.intent}
                      placeholder="What the choices should test"
                      onChange={(event) => setPrefs({ ...prefs, intent: event.target.value })}
                    />
                  </label>
                ) : null}
              </div>
            </form>
            <div className="studio-tree" aria-label="Course so far">
              <div className="studio-strip" aria-label="Course phases">
                {course.strip.map((item) => {
                  const order = ["structure", "goals", "close", "ready"];
                  const later = order.indexOf(item.name) > order.indexOf(course.phase.name);
                  return (
                  <button
                    key={item.name}
                    type="button"
                    className={`studio-strip-phase${item.active ? " is-active" : ""}${item.filled ? " is-filled" : ""}`}
                    aria-current={item.active ? "step" : undefined}
                    disabled={busy || later}
                    onClick={() => void choosePhase(item.name)}
                  >
                    <span>{item.label}</span>
                    {item.filled ? <span className="studio-strip-filled">Filled</span> : null}
                  </button>
                  );
                })}
              </div>
              <p className="studio-phase-codes" aria-label="Phase codes">
                {course.view.name === course.phase.name
                  ? course.phase.open_codes.length > 0
                    ? `Still open: ${course.phase.open_codes.join(", ")}`
                    : "Mark ready can be turned on."
                  : `Codes: ${course.view.codes.join(", ") || "none"}`}
              </p>
              <div className="studio-ready">
                <button
                  type="button"
                  className="button"
                  disabled={busy || course.ready || course.phase.name !== "ready"}
                  onClick={() => void markReady()}
                >
                  {course.ready ? "Marked ready" : "Mark ready"}
                </button>
                {course.gaps.length > 0 ? (
                  <details className="studio-all-gaps">
                    <summary>All gaps</summary>
                    <ul className="studio-gaps" aria-label="Open gaps">
                      {course.gaps.map((gap) => (
                        <li key={gap}>{gap}</li>
                      ))}
                    </ul>
                  </details>
                ) : null}
              </div>
              {course.units.length === 0 ? (
                <p className="ds-quiet">No units yet. The tree updates after you accept a change.</p>
              ) : (
                <ul className="studio-tree-list">
                  {course.units.map((unit) => (
                    <Tier
                      key={unit.id}
                      code={unit.code}
                      title={unit.title}
                      marks={[waveLabel(course, unit.code)].filter((mark): mark is string => mark != null)}
                      wave={listedCodes(course).includes(unit.code)}
                      open={open.has(unit.code)}
                      onToggle={() => toggle(unit.code)}
                    >
                      <Fact label="Goal" value={unit.learning_goal} />
                      <Fact label="Success" value={unit.success_criterion} />
                      <ul>
                        {unit.quests.map((quest) => (
                          <Tier
                            key={quest.id}
                            code={quest.code}
                            title={quest.title}
                            marks={[waveLabel(course, quest.code)].filter((mark): mark is string => mark != null)}
                            wave={listedCodes(course).includes(quest.code)}
                            open={open.has(quest.code)}
                            onToggle={() => toggle(quest.code)}
                          >
                            <Fact label="Goal" value={quest.learning_goal} />
                            <Fact label="Success" value={quest.success_criterion} />
                            {quest.close ? <p className="studio-fact"><span>Close</span>{closeSummary(quest.close)}</p> : null}
                            {quest.close?.choice_mode === "dynamic" && quest.close.intent ? (
                              <Fact label="Intent" value={quest.close.intent} />
                            ) : null}
                            {quest.close?.choice_mode === "predefined" ? (
                              <ul className="studio-choices">
                                {quest.close.items.map((item) => (
                                  <li key={item.text}>{item.text}</li>
                                ))}
                              </ul>
                            ) : null}
                            <ul>
                              {quest.moves.map((move) => (
                                <Tier
                                  key={move.id}
                                  code={move.code}
                                  title={move.title}
                                  marks={[waveLabel(course, move.code)].filter((mark): mark is string => mark != null)}
                                  wave={listedCodes(course).includes(move.code)}
                                  open={open.has(move.code)}
                                  onToggle={() => toggle(move.code)}
                                >
                                  <Fact label="Goal" value={move.learning_goal} />
                                  <Fact label="Success" value={move.success_criterion} />
                                </Tier>
                              ))}
                            </ul>
                          </Tier>
                        ))}
                      </ul>
                    </Tier>
                  ))}
                </ul>
              )}
            </div>
            <div className="studio-chat">
              <div className="ds-scroll">
                <div className="ds-column">
                  {messages.length === 0 ? (
                    <p className="ds-quiet">
                      State a focus, such as grade 6 geometry. Suggestions name the framework they come from. Nothing is saved until you accept it.
                    </p>
                  ) : null}
                  {messages.map((message) => (
                    <div key={message.id} className={`bubble ${message.role === "user" ? "user" : "assistant"}`}>
                      <p>{message.content}</p>
                      {message.proposal && !message.applied ? (
                        <div className="studio-proposal">
                          <p>Accept this change to update the course.</p>
                          <ul>
                            {message.proposal.operations.map((op, index) => (
                              <li key={`${op.op}-${op.code}-${index}`}>{describeOperation(op)}</li>
                            ))}
                          </ul>
                          <div className="rail-actions">
                            <button type="button" className="button" disabled={busy} onClick={() => void accept(message)}>
                              Accept
                            </button>
                            <button type="button" className="ghost" disabled={busy} onClick={() => void dismiss(message)}>
                              Dismiss
                            </button>
                          </div>
                        </div>
                      ) : null}
                      {message.applied ? <p className="studio-saved">Saved to the course.</p> : null}
                    </div>
                  ))}
                  <div ref={endRef} />
                </div>
              </div>
              {busy ? <p className="ds-typing">Writing…</p> : null}
              {error ? (
                <div className="banner" role="alert">
                  <p>{error}</p>
                </div>
              ) : null}
              <form className="ds-composer-seat" onSubmit={(event) => void send(event)}>
                <div className="ds-card">
                  <textarea
                    className="ds-draft"
                    value={input}
                    rows={1}
                    placeholder="Describe the course you want"
                    aria-label="Message the course builder"
                    disabled={busy}
                    maxLength={8000}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        event.currentTarget.form?.requestSubmit();
                      }
                    }}
                  />
                  <div className="ds-card-row">
                    <button className="ds-send" type="submit" aria-label="Send" disabled={busy || input.trim().length === 0}>
                      ↑
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </>
        )}
        {error && !course ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
      </section>
      {settingsOpen ? (
        <div className="prompt-backdrop" role="presentation" onMouseDown={() => setSettingsOpen(false)}>
          <div
            className="prompt-dialog settings-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="studio-model-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <h2 id="studio-model-title">Model</h2>
                <p>This choice is only for CreateCourse. It does not change the kid tutor.</p>
              </div>
              <button type="button" className="ghost" onClick={() => setSettingsOpen(false)}>Close</button>
            </header>
            <form className="prompt-body" onSubmit={(event) => void saveModel(event)}>
              <label>
                Model
                <select value={modelDraft} onChange={(event) => setModelDraft(event.target.value)}>
                  {(settings?.options ?? ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"]).map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              {error ? (
                <div className="banner" role="alert">
                  <p>{error}</p>
                </div>
              ) : null}
              <div className="rail-actions">
                <button className="button" type="submit" disabled={busy}>Save model</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </main>
  );
}
