"use client";

import { useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { api } from "@/lib/api";
import type {
  BeatOut,
  Competency,
  CourseSummary,
  CourseTree,
  HintLadder,
  QuestDetail,
  QuizInput,
  RubricRowInput,
  TrapInput,
  UnitNode,
} from "@/lib/types";

const ROLES = ["mystery_hook", "interactive_toy", "diagnostic_gate", "feynman_flip"] as const;
const ROLE_LABEL: Record<string, string> = {
  mystery_hook: "Mystery hook",
  interactive_toy: "Interactive toy",
  diagnostic_gate: "Diagnostic gate",
  feynman_flip: "Feynman flip",
};
const BLOOMS = ["remember", "understand", "apply", "analyze", "evaluate", "create"];
const LOADS = ["low", "medium", "high"];
const BANDS = ["6-8", "9-11", "12-14", "15-17"];

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function emptyChoice() {
  return { id: "", text: "", misconception: "" };
}

function widgetFrom(beat: BeatOut): QuizInput | null {
  const widget = beat.widget;
  if (!widget) return null;
  return {
    type: widget.type === "flaw" || widget.type === "order" ? widget.type : "single",
    prompt: widget.prompt ?? "",
    choices: (widget.choices ?? []).map((choice) => ({
      id: choice.id ?? "",
      text: choice.text ?? "",
      misconception: choice.misconception ?? "",
    })),
    answer: widget.answer ?? (widget.type === "order" ? [] : ""),
    explain: Boolean(widget.explain),
    misconception: widget.misconception ?? "",
  };
}

function answerText(answer: string | string[]) {
  return Array.isArray(answer) ? answer.join(", ") : answer;
}

type BeatDraft = {
  role: string;
  bloom_level: string;
  cognitive_load: string;
  prompt: string;
  rubric: RubricRowInput[];
  misconception_map: TrapInput[];
  hint_ladder: HintLadder;
  widget: QuizInput | null;
  useWidget: boolean;
};

function draftBeat(beat: BeatOut, index: number): BeatDraft {
  const role = ROLES[index] ?? beat.role;
  const widget = role === "mystery_hook" || role === "feynman_flip" ? null : widgetFrom(beat);
  return {
    role,
    bloom_level: beat.bloom_level || "understand",
    cognitive_load: beat.cognitive_load || "medium",
    prompt: beat.prompt ?? "",
    rubric: (beat.rubric ?? []).map((row) => ({ id: row.id, text: row.text, weight: row.weight })),
    misconception_map: (beat.misconception_map ?? []).map((trap) => ({
      id: trap.id,
      trap: trap.trap,
      note: trap.note,
    })),
    hint_ladder: {
      nudge: beat.hint_ladder?.nudge ?? "",
      analogy: beat.hint_ladder?.analogy ?? "",
      scaffold: beat.hint_ladder?.scaffold ?? "",
    },
    widget,
    useWidget: role === "interactive_toy" || widget != null,
  };
}

function payloadBeat(draft: BeatDraft) {
  let widget: QuizInput | null = null;
  if (draft.role === "interactive_toy" || (draft.role === "diagnostic_gate" && draft.useWidget && draft.widget)) {
    const source = draft.widget ?? {
      type: "single" as const,
      prompt: draft.prompt,
      choices: [emptyChoice(), emptyChoice()],
      answer: "",
      explain: false,
      misconception: "",
    };
    const answer =
      source.type === "order"
        ? answerText(source.answer)
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean)
        : answerText(source.answer).trim();
    widget = { ...source, answer };
  }
  return {
    role: draft.role,
    bloom_level: draft.bloom_level,
    cognitive_load: draft.cognitive_load,
    prompt: draft.prompt,
    rubric: draft.rubric,
    misconception_map: draft.misconception_map,
    hint_ladder: draft.hint_ladder,
    widget,
  };
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
  const [openUnits, setOpenUnits] = useState<string[]>(initialTree?.units.map((unit) => unit.id) ?? []);
  const [quest, setQuest] = useState<QuestDetail | null>(null);
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);

  async function refreshCourses(selectId?: string) {
    const next = await api<CourseSummary[]>("/courses");
    setCourses(next);
    const id = selectId ?? tree?.id ?? next[0]?.id ?? null;
    if (!id) {
      setTree(null);
      setQuest(null);
      return;
    }
    const loaded = await api<CourseTree>(`/courses/${id}`);
    setTree(loaded);
    setOpenUnits(loaded.units.map((unit) => unit.id));
  }

  async function openCourse(courseId: string) {
    setError(null);
    setQuest(null);
    try {
      const loaded = await api<CourseTree>(`/courses/${courseId}`);
      setTree(loaded);
      setOpenUnits(loaded.units.map((unit) => unit.id));
    } catch (err) {
      setError(messageOf(err));
    }
  }

  async function openQuest(questId: string) {
    setError(null);
    try {
      setQuest(await api<QuestDetail>(`/quests/${questId}`));
    } catch (err) {
      setError(messageOf(err));
    }
  }

  async function createCourse() {
    setBusy(true);
    setError(null);
    try {
      const created = await api<CourseTree>("/courses", {
        method: "POST",
        body: JSON.stringify({ title: "New course", age_band: "9-11", standards_alignment: "" }),
      });
      await refreshCourses(created.id);
      setQuest(null);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function importFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const text = await file.text();
      const payload = JSON.parse(text) as unknown;
      const created = await api<CourseTree>("/courses/import", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refreshCourses(created.id);
      setQuest(null);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function exportCourse() {
    if (!tree) return;
    setError(null);
    try {
      const file = await api<unknown>(`/courses/${tree.id}/export`);
      const blob = new Blob([JSON.stringify(file, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${tree.code}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(messageOf(err));
    }
  }

  return (
    <AdminFrame
      current="lessons"
      sidebar={
        <>
        <button type="button" className="ds-new" disabled={busy} onClick={() => void createCourse()}>
          <span aria-hidden="true">+</span>
          New course
        </button>
        <div className="ds-file-row">
          <label className="ds-file">
            Import course
            <input
              type="file"
              accept="application/json,.json"
              aria-label="Import a course file"
              disabled={busy}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void importFile(file);
              }}
            />
          </label>
          <button type="button" className="ghost" disabled={!tree || busy} onClick={() => void exportCourse()}>
            Export course
          </button>
        </div>
        <p className="ds-quiet">One file is one course. Upload replaces that course code.</p>
        <ul className="ds-list" aria-label="Courses">
          {courses.map((course) => {
            const open = tree?.id === course.id;
            return (
              <li key={course.id}>
                <button
                  type="button"
                  className={`ds-row ${open && !quest ? "is-on" : ""}`}
                  onClick={() => void openCourse(course.id)}
                >
                  <strong>{course.title}</strong>
                  <small>
                    {course.code} · ages {course.age_band} · {course.quest_count} quests
                  </small>
                </button>
                {open && tree ? (
                  <ul className="ds-tree">
                    {tree.units.map((unit) => (
                      <UnitBranch
                        key={unit.id}
                        unit={unit}
                        open={openUnits.includes(unit.id)}
                        activeQuestId={quest?.id ?? null}
                        onToggle={() =>
                          setOpenUnits((current) =>
                            current.includes(unit.id)
                              ? current.filter((id) => id !== unit.id)
                              : [...current, unit.id],
                          )
                        }
                        onQuest={(questId) => void openQuest(questId)}
                      />
                    ))}
                  </ul>
                ) : null}
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
        {quest ? (
          <QuestEditor
            key={quest.id}
            quest={quest}
            onChange={setQuest}
            onClose={() => setQuest(null)}
            onError={setError}
            onSaved={async () => {
              if (tree) await refreshCourses(tree.id);
            }}
          />
        ) : tree ? (
          <CourseEditor
            key={tree.id}
            tree={tree}
            onChange={(next) => {
              setTree(next);
              setCourses((current) =>
                current.map((item) =>
                  item.id === next.id
                    ? {
                        ...item,
                        code: next.code,
                        title: next.title,
                        age_band: next.age_band,
                        standards_alignment: next.standards_alignment,
                        unit_count: next.units.length,
                        quest_count: next.units.reduce((sum, unit) => sum + unit.quests.length, 0),
                      }
                    : item,
                ),
              );
            }}
            onError={setError}
            onDeleted={async () => {
              setTree(null);
              setQuest(null);
              await refreshCourses();
            }}
          />
        ) : (
          <article className="editor">
            <h2>Course tree</h2>
            <p className="help">Import a course file, or add a course, then open a quest to edit its four beats.</p>
          </article>
        )}
    </AdminFrame>
  );
}

function UnitBranch({
  unit,
  open,
  activeQuestId,
  onToggle,
  onQuest,
}: {
  unit: UnitNode;
  open: boolean;
  activeQuestId: string | null;
  onToggle: () => void;
  onQuest: (questId: string) => void;
}) {
  return (
    <li>
      <button type="button" className="ds-row ds-indent" aria-expanded={open} onClick={onToggle}>
        <strong>
          Unit {unit.number}. {unit.title}
        </strong>
        <small>{unit.quests.length} quests</small>
      </button>
      {open ? (
        <ul>
          {unit.quests.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`ds-row ds-indent-2 ${item.id === activeQuestId ? "is-on" : ""}`}
                onClick={() => onQuest(item.id)}
              >
                <strong>{item.title}</strong>
                <small>
                  {item.code} · {item.quest_type}
                </small>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function CourseEditor({
  tree,
  onChange,
  onError,
  onDeleted,
}: {
  tree: CourseTree;
  onChange: (tree: CourseTree) => void;
  onError: (message: string | null) => void;
  onDeleted: () => Promise<void>;
}) {
  const [draft, setDraft] = useState(tree);
  const [unitTitle, setUnitTitle] = useState("");
  const current = draft.id === tree.id ? draft : tree;

  async function saveCourse() {
    onError(null);
    try {
      const next = await api<CourseTree>(`/courses/${tree.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: current.title,
          code: current.code,
          age_band: current.age_band,
          standards_alignment: current.standards_alignment,
          competency_dictionary: current.competency_dictionary,
        }),
      });
      setDraft(next);
      onChange(next);
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function addUnit() {
    const title = unitTitle.trim();
    if (!title) return;
    onError(null);
    try {
      const next = await api<CourseTree>(`/courses/${tree.id}/units`, {
        method: "POST",
        body: JSON.stringify({
          title,
          enduring_understanding: "Students can explain the idea this unit is built around.",
          continuity_summary: "This unit carries an idea forward. The next quest uses that idea.",
        }),
      });
      setUnitTitle("");
      setDraft(next);
      onChange(next);
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function removeCourse() {
    onError(null);
    try {
      await api(`/courses/${tree.id}`, { method: "DELETE" });
      await onDeleted();
    } catch (err) {
      onError(messageOf(err));
    }
  }

  function setCompetency(index: number, patch: Partial<Competency>) {
    const competency_dictionary = current.competency_dictionary.map((item, itemIndex) =>
      itemIndex === index ? { ...item, ...patch } : item,
    );
    setDraft({ ...current, competency_dictionary });
  }

  return (
    <article className="editor">
      <p className="eyebrow">Tier 1 course</p>
      <h2>{tree.title}</h2>
      <div className="split">
        <label>
          Title
          <input value={current.title} onChange={(event) => setDraft({ ...current, title: event.target.value })} />
        </label>
        <label>
          Code
          <input value={current.code} onChange={(event) => setDraft({ ...current, code: event.target.value })} />
        </label>
      </div>
      <label>
        Age band
        <select value={current.age_band} onChange={(event) => setDraft({ ...current, age_band: event.target.value })}>
          {BANDS.map((band) => (
            <option key={band} value={band}>{band}</option>
          ))}
        </select>
      </label>
      <label>
        Standards alignment
        <textarea
          value={current.standards_alignment}
          onChange={(event) => setDraft({ ...current, standards_alignment: event.target.value })}
        />
      </label>
      <h3>Competency dictionary</h3>
      {current.competency_dictionary.map((item, index) => (
        <div className="split" key={`${item.code}-${index}`}>
          <label>
            Code
            <input value={item.code} onChange={(event) => setCompetency(index, { code: event.target.value })} />
          </label>
          <label>
            Description
            <input
              value={item.description}
              onChange={(event) => setCompetency(index, { description: event.target.value })}
            />
          </label>
        </div>
      ))}
      <button
        type="button"
        className="ghost"
        onClick={() =>
          setDraft({
            ...current,
            competency_dictionary: [...current.competency_dictionary, { code: "", description: "" }],
          })
        }
      >
        Add competency
      </button>
      <div className="rail-actions">
        <button type="button" className="button" onClick={() => void saveCourse()}>Save course</button>
        <button type="button" className="ghost" onClick={() => void removeCourse()}>Delete course</button>
      </div>
      <h3>Add a unit</h3>
      <div className="split">
        <label>
          Unit title
          <input value={unitTitle} onChange={(event) => setUnitTitle(event.target.value)} />
        </label>
        <button type="button" className="button" onClick={() => void addUnit()}>Add unit</button>
      </div>
      <p className="help">Open a quest in the tree to edit its four beats, rubric, hints, and widget.</p>
    </article>
  );
}

function QuestEditor({
  quest,
  onChange,
  onClose,
  onError,
  onSaved,
}: {
  quest: QuestDetail;
  onChange: (quest: QuestDetail) => void;
  onClose: () => void;
  onError: (message: string | null) => void;
  onSaved: () => Promise<void>;
}) {
  const [meta, setMeta] = useState(quest);
  const [beats, setBeats] = useState<BeatDraft[]>(() => {
    const ordered = [...quest.beats].sort((left, right) => left.position - right.position);
    return ROLES.map((role, index) => draftBeat(ordered[index] ?? ordered.find((beat) => beat.role === role) ?? ordered[0], index));
  });
  const shown = meta.id === quest.id ? meta : quest;

  function setBeat(index: number, patch: Partial<BeatDraft>) {
    setBeats((current) => current.map((beat, beatIndex) => (beatIndex === index ? { ...beat, ...patch } : beat)));
  }

  async function saveMeta() {
    onError(null);
    try {
      const next = await api<QuestDetail>(`/quests/${quest.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: shown.title,
          code: shown.code,
          quest_type: shown.quest_type,
          prerequisite_codes: shown.prerequisite_codes,
          competency_tags: shown.competency_tags,
          dinner_prompt: shown.dinner_prompt,
        }),
      });
      setMeta(next);
      onChange(next);
      await onSaved();
    } catch (err) {
      onError(messageOf(err));
    }
  }

  async function saveBeats() {
    onError(null);
    try {
      const next = await api<QuestDetail>(`/quests/${quest.id}/beats`, {
        method: "PUT",
        body: JSON.stringify({ beats: beats.map(payloadBeat) }),
      });
      setMeta(next);
      setBeats(ROLES.map((role, index) => draftBeat(next.beats[index], index)));
      onChange(next);
    } catch (err) {
      onError(messageOf(err));
    }
  }

  return (
    <article className="editor">
      <p className="eyebrow">Tier 3 quest</p>
      <h2>{quest.title}</h2>
      <button type="button" className="ghost" onClick={onClose}>Back to course</button>
      <div className="split">
        <label>
          Title
          <input value={shown.title} onChange={(event) => setMeta({ ...shown, title: event.target.value })} />
        </label>
        <label>
          Code
          <input value={shown.code} onChange={(event) => setMeta({ ...shown, code: event.target.value })} />
        </label>
      </div>
      <label>
        Type
        <select
          value={shown.quest_type}
          onChange={(event) => setMeta({ ...shown, quest_type: event.target.value })}
        >
          <option value="core">core</option>
          <option value="branch">branch</option>
          <option value="capstone">capstone</option>
        </select>
      </label>
      <label>
        Prerequisite quest codes
        <input
          value={shown.prerequisite_codes.join(", ")}
          onChange={(event) =>
            setMeta({
              ...shown,
              prerequisite_codes: event.target.value.split(",").map((item) => item.trim()).filter(Boolean),
            })
          }
        />
      </label>
      <label>
        Competency tags
        <input
          value={shown.competency_tags.join(", ")}
          onChange={(event) =>
            setMeta({
              ...shown,
              competency_tags: event.target.value.split(",").map((item) => item.trim()).filter(Boolean),
            })
          }
        />
      </label>
      <label>
        Parent dinner-table prompt
        <textarea
          value={shown.dinner_prompt}
          onChange={(event) => setMeta({ ...shown, dinner_prompt: event.target.value })}
        />
      </label>
      <p className="help">The dinner-table prompt is stored only. It is not sent to the child.</p>
      <button type="button" className="button" onClick={() => void saveMeta()}>Save quest</button>
      <h3>Four beats</h3>
      {beats.map((beat, index) => (
        <BeatFields key={beat.role} beat={beat} onChange={(patch) => setBeat(index, patch)} />
      ))}
      <button type="button" className="button" onClick={() => void saveBeats()}>Save beats</button>
    </article>
  );
}

function BeatFields({ beat, onChange }: { beat: BeatDraft; onChange: (patch: Partial<BeatDraft>) => void }) {
  const typed = beat.role === "mystery_hook" || beat.role === "feynman_flip";
  return (
    <fieldset className="beat-fields">
      <legend>{ROLE_LABEL[beat.role] ?? beat.role}</legend>
      <div className="split">
        <label>
          Bloom level
          <select value={beat.bloom_level} onChange={(event) => onChange({ bloom_level: event.target.value })}>
            {BLOOMS.map((level) => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
        </label>
        <label>
          Cognitive load
          <select value={beat.cognitive_load} onChange={(event) => onChange({ cognitive_load: event.target.value })}>
            {LOADS.map((load) => (
              <option key={load} value={load}>{load}</option>
            ))}
          </select>
        </label>
      </div>
      <label>
        Prompt
        <textarea value={beat.prompt} onChange={(event) => onChange({ prompt: event.target.value })} />
      </label>
      <h4>Rubric</h4>
      {beat.rubric.map((row, index) => (
        <div className="split" key={`${beat.role}-rubric-${index}`}>
          <label>
            Id
            <input
              value={row.id}
              onChange={(event) => {
                const rubric = beat.rubric.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, id: event.target.value } : item,
                );
                onChange({ rubric });
              }}
            />
          </label>
          <label>
            Text
            <input
              value={row.text}
              onChange={(event) => {
                const rubric = beat.rubric.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, text: event.target.value } : item,
                );
                onChange({ rubric });
              }}
            />
          </label>
          <label>
            Weight
            <input
              type="number"
              min={0}
              max={100}
              value={row.weight}
              onChange={(event) => {
                const rubric = beat.rubric.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, weight: Number(event.target.value) } : item,
                );
                onChange({ rubric });
              }}
            />
          </label>
        </div>
      ))}
      <h4>Misconception map</h4>
      {beat.misconception_map.map((trap, index) => (
        <div className="split" key={`${beat.role}-trap-${index}`}>
          <label>
            Id
            <input
              value={trap.id}
              onChange={(event) => {
                const misconception_map = beat.misconception_map.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, id: event.target.value } : item,
                );
                onChange({ misconception_map });
              }}
            />
          </label>
          <label>
            Trap
            <input
              value={trap.trap}
              onChange={(event) => {
                const misconception_map = beat.misconception_map.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, trap: event.target.value } : item,
                );
                onChange({ misconception_map });
              }}
            />
          </label>
          <label>
            Note
            <input
              value={trap.note}
              onChange={(event) => {
                const misconception_map = beat.misconception_map.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, note: event.target.value } : item,
                );
                onChange({ misconception_map });
              }}
            />
          </label>
        </div>
      ))}
      <h4>Hint ladder</h4>
      <label>
        Nudge
        <input
          value={beat.hint_ladder.nudge}
          onChange={(event) => onChange({ hint_ladder: { ...beat.hint_ladder, nudge: event.target.value } })}
        />
      </label>
      <label>
        Analogy
        <input
          value={beat.hint_ladder.analogy}
          onChange={(event) => onChange({ hint_ladder: { ...beat.hint_ladder, analogy: event.target.value } })}
        />
      </label>
      <label>
        Scaffold
        <input
          value={beat.hint_ladder.scaffold}
          onChange={(event) => onChange({ hint_ladder: { ...beat.hint_ladder, scaffold: event.target.value } })}
        />
      </label>
      {typed ? <p className="help">This beat stays a typed reply.</p> : (
        <WidgetFields beat={beat} onChange={onChange} />
      )}
    </fieldset>
  );
}

