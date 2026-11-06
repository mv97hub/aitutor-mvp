"use client";

import { useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { api } from "@/lib/api";
import type { StudioSummary } from "@/lib/studio";
import type { CatalogQuest, CourseClose, CourseSummary, CourseTree } from "@/lib/types";

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function closeLabel(close: CourseClose | null) {
  if (!close || close.questions.length === 0) return "No questions";
  if (close.answer_style === "multiple_choice" && close.selection === "multi") return "Multi-choice";
  if (close.answer_style === "multiple_choice") return "Single choice";
  return "Essay";
}

export function AdminApp({
  initialCourses,
  initialTree,
  initialError,
}: {
  initialCourses: CourseSummary[];
  initialTree: CourseTree | null;
  initialError: string | null;
}) {
  const [courses, setCourses] = useState(initialCourses);
  const [tree, setTree] = useState<CourseTree | null>(initialTree);
  const [open, setOpen] = useState<string[]>(initialTree?.quests.map((quest) => quest.code) ?? []);
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<"import" | "remove" | null>(null);
  const [drafts, setDrafts] = useState<StudioSummary[]>([]);
  const [catalog, setCatalog] = useState<CourseSummary[]>([]);

  async function refreshCourses(selectId?: string) {
    const next = await api<CourseSummary[]>("/courses");
    setCourses(next);
    const id = selectId ?? (tree && next.some((course) => course.id === tree.id) ? tree.id : next[0]?.id);
    if (!id) {
      setTree(null);
      setOpen([]);
      return;
    }
    const loaded = await api<CourseTree>(`/courses/${id}`);
    setTree(loaded);
    setOpen(loaded.quests.map((quest) => quest.code));
  }

  async function openCourse(courseId: string) {
    setError(null);
    try {
      const loaded = await api<CourseTree>(`/courses/${courseId}`);
      setTree(loaded);
      setOpen(loaded.quests.map((quest) => quest.code));
    } catch (err) {
      setError(messageOf(err));
    }
  }

  async function openImport() {
    setError(null);
    setBusy(true);
    try {
      setDrafts(await api<StudioSummary[]>("/studio/courses"));
      setDialog("import");
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function openRemove() {
    setError(null);
    setBusy(true);
    try {
      setCatalog(await api<CourseSummary[]>("/courses"));
      setDialog("remove");
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function importDraft(draft: StudioSummary) {
    setBusy(true);
    setError(null);
    try {
      const created = await api<CourseTree>("/courses/import-studio", {
        method: "POST",
        body: JSON.stringify({ studio_course_id: draft.id }),
      });
      setDialog(null);
      await refreshCourses(created.id);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeCourse(course: CourseSummary) {
    setBusy(true);
    setError(null);
    try {
      await api(`/courses/${course.id}/remove`, { method: "POST" });
      setDialog(null);
      await refreshCourses(tree?.id === course.id ? undefined : tree?.id);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  function toggle(code: string) {
    setOpen((current) => (current.includes(code) ? current.filter((item) => item !== code) : [...current, code]));
  }

  return (
    <AdminFrame
      current="lessons"
      sidebar={
        <>
          <div className="ds-file-row">
            <button type="button" className="button" disabled={busy} onClick={() => void openImport()}>
              Import course
            </button>
            <button type="button" className="ghost" disabled={busy} onClick={() => void openRemove()}>
              Remove course
            </button>
          </div>
          <p className="ds-quiet">Import copies a Create course draft. Remove takes a course out of the catalog and keeps its chats.</p>
          <ul className="ds-list" aria-label="Courses">
            {courses.map((course) => {
              const selected = tree?.id === course.id;
              return (
                <li key={course.id}>
                  <button
                    type="button"
                    className={`ds-row ${selected ? "is-on" : ""}`}
                    onClick={() => void openCourse(course.id)}
                  >
                    <strong>{course.title}</strong>
                    <small>
                      {course.code} · {course.audience || "any age"} · {course.quest_count} quests
                    </small>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      }
    >
      {error ? (
        <div className="banner" role="alert" style={{ margin: 18 }}>
          <p>{error}</p>
        </div>
      ) : null}
      {tree ? (
        <article className="editor">
          <header className="studio-prefs">
            <div className="studio-prefs-head">
              <div className="studio-prefs-title">
                <h2>
                  <span className="studio-code">{tree.code}</span>
                  {tree.title}
                </h2>
                <p className="studio-pref-summary">{tree.description || "No description yet."}</p>
                <p className="help">
                  {tree.quest_count} quests · {tree.goals_per_quest} goals per quest · {tree.quiz_minutes} minutes
                  before the quiz · Ages {tree.audience}
                </p>
              </div>
            </div>
          </header>
          {tree.quests.length === 0 ? <p className="ds-quiet">No quests yet.</p> : null}
          <ul className="studio-tree-list" aria-label="Course">
            {tree.quests.map((quest) => (
              <QuestBranch
                key={quest.id}
                quest={quest}
                open={open.includes(quest.code)}
                onToggle={() => toggle(quest.code)}
              />
            ))}
          </ul>
        </article>
      ) : (
        <article className="editor">
          <h2>Course tree</h2>
          <p className="help">Import a Create course draft to put it in the kid catalog.</p>
        </article>
      )}
      {dialog === "import" ? (
        <Picker
          title="Import course"
          note="Choosing a draft copies it into the kid catalog. The Create course original stays."
          empty="No saved drafts."
          rows={drafts.map((draft) => ({ id: draft.id, title: draft.title, code: draft.code }))}
          busy={busy}
          onClose={() => setDialog(null)}
          onChoose={(id) => {
            const draft = drafts.find((row) => row.id === id);
            if (draft) void importDraft(draft);
          }}
        />
      ) : null}
      {dialog === "remove" ? (
        <Picker
          title="Remove course"
          note="Choosing a course removes it from the catalog. Kid chat history for that course is kept."
          empty="No courses in the catalog."
          rows={catalog.map((course) => ({ id: course.id, title: course.title, code: course.code }))}
          busy={busy}
          onClose={() => setDialog(null)}
          onChoose={(id) => {
            const course = catalog.find((row) => row.id === id);
            if (course) void removeCourse(course);
          }}
        />
      ) : null}
    </AdminFrame>
  );
}

function QuestBranch({
  quest,
  open,
  onToggle,
}: {
  quest: CatalogQuest;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <li>
      <button type="button" className="studio-tier-row" aria-expanded={open} onClick={onToggle}>
        <span className="studio-code">{quest.code}</span>
        <span className="studio-title">{quest.title}</span>
      </button>
      {open ? (
        <div>
          {quest.goals.length === 0 ? <p className="ds-quiet">No goals yet.</p> : null}
          {quest.goals.map((goal) => (
            <div key={goal.position} className="studio-goal-row">
              <p className="studio-fact">
                <span>Goal {goal.position}</span>
                {goal.learning_goal || "No learning goal yet"}
              </p>
              <p className="studio-fact">
                <span>Success criterion</span>
                {goal.success_criterion || "No success criterion yet"}
              </p>
            </div>
          ))}
          <p className="studio-fact">
            <span>Close</span>
            {closeLabel(quest.close)}
          </p>
          {(quest.close?.questions ?? []).map((item, index) => (
            <div key={`${quest.code}-question-${index}`} className="studio-goal-row">
              <p className="studio-fact">
                <span>Question {index + 1}</span>
                {item.text}
              </p>
              {item.choices?.length ? (
                <ul className="studio-choices">
                  {item.choices.map((choice) => (
                    <li key={choice.text}>{choice.correct ? `${choice.text} (correct)` : choice.text}</li>
                  ))}
                </ul>
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
        </div>
      ) : null}
    </li>
  );
}

function Picker({
  title,
  note,
  empty,
  rows,
  busy,
  onClose,
  onChoose,
}: {
  title: string;
  note: string;
  empty: string;
  rows: { id: string; title: string; code: string }[];
  busy: boolean;
  onClose: () => void;
  onChoose: (id: string) => void;
}) {
  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="prompt-dialog settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="catalog-picker-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="catalog-picker-title">{title}</h2>
            <p>{note}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="prompt-body">
          <ul className="studio-manage-list" aria-label={title}>
            {rows.length === 0 ? <li className="ds-quiet">{empty}</li> : null}
            {rows.map((row) => (
              <li key={row.id}>
                <button type="button" className="ds-row" disabled={busy} onClick={() => onChoose(row.id)}>
                  <strong>{row.title}</strong>
                  <small>{row.code}</small>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
