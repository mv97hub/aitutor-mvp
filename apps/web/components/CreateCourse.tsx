"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { BrandMark } from "@/components/BrandMark";
import { api } from "@/lib/api";
import { STUDIO_MODELS, kcModelLabel } from "@/lib/kc-models";
import {
  AGE_BANDS,
  DEPTHS,
  QUIZ_MINUTES,
  closeSummary,
  type StudioClose,
  type StudioCourse,
  type StudioMessage,
  type StudioPhaseName,
  type StudioSettings,
  type StudioSummary,
} from "@/lib/studio";

type QuestPopup = { kind: "quest"; mode: "add" | "edit"; code: string; title: string };
type GoalPopup = {
  kind: "goal";
  mode: "add" | "edit";
  code: string;
  position: number;
  learningGoal: string;
  success: string;
};
type CloseMode = "single" | "multiple" | "none";
type ClosePopup = {
  kind: "close";
  code: string;
  index: number;
  mode: CloseMode;
  question: string;
  options: { text: string; correct: boolean }[];
};
type Popup = QuestPopup | GoalPopup | ClosePopup;

type Prefs = {
  code: string;
  title: string;
  audience: string;
  focus: string;
  theme: string;
  depth: StudioCourse["depth"];
  quizMinutes: StudioCourse["quiz_minutes"];
  sources: string;
  questCount: number;
  goalsPerQuest: number;
  close_style: StudioClose["close_style"];
  answer_style: StudioClose["answer_style"];
  choice_mode: "predefined" | "dynamic";
  itemsText: string;
  intent: string;
};

function blankPrefs(): Prefs {
  return {
    code: "",
    title: "",
    audience: "9-11",
    focus: "",
    theme: "",
    depth: "standard",
    quizMinutes: 5,
    sources: "",
    questCount: 10,
    goalsPerQuest: 3,
    close_style: "one",
    answer_style: "essay",
    choice_mode: "dynamic",
    itemsText: "",
    intent: "",
  };
}

function prefsFrom(course: StudioCourse): Prefs {
  return {
    code: course.code,
    title: course.title,
    audience: (AGE_BANDS as readonly string[]).includes(course.audience) ? course.audience : "9-11",
    focus: course.focus,
    theme: course.theme,
    depth: course.depth,
    quizMinutes: course.quiz_minutes,
    sources: course.sources,
    questCount: course.quest_count || 10,
    goalsPerQuest: course.goals_per_quest || 3,
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
      questions: [],
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
      questions: [],
      intent: "",
    };
  }
  return {
    close_style: prefs.close_style,
    answer_style: prefs.answer_style,
    choice_mode: "dynamic",
    items: [],
    questions: [],
    intent: prefs.intent.trim(),
  };
}

function fourOptions(source: { text: string; correct?: boolean }[]) {
  const rows = source.slice(0, 4).map((choice) => ({ text: choice.text, correct: Boolean(choice.correct) }));
  while (rows.length < 4) rows.push({ text: "", correct: false });
  const correctAt = rows.findIndex((row) => row.correct);
  const chosen = correctAt < 0 ? 0 : correctAt;
  return rows.map((row, index) => ({ ...row, correct: index === chosen }));
}

function closePopupFrom(code: string, close: StudioClose | null, index: number): ClosePopup {
  const item = close?.questions[index];
  const own = item?.choices ?? [];
  const legacy = !own.length && index === 0 ? close?.items ?? [] : [];
  const source = own.length ? own : legacy;
  const hasChoices = source.length > 0;
  let mode: CloseMode = "single";
  if (!item) {
    if (!close || (close.questions.length === 0 && close.items.length === 0)) mode = "none";
  } else if (item.kind === "multiple" || (item.kind === "single" && hasChoices) || (hasChoices && item.kind !== "single")) {
    mode = "multiple";
  }
  return {
    kind: "close",
    code,
    index,
    mode,
    question: item?.text ?? "",
    options: fourOptions(source),
  };
}