function WidgetFields({ beat, onChange }: { beat: BeatDraft; onChange: (patch: Partial<BeatDraft>) => void }) {
  const optional = beat.role === "diagnostic_gate";
  const widget = beat.widget ?? {
    type: "single" as const,
    prompt: "",
    choices: [emptyChoice(), emptyChoice()],
    answer: "",
    explain: false,
    misconception: "",
  };
  function setWidget(patch: Partial<QuizInput>) {
    onChange({ widget: { ...widget, ...patch }, useWidget: true });
  }
  return (
    <div>
      <h4>Widget</h4>
      {optional ? (
        <label className="check">
          <input
            type="checkbox"
            checked={beat.useWidget}
            onChange={(event) => onChange({ useWidget: event.target.checked, widget: event.target.checked ? widget : null })}
          />
          Use a widget on this gate
        </label>
      ) : null}
      {beat.useWidget || beat.role === "interactive_toy" ? (
        <>
          <label>
            Widget type
            <select
              value={widget.type}
              onChange={(event) => setWidget({ type: event.target.value as QuizInput["type"] })}
            >
              <option value="single">misconception MCQ</option>
              <option value="flaw">spot the flaw</option>
              <option value="order">ordering</option>
            </select>
          </label>
          <label>
            Widget prompt
            <textarea value={widget.prompt} onChange={(event) => setWidget({ prompt: event.target.value })} />
          </label>
          {widget.choices.map((choice, index) => (
            <div className="split" key={`${beat.role}-choice-${index}`}>
              <label>
                Choice id
                <input
                  value={choice.id}
                  onChange={(event) => {
                    const choices = widget.choices.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, id: event.target.value } : item,
                    );
                    setWidget({ choices });
                  }}
                />
              </label>
              <label>
                Choice text
                <input
                  value={choice.text}
                  onChange={(event) => {
                    const choices = widget.choices.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, text: event.target.value } : item,
                    );
                    setWidget({ choices });
                  }}
                />
              </label>
              <label>
                Misconception
                <input
                  value={choice.misconception}
                  onChange={(event) => {
                    const choices = widget.choices.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, misconception: event.target.value } : item,
                    );
                    setWidget({ choices });
                  }}
                />
              </label>
            </div>
          ))}
          <label>
            Answer
            <input
              value={answerText(widget.answer)}
              onChange={(event) => setWidget({ answer: event.target.value })}
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={widget.explain}
              onChange={(event) => setWidget({ explain: event.target.checked })}
            />
            Ask for a short explanation
          </label>
          <label>
            Widget misconception
            <input
              value={widget.misconception}
              onChange={(event) => setWidget({ misconception: event.target.value })}
            />
          </label>
        </>
      ) : (
        <p className="help">This gate stays a typed reply until you turn the widget on.</p>
      )}
    </div>
  );
}