function popupBody(popup: Popup): Record<string, unknown> {
  if (popup.kind === "quest") {
    return { action: popup.mode === "add" ? "add_quest" : "update_quest", code: popup.code, title: popup.title };
  }
  if (popup.kind === "goal") {
    return {
      action: popup.mode === "add" ? "add_goal" : "update_goal",
      code: popup.code,
      position: popup.position,
      learning_goal: popup.learningGoal,
      success_criterion: popup.success,
    };
  }
  if (popup.mode === "none") {
    return {
      action: "set_close",
      code: popup.code,
      question_index: popup.index,
      close: { close_style: "one", answer_style: "essay", choice_mode: null, items: [], questions: [], intent: "" },
    };
  }
  const text = popup.question.trim();
  if (popup.mode === "single") {
    return {
      action: "set_close",
      code: popup.code,
      question_index: popup.index,
      close: {
        close_style: "one",
        answer_style: "essay",
        choice_mode: null,
        selection: null,
        items: [],
        questions: text ? [{ text, kind: "single", choices: [] }] : [],
        intent: "",
      },
    };
  }
  return {
    action: "set_close",
    code: popup.code,
    question_index: popup.index,
    close: {
      close_style: "one",
      answer_style: "multiple_choice",
      choice_mode: "predefined",
      selection: null,
      items: [],
      questions: [
        {
          text: text || "Choose the best answer.",
          kind: "multiple",
          choices: popup.options
            .filter((option) => option.text.trim())
            .map((option) => ({ text: option.text.trim(), correct: option.correct })),
        },
      ],
      intent: "",
    },
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

function Tier({
  code,
  title,
  marks,
  wave,
  open,
  onToggle,
  onEdit,
  children,
}: {
  code: string;
  title: string;
  marks: string[];
  wave: boolean;
  open: boolean;
  onToggle: () => void;
  onEdit?: () => void;
  children?: ReactNode;
}) {
  return (
    <li className="studio-tier">
      <div className="studio-tier-line">
        <button type="button" className={`studio-tier-row${wave ? " is-wave" : ""}`} aria-expanded={open} onClick={onToggle}>
          <span aria-hidden="true">{open ? "▾" : "▸"}</span>
          <span className="studio-code">{code}</span>
          <span className="studio-title">{title}</span>
          {marks.map((mark) => (
            <span key={mark} className="studio-gap">{mark}</span>
          ))}
        </button>
        {onEdit ? (
          <button type="button" className="ghost studio-inline" onClick={onEdit}>
            Edit
          </button>
        ) : null}
      </div>
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
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [draft, setDraft] = useState<Prefs | null>(null);
  const [draftMode, setDraftMode] = useState<"create" | "edit" | null>(null);
  const [prefError, setPrefError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [coursesOpen, setCoursesOpen] = useState(false);
  const [modelDraft, setModelDraft] = useState("gpt-4o-mini");
  const [popup, setPopup] = useState<Popup | null>(null);
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
    setDraft(null);
    setDraftMode(null);
    setMessages(history);
    setOpen(new Set(next.quests.map((quest) => quest.code)));
  }

  function cancelPrefs() {
    setDraft(null);
    setDraftMode(null);
    setPrefError(null);
  }

  function preferenceBody(nextTitle: string, focus: string) {
    if (!draft) throw new Error("Preferences are closed.");
    return {
      title: nextTitle,
      audience: draft.audience,
      focus,
      theme: draft.theme.trim(),
      depth: draft.depth,
      quiz_minutes: draft.quizMinutes,
      sources: draft.sources.trim() || "none",
      quest_count: draft.questCount,
      goals_per_quest: draft.goalsPerQuest,
      close_default: closeFrom(draft),
    };
  }

  async function savePrefs(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    setBusy(true);
    setPrefError(null);
    try {
      if (draftMode === "create") {
        const created = await api<StudioCourse>("/studio/courses", {
          method: "POST",
          body: JSON.stringify({ code: draft.code.trim(), title: draft.title.trim() }),
        });
        try {
          await api<StudioCourse>(`/studio/courses/${created.id}`, {
            method: "PATCH",
            body: JSON.stringify(preferenceBody(created.title, "")),
          });
          const opened = await api<{ course: StudioCourse; messages: StudioMessage[] }>(
            `/studio/courses/${created.id}/opening`,
            { method: "POST" },
          );
          setCourses((prev) => [
            {
              id: opened.course.id,
              code: opened.course.code,
              title: opened.course.title,
              updated_at: opened.course.updated_at,
            },
            ...prev.filter((row) => row.id !== opened.course.id),
          ]);
          setCourse(opened.course);
          setMessages(opened.messages);
          setOpen(new Set());
          setDraft(null);
          setDraftMode(null);
          setInput("");
          setSavedNote(null);
        } catch (err) {
          setCourses((prev) => [
            { id: created.id, code: created.code, title: created.title, updated_at: created.updated_at },
            ...prev.filter((row) => row.id !== created.id),
          ]);
          setCourse(created);
          setMessages([]);
          setDraft(null);
          setDraftMode(null);
          setError(err instanceof Error ? err.message : "Could not finish that course.");
        }
        return;
      }
      if (!course) return;
      const next = await api<StudioCourse>(`/studio/courses/${course.id}`, {
        method: "PATCH",
        body: JSON.stringify(preferenceBody(course.title, course.focus)),
      });
      setCourse(next);
      setCourses((rows) =>
        rows.map((row) => (row.id === next.id ? { ...row, title: next.title, updated_at: next.updated_at } : row)),
      );
      setDraft(null);
      setDraftMode(null);
      setPrefError(null);
      setSavedNote("Saved");
    } catch (err) {
      setPrefError(err instanceof Error ? err.message : "Could not save those preferences.");
    } finally {
      setBusy(false);
    }
  }

  async function ask(text: string) {
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
      const body = JSON.parse(raw) as {
        user: StudioMessage;
        assistant: StudioMessage;
        course?: StudioCourse;
        wrote?: boolean;
      };
      if (body.course) {
        const history = await api<StudioMessage[]>(`/studio/courses/${body.course.id}/messages`);
        setCourse(body.course);
        setMessages(history);
        openQuests(body.course);
        if (body.wrote) setSavedNote("Course updated");
      } else {
        setMessages((prev) => [...prev, body.user, body.assistant]);
      }
    } catch (err) {
      setInput(text);
      setError(err instanceof Error ? err.message : "The studio could not answer.");
    } finally {
      setBusy(false);
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    await ask(input.trim());
  }

  function openQuests(nextCourse: StudioCourse) {
    setOpen((prev) => {
      const next = new Set(prev);
      for (const quest of nextCourse.quests) next.add(quest.code);
      return next;
    });
  }

  async function undo() {
    if (!course) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<StudioCourse>(`/studio/courses/${course.id}/undo`, { method: "POST" });
      const history = await api<StudioMessage[]>(`/studio/courses/${course.id}/messages`);
      setCourse(next);
      setMessages(history);
      setPopup(null);
      setSavedNote("Undone");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not undo that write.");
    } finally {
      setBusy(false);
    }
  }

  async function choosePhase(name: StudioPhaseName) {
    if (!course || busy) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<StudioCourse>(`/studio/courses/${course.id}/stage`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setCourse(next);
      setPopup(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open that stage.");
    } finally {
      setBusy(false);
    }
  }

  async function advanceStage() {
    if (!course || !course.can_advance) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<StudioCourse>(`/studio/courses/${course.id}/advance-stage`, { method: "POST" });
      const history = await api<StudioMessage[]>(`/studio/courses/${course.id}/messages`);
      setCourse(next);
      setMessages(history);
      setPopup(null);
      setSavedNote(next.ready ? "Submitted" : "Stage complete");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not mark this stage complete.");
    } finally {
      setBusy(false);
    }
  }

  async function pushDraft() {
    if (!course || !course.can_push) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<StudioCourse>(`/studio/courses/${course.id}/push-draft`, { method: "POST" });
      const history = await api<StudioMessage[]>(`/studio/courses/${course.id}/messages`);
      setCourse(next);
      setMessages(history);
      openQuests(next);
      setSavedNote("Draft is in the tree");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not push that draft.");
    } finally {
      setBusy(false);
    }
  }

  async function savePopup(event: FormEvent) {
    event.preventDefault();
    if (!course || !popup) return;
    setBusy(true);
    setError(null);
    try {
      const body = popupBody(popup);
      const next = await api<StudioCourse>(`/studio/courses/${course.id}/tree`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setCourse(next);
      setPopup(null);
      openQuests(next);
      setSavedNote("Course updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save that edit.");
    } finally {
      setBusy(false);
    }
  }

  async function deletePopup() {
    if (!course || !popup || popup.kind === "close") return;
    setBusy(true);
    setError(null);
    try {
      const action = popup.kind === "quest" ? "delete_quest" : "delete_goal";
      const next = await api<StudioCourse>(`/studio/courses/${course.id}/tree`, {
        method: "POST",
        body: JSON.stringify({
          action,
          code: popup.code,
          position: popup.kind === "goal" ? popup.position : undefined,
        }),
      });
      setCourse(next);
      setPopup(null);
      setSavedNote("Course updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete that item.");
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

  const detailLabel = DEPTHS.find((item) => item.value === prefs?.depth)?.label ?? "Standard";
  const lockingIdentity = draftMode === "edit";

  return (
    <main className="ds-shell studio-shell">
      <aside className="ds-side">
        <div className="ds-logo">
          <BrandMark />
        </div>
        <p className="ds-learner">Create course</p>
        <Link href="/manage-courses" className="studio-manage-link">Manage courses</Link>
        <button
          type="button"
          className="button studio-new"
          onClick={() => {
            setPrefError(null);
            setDraftMode("create");
            setDraft(blankPrefs());
          }}
        >
          New course
        </button>
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
            Model · {kcModelLabel(settings?.model ?? "gpt-4o-mini")}
          </button>
        </div>
      </aside>
      <section className="studio-stage">
        {!course || !prefs ? (
          <div className="ds-empty">
            <p>Create a course. The description in that form is what the quests follow.</p>
          </div>
        ) : (
          <>
            <div className="studio-prefs">
              <div className="studio-prefs-head">
                <div className="studio-prefs-title">
                  <h1>
                    <span className="studio-code">{course.code}</span>
                    {course.title}
                    <span className="studio-draft">{course.ready ? "Ready" : "Draft"}</span>
                    <span className="studio-phase-name">{course.stage_view.label}</span>
                  </h1>
                  <p className="studio-pref-summary">
                    {detailLabel} · {course.quiz_minutes} minutes before the quiz
                    {(AGE_BANDS as readonly string[]).includes(course.audience) ? ` · Ages ${course.audience}` : ""}
                    {course.theme ? ` · ${course.theme}` : ""}
                  </p>
                </div>
                <div className="studio-prefs-actions">
                  {savedNote ? <span className="studio-saved">{savedNote}</span> : null}
                  {course.undo ? (
                    <button className="ghost" type="button" disabled={busy} onClick={() => void undo()}>
                      Undo last write
                    </button>
                  ) : null}
                  <button
                    className="button"
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      setPrefError(null);
                      setDraftMode("edit");
                      setDraft(prefsFrom(course));
                    }}
                  >
                    Edit preferences
                  </button>
                </div>
              </div>
            </div>
            <div className="studio-strip" aria-label="Course stages">
              {course.stage_strip.map((item) => {
                const order = ["quests", "goals", "close", "ready"];
                const later = order.indexOf(item.name) > order.indexOf(course.stage.name);
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
            <div className="studio-columns">
            <div className="studio-tree" aria-label="Course so far">
              <div className="studio-ready">
                <button
                  type="button"
                  className="button"
                  disabled={busy || !course.can_advance}
                  onClick={() => void advanceStage()}
                >
                  {course.ready ? "Submitted" : course.stage_view.name === "ready" ? "Final Submit" : "Mark Complete"}
                </button>
                {course.stage_view.name === "quests" ? (
                  <button
                    type="button"
                    className="ghost"
                    disabled={busy}
                    onClick={() => setPopup({ kind: "quest", mode: "add", code: "", title: "" })}
                  >
                    Add quest
                  </button>
                ) : null}
              </div>
              {course.quests.length === 0 ? (
                <p className="ds-quiet">No quests yet.</p>
              ) : (
                <ul className="studio-tree-list">
                  {course.quests.map((quest) => {
                    const goals = quest.goals.length > 0 ? quest.goals : [];
                    return (
                    <Tier
                      key={quest.id}
                      code={quest.code}
                      title={quest.title}
                      marks={[]}
                      wave={false}
                      open={open.has(quest.code)}
                      onToggle={() => toggle(quest.code)}
                      onEdit={course.stage_view.name === "quests" ? () => setPopup({ kind: "quest", mode: "edit", code: quest.code, title: quest.title }) : undefined}
                    >
                      {goals.length === 0 ? <p className="ds-quiet">No goals yet.</p> : null}
                      {goals.map((goal) => (
                        <div key={goal.position} className="studio-goal-row">
                          <Fact label={`Goal ${goal.position}`} value={goal.learning_goal || "No learning goal yet"} />
                          <Fact label="Success criterion" value={goal.success_criterion || "No success criterion yet"} />
                          {course.stage_view.name === "goals" ? (
                            <button
                              type="button"
                              className="ghost studio-inline"
                              onClick={() => setPopup({
                                kind: "goal",
                                mode: "edit",
                                code: quest.code,
                                position: goal.position,
                                learningGoal: goal.learning_goal,
                                success: goal.success_criterion,
                              })}
                            >
                              Edit
                            </button>
                          ) : null}
                        </div>
                      ))}
                      {course.stage_view.name === "goals" ? (
                        <button
                          type="button"
                          className="ghost studio-inline"
                          onClick={() => setPopup({ kind: "goal", mode: "add", code: quest.code, position: goals.length + 1, learningGoal: "", success: "" })}
                        >
                          Add goal
                        </button>
                      ) : null}
                      <p className="studio-fact"><span>Close</span>{quest.close ? closeSummary(quest.close) : "No close yet"}</p>
                      {(quest.close?.questions ?? []).map((item, index) => (
                        <div key={`${quest.code}-question-${index}`} className="studio-goal-row">
                          <p className="studio-fact">
                            <span>{item.kind === "multiple" ? "Multiple choice" : "Single choice"} {index + 1}</span>
                            {item.text}
                          </p>
                          {item.kind === "multiple" && item.choices?.length ? (
                            <ul className="studio-choices">
                              {item.choices.map((choice) => (
                                <li key={choice.text}>{choice.correct ? `${choice.text} (correct)` : choice.text}</li>
                              ))}
                            </ul>
                          ) : null}
                          {course.stage_view.name === "close" ? (
                            <button
                              type="button"
                              className="ghost studio-inline"
                              onClick={() => setPopup(closePopupFrom(quest.code, quest.close, index))}
                            >
                              Edit
                            </button>
                          ) : null}
                        </div>
                      ))}
                      {quest.close?.items.length && !(quest.close.questions ?? []).some((item) => item.choices?.length) ? (
                        <ul className="studio-choices">
                          {quest.close.items.map((item) => (
                            <li key={item.text}>{item.correct ? `${item.text} (correct)` : item.text}</li>
                          ))}
                        </ul>
                      ) : null}
                      {course.stage_view.name === "close" ? (
                        <button
                          type="button"
                          className="ghost studio-inline"
                          onClick={() => setPopup(closePopupFrom(quest.code, quest.close, quest.close?.questions.length ?? 0))}
                        >
                          Add question
                        </button>
                      ) : null}
                    </Tier>
                    );
                  })}
                </ul>
              )}
              <section className="studio-gap-panel" aria-label="Gaps and issues">
                <h2>Gaps & Issues</h2>
                {course.stage_gaps.length === 0 ? (
                  <p className="ds-quiet">Nothing missing for this stage.</p>
                ) : (
                  <ul className="studio-gaps">
                    {course.stage_gaps.map((gap) => (
                      <li key={gap}>{gap}</li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
            <div className="studio-chat">
              <div className="ds-scroll">
                <div className="ds-column">
                  {messages.length === 0 ? (
                    <p className="ds-quiet">
                      The chat drafts this stage. The tree changes when you click Push draft to Tree.
                    </p>
                  ) : null}
                  {messages.map((message) => (
                    <div key={message.id} className={`bubble ${message.role === "user" ? "user" : "assistant"}`}>
                      <p>{message.content}</p>
                      {message.applied ? <p className="studio-saved">Saved to the course.</p> : null}
                    </div>
                  ))}
                  {course.stage_view.name !== "ready" && !course.can_push ? (
                    <p className="ds-quiet">Ask for the change on this stage.</p>
                  ) : null}
                  <div ref={endRef} />
                </div>
              </div>
              {busy ? <p className="ds-typing">Writing…</p> : null}
              {error ? (
                <div className="banner" role="alert">
                  <p>{error}</p>
                </div>
              ) : null}
              {course.stage_view.name !== "ready" ? (
                <button
                  type="button"
                  className="button studio-push"
                  disabled={busy || !course.can_push}
                  onClick={() => void pushDraft()}
                >
                  Push draft to Tree
                </button>
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
            </div>
          </>
        )}
        {error && !course ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
      </section>
      {popup ? (
        <div className="prompt-backdrop" role="presentation" onMouseDown={() => setPopup(null)}>
          <div
            className="prompt-dialog settings-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="studio-edit-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <h2 id="studio-edit-title">
                  {popup.kind === "quest" ? (popup.mode === "add" ? "Add quest" : "Edit quest") : null}
                  {popup.kind === "goal" ? (popup.mode === "add" ? "Add goal" : "Edit goal") : null}
                  {popup.kind === "close" ? `Question ${popup.index + 1}` : null}
                </h2>
              </div>
              <button type="button" className="ghost" onClick={() => setPopup(null)}>Close</button>
            </header>
            <form className="prompt-body" onSubmit={(event) => void savePopup(event)}>
              {popup.kind === "quest" ? (
                <label>
                  Title
                  <input value={popup.title} maxLength={240} required onChange={(event) => setPopup({ ...popup, title: event.target.value })} />
                </label>
              ) : null}
              {popup.kind === "goal" ? (
                <>
                  <label>
                    Learning goal
                    <textarea rows={3} value={popup.learningGoal} onChange={(event) => setPopup({ ...popup, learningGoal: event.target.value })} />
                  </label>
                  <label>
                    Success criterion
                    <textarea rows={3} value={popup.success} onChange={(event) => setPopup({ ...popup, success: event.target.value })} />
                  </label>
                </>
              ) : null}
              {popup.kind === "close" ? (
                <>
                  <label>
                    Close
                    <select
                      value={popup.mode}
                      onChange={(event) => {
                        const mode = event.target.value as CloseMode;
                        setPopup({
                          ...popup,
                          mode,
                          options: mode === "multiple" ? fourOptions(popup.options) : popup.options,
                        });
                      }}
                    >
                      <option value="single">Single choice</option>
                      <option value="multiple">Multiple choice</option>
                      <option value="none">No questions</option>
                    </select>
                  </label>
                  {popup.mode === "single" ? <p>The kid types the answer.</p> : null}
                  {popup.mode === "multiple" ? <p>Four options. The kid picks one.</p> : null}
                  {popup.mode !== "none" ? (
                    <label>
                      Question
                      <textarea rows={3} value={popup.question} onChange={(event) => setPopup({ ...popup, question: event.target.value })} />
                    </label>
                  ) : null}
                  {popup.mode === "multiple" ? (
                    <fieldset className="studio-options">
                      <legend>Options</legend>
                      {popup.options.map((option, index) => (
                        <div key={index} className="studio-option-row">
                          <input
                            value={option.text}
                            placeholder={`Option ${index + 1}`}
                            onChange={(event) => {
                              const options = popup.options.map((item, itemIndex) => itemIndex === index ? { ...item, text: event.target.value } : item);
                              setPopup({ ...popup, options });
                            }}
                          />
                          <label>
                            <input
                              type="radio"
                              name="correct-option"
                              checked={option.correct}
                              onChange={() => {
                                const options = popup.options.map((item, itemIndex) => ({ ...item, correct: itemIndex === index }));
                                setPopup({ ...popup, options });
                              }}
                            />
                            Correct
                          </label>
                        </div>
                      ))}
                    </fieldset>
                  ) : null}
                </>
              ) : null}
              <div className="prompt-actions">
                {popup.kind !== "close" && popup.mode === "edit" ? (
                  <button type="button" className="ghost" disabled={busy} onClick={() => void deletePopup()}>Delete</button>
                ) : null}
                <button className="button" type="submit" disabled={busy}>Save</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
      {draft ? (
        <div className="prompt-backdrop" role="presentation" onMouseDown={cancelPrefs}>
          <div
            className="prompt-dialog settings-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="studio-pref-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <h2 id="studio-pref-title">{draftMode === "create" ? "New course" : "Preferences"}</h2>
                <p>
                  {draftMode === "create"
                    ? "The course is created when you save. Code and name stay fixed after that."
                    : "Code and name stay as they are. A quest can still use a different close."}
                </p>
              </div>
              <button type="button" className="ghost" onClick={cancelPrefs}>Close</button>
            </header>
            <form className="prompt-body" onSubmit={(event) => void savePrefs(event)}>
              <label>
                Code
                <input
                  value={draft.code}
                  maxLength={16}
                  placeholder="GEO"
                  required
                  autoComplete="off"
                  disabled={lockingIdentity}
                  onChange={(event) => setDraft({ ...draft, code: event.target.value })}
                />
              </label>
              <label>
                Name
                <input
                  value={draft.title}
                  maxLength={240}
                  placeholder="Triangles"
                  required
                  disabled={lockingIdentity}
                  onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                />
              </label>
              <label>
                Course description
                <textarea
                  value={draft.theme}
                  rows={3}
                  maxLength={240}
                  placeholder="Who this is for, and what the course should cover"
                  onChange={(event) => setDraft({ ...draft, theme: event.target.value })}
                />
              </label>
              <label>
                Number of quests
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={draft.questCount}
                  onChange={(event) => setDraft({ ...draft, questCount: Number(event.target.value) })}
                />
              </label>
              <label>
                Goals per quest
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={draft.goalsPerQuest}
                  onChange={(event) => setDraft({ ...draft, goalsPerQuest: Number(event.target.value) })}
                />
              </label>
              <label>
                Detail
                <select
                  value={draft.depth}
                  onChange={(event) => setDraft({ ...draft, depth: event.target.value as Prefs["depth"] })}
                >
                  {DEPTHS.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label>
                Minimum time before the closing quiz
                <select
                  value={draft.quizMinutes}
                  onChange={(event) =>
                    setDraft({ ...draft, quizMinutes: Number(event.target.value) as Prefs["quizMinutes"] })
                  }
                >
                  {QUIZ_MINUTES.map((minutes) => (
                    <option key={minutes} value={minutes}>{minutes} minutes</option>
                  ))}
                </select>
              </label>
              <label>
                Close default
                <select
                  value={draft.close_style}
                  onChange={(event) =>
                    setDraft({ ...draft, close_style: event.target.value as Prefs["close_style"] })
                  }
                >
                  <option value="one">One question</option>
                  <option value="several">Several questions</option>
                </select>
              </label>
              <label>
                Answer style
                <select
                  value={draft.answer_style}
                  onChange={(event) =>
                    setDraft({ ...draft, answer_style: event.target.value as Prefs["answer_style"] })
                  }
                >
                  <option value="multiple_choice">Multiple choice</option>
                  <option value="essay">Single choice</option>
                  <option value="mixed">Mixed</option>
                </select>
              </label>
              <label>
                Audience
                <select
                  value={draft.audience}
                  onChange={(event) => setDraft({ ...draft, audience: event.target.value })}
                >
                  {AGE_BANDS.map((band) => (
                    <option key={band} value={band}>Ages {band}</option>
                  ))}
                </select>
              </label>
              <label>
                Framework to honor
                <input
                  value={draft.sources}
                  maxLength={80}
                  placeholder="None"
                  onChange={(event) => setDraft({ ...draft, sources: event.target.value })}
                />
              </label>
              {prefError ? (
                <div className="banner" role="alert">
                  <p>{prefError}</p>
                </div>
              ) : null}
              <div className="rail-actions">
                <button className="button" type="submit" disabled={busy}>Save</button>
                <button type="button" className="ghost" onClick={cancelPrefs}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
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
                  {(settings?.options ?? STUDIO_MODELS).map((option) => (
                    <option key={option} value={option}>{kcModelLabel(option)}</option>
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
