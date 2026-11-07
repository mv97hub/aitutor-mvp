"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { KcBanner } from "@/components/KcBanner";
import { KcDebugPanel } from "@/components/KcDebugPanel";
import { ChoiceWidget } from "@/components/LessonBlocks";
import { api } from "@/lib/api";
import type { KcDebugVariable, KcProgress, KcTutorCourse, KcTutorSession } from "@/lib/kc";
import type { KcDebugTurn } from "@/lib/kc-debug";
import { hoverFor } from "@/lib/kc-layer-fields";
import { KC_MODELS, kcModel, type KcModel } from "@/lib/kc-models";
import type { KidQuiz, ProfileDefaults, Student } from "@/lib/types";
import { useRouter } from "next/navigation";

type SettingsDraft = {
  model: KcModel;
  age: string;
  reading_level: string;
  modality: string;
  interests: string;
};

function tutorPath(parts: { student?: string; course?: string; kc?: string; session?: string; model?: string }) {
  const params = new URLSearchParams();
  if (parts.student) params.set("student", parts.student);
  if (parts.course) params.set("course", parts.course);
  if (parts.kc) params.set("kc", parts.kc);
  if (parts.session) params.set("session", parts.session);
  if (parts.model) params.set("model", parts.model);
  const query = params.toString();
  return query ? `/kc-tutor?${query}` : "/kc-tutor";
}

function settingsDraft(learner: Student | null, model: string): SettingsDraft {
  return {
    model: kcModel(model),
    age: learner?.age == null ? "" : String(learner.age),
    reading_level: learner?.reading_level ?? "",
    modality: learner?.modality ?? "",
    interests: learner?.interests.join(", ") ?? "",
  };
}

const ADD_NEW_CHILD = "__add_new_child__";

type ChildDraft = {
  name: string;
  age: string;
  reading_level: string;
  modality: string;
  interests: string;
};

function blankChild(): ChildDraft {
  return { name: "", age: "", reading_level: "", modality: "", interests: "" };
}

function childCreateBody(draft: ChildDraft) {
  const body: {
    display_name: string;
    age: number;
    reading_level?: string;
    modality?: string;
    interests?: string[];
  } = {
    display_name: draft.name.trim(),
    age: Number(draft.age),
  };
  const readingLevel = draft.reading_level.trim();
  const modality = draft.modality.trim();
  const interests = draft.interests
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (readingLevel) body.reading_level = readingLevel;
  if (modality) body.modality = modality;
  if (interests.length > 0) body.interests = interests;
  return body;
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

export function KcTutor({
  students,
  courses,
  studentId,
  courseId,
  kcId,
  model,
  progress,
  session,
  error,
  variables,
  turns,
}: {
  students: Student[];
  courses: KcTutorCourse[];
  studentId: string;
  courseId: string;
  kcId: string;
  model: string;
  progress: KcProgress | null;
  session: KcTutorSession | null;
  error: string | null;
  variables: KcDebugVariable[];
  turns: KcDebugTurn[];
}) {
  const [debugOpen, setDebugOpen] = useState(false);
  const course = courses.find((item) => item.id === courseId) ?? null;
  const learner = students.find((item) => item.id === studentId) ?? null;
  const router = useRouter();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsNotice, setSettingsNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState<SettingsDraft>(() => settingsDraft(learner, model));
  const [pickedStudent, setPickedStudent] = useState(studentId);
  const [createdStudents, setCreatedStudents] = useState<Student[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const [addKey, setAddKey] = useState(0);
  const [savingChild, setSavingChild] = useState(false);
  const [addNotice, setAddNotice] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);
  const [restartNotice, setRestartNotice] = useState<string | null>(null);
  const roster = students.concat(
    createdStudents.filter((student) => !students.some((row) => row.id === student.id)),
  );

  useEffect(() => {
    setPickedStudent(studentId);
  }, [studentId]);

  function openSettings() {
    setAddOpen(false);
    setDraft(settingsDraft(learner, model));
    setSettingsNotice(null);
    setSettingsOpen(true);
  }

  function openAddChild() {
    setSettingsOpen(false);
    setAddNotice(null);
    setAddKey((key) => key + 1);
    setAddOpen(true);
  }

  async function createChild(child: ChildDraft) {
    const name = child.name.trim();
    const age = Number(child.age);
    if (!name) {
      setAddNotice("Name is required.");
      return;
    }
    if (!Number.isInteger(age) || age < 4 || age > 18) {
      setAddNotice("Age must be from 4 to 18.");
      return;
    }
    setSavingChild(true);
    setAddNotice(null);
    try {
      const student = await api<Student>("/students", {
        method: "POST",
        body: JSON.stringify(childCreateBody({ ...child, name, age: String(age) })),
      });
      setCreatedStudents((rows) => [...rows.filter((row) => row.id !== student.id), student]);
      setPickedStudent(student.id);
      setAddOpen(false);
      router.push(
        tutorPath({
          student: student.id,
          course: courseId || undefined,
          model,
        }),
      );
      router.refresh();
    } catch (err) {
      setAddNotice(err instanceof Error ? err.message : "Could not add that child.");
    } finally {
      setSavingChild(false);
    }
  }

  async function startCourseOver() {
    if (!studentId || !courseId || restarting) return;
    setRestarting(true);
    setRestartNotice(null);
    try {
      const restarted = await api<KcProgress>(`/kc/tutor/courses/${courseId}/restart`, {
        method: "POST",
        body: JSON.stringify({ student_id: studentId }),
      });
      router.push(
        tutorPath({
          student: studentId,
          course: courseId,
          kc: restarted.ring[0]?.id,
          model,
        }),
      );
      router.refresh();
    } catch (err) {
      setRestartNotice(err instanceof Error ? err.message : "Could not start this course over.");
    } finally {
      setRestarting(false);
    }
  }

  function jumpToComponent(kc: string) {
    if (!kc || !studentId || !courseId) return;
    router.push(tutorPath({ student: studentId, course: courseId, kc, model }));
    router.refresh();
  }

  async function saveSettings(event: FormEvent) {
    event.preventDefault();
    setSavingSettings(true);
    setSettingsNotice(null);
    try {
      if (learner) {
        const age = Number(draft.age);
        if (!Number.isInteger(age) || age < 4 || age > 18) {
          setSettingsNotice("Age must be from 4 to 18.");
          return;
        }
        await api<Student>(`/students/${learner.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            age,
            reading_level: draft.reading_level.trim(),
            modality: draft.modality.trim(),
            interests: draft.interests
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
          }),
        });
      }
      const nextModel = kcModel(draft.model);
      setSettingsOpen(false);
      router.push(
        tutorPath({
          student: studentId,
          course: courseId,
          kc: session ? undefined : kcId,
          session: session?.id,
          model: nextModel,
        }),
      );
      router.refresh();
    } catch (err) {
      setSettingsNotice(err instanceof Error ? err.message : "Could not save those settings.");
    } finally {
      setSavingSettings(false);
    }
  }

  const components = progress?.ring ?? [];
  const openKc = session?.kc_id || kcId;
  const jumpValue = components.some((item) => item.id === openKc) ? openKc : "";

  return (
    <main className={`ds-shell kc-screen${debugOpen ? " is-debug" : ""}`}>
      <KcBanner name="KC Tutor">
        <div className="kc-fast">
          <button
            type="button"
            className="button"
            aria-pressed={debugOpen}
            aria-expanded={debugOpen}
            aria-controls="kc-debug-panel"
            onClick={() => setDebugOpen((open) => !open)}
          >
            Debug
          </button>
        </div>
      </KcBanner>
      <aside className="ds-side kc-tutor-side">
        {error && !session ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <form
          className="kc-tutor-pick"
          method="get"
          action="/kc-tutor"
          onSubmit={(event) => {
            if (new FormData(event.currentTarget).get("student") === ADD_NEW_CHILD) {
              event.preventDefault();
              openAddChild();
            }
          }}
        >
          <input type="hidden" name="model" value={model} />
          <label>
            Child
            <select
              aria-label="Choose a child"
              name="student"
              value={pickedStudent}
              onChange={(event) => {
                const next = event.target.value;
                if (next === ADD_NEW_CHILD) {
                  event.currentTarget.value = pickedStudent;
                  openAddChild();
                  return;
                }
                setPickedStudent(next);
              }}
            >
              <option value={ADD_NEW_CHILD}>Add New Child</option>
              <option value="">Choose a child</option>
              {roster.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Course
            <select aria-label="Choose a course" name="course" defaultValue={courseId}>
              <option value="">Choose a ready course</option>
              {courses.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <button className="button" type="submit">
            Open
          </button>
        </form>
        <div className="kc-tutor-pick">
          <button
            className="button"
            type="button"
            onClick={() => void startCourseOver()}
            disabled={!studentId || !courseId || restarting}
          >
            Start Course Over
          </button>
        </div>
        {restartNotice ? (
          <div className="banner" role="alert">
            <p>{restartNotice}</p>
          </div>
        ) : null}
        {progress ? (
          <>
            <Ring progress={progress} />
            {course?.kind === "time_boxed" && progress.minutes ? (
              <p className="kc-minutes">{progress.minutes} minutes</p>
            ) : null}
            <ul className="kc-cards" aria-label="Next work">
              {progress.cards.map((card) => (
                <li key={card.role}>
                  <a href={tutorPath({ student: studentId, course: courseId, kc: card.id, model })}>
                    <span>{card.label}</span>
                    <strong>{card.title}</strong>
                    <small>{card.reason}</small>
                  </a>
                </li>
              ))}
            </ul>
            {progress.cards.length === 0 ? <p className="ds-quiet">Every target component is known.</p> : null}
          </>
        ) : null}
        <div className="ds-foot">
          <button
            type="button"
            className="ds-settings"
            aria-expanded={settingsOpen}
            aria-haspopup="dialog"
            onClick={openSettings}
          >
            <GearIcon />
            Settings
          </button>
          <div className="kc-tutor-pick">
            <label>
              TEST KC Selection
              <select
                aria-label="TEST KC Selection"
                value={jumpValue}
                disabled={!studentId || !courseId || components.length === 0}
                onChange={(event) => jumpToComponent(event.target.value)}
              >
                <option value="">Choose a component</option>
                {components.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        {settingsOpen ? (
          <TutorSettingsDialog
            learner={learner}
            draft={draft}
            saving={savingSettings}
            notice={settingsNotice}
            onChange={setDraft}
            onSubmit={(event) => void saveSettings(event)}
            onClose={() => setSettingsOpen(false)}
          />
        ) : null}
        {addOpen ? (
          <AddChildDialog
            key={addKey}
            saving={savingChild}
            notice={addNotice}
            onCreate={(child) => void createChild(child)}
            onClose={() => setAddOpen(false)}
          />
        ) : null}
      </aside>
      <section className="ds-stage">
        {session ? (
          <header className="ds-header">
            <p className="kc-step">
              {session.title} · {session.recipe} · {session.step_label}
              {session.status === "completed" ? ` · score ${session.score ?? 0}` : ""}
            </p>
          </header>
        ) : null}
        {session?.redirect ? <p className="kc-redirect">Next card: {session.redirect.title}</p> : null}
        {!session ? <div className="ds-empty"><p>A card opens one component.</p></div> : null}
        {session ? (
          <KcLesson
            key={`${session.id}:${session.step}:${session.messages.length}:${session.status}`}
            session={session}
            model={model}
          />
        ) : null}
      </section>
      {debugOpen ? <KcDebugPanel variables={variables} turns={turns} /> : null}
    </main>
  );
}

function KcLesson({
  session,
  model,
}: {
  session: KcTutorSession;
  model: string;
}) {
  const router = useRouter();
  const started = useRef("");
  const [speakError, setSpeakError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [speaking, setSpeaking] = useState(false);
  const [answering, setAnswering] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);
  const [settled, setSettled] = useState<{ ids: string[]; note: string } | null>(null);
  const anchor = [...session.messages].reverse().find((message) => message.role === "assistant");
  const quiz = session.choice ? quizFor(session.choice) : null;
  const choosing = Boolean(quiz) && session.status !== "completed" && !session.needs_speech && !settled;

  useEffect(() => {
    if (!session.needs_speech) return;
    const key = `${session.id}:${session.step}:${session.messages.length}:${attempt}:${model}`;
    if (started.current === key) return;
    started.current = key;
    const controller = new AbortController();
    let cancelled = false;
    setSpeaking(true);
    setSpeakError(null);
    void fetch("/api/kc/tutor/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: session.id, model }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = (await response.text()).trim();
          throw new Error(text || "The tutor could not say this step.");
        }
        if (!cancelled) router.refresh();
      })
      .catch((err: unknown) => {
        if (cancelled || (err instanceof DOMException && err.name === "AbortError")) return;
        setSpeakError(err instanceof Error ? err.message : "The tutor could not say this step.");
      })
      .finally(() => {
        if (!cancelled) setSpeaking(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
      if (started.current === key) started.current = "";
    };
  }, [attempt, model, router, session.id, session.messages.length, session.needs_speech, session.step]);

  async function sendAnswer(answer: string) {
    const cleaned = answer.trim();
    if (!cleaned || answering) return;
    setAnswering(true);
    setReplyError(null);
    try {
      const response = await fetch("/api/kc/tutor/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: session.id, answer: cleaned, model }),
      });
      if (!response.ok) {
        const text = (await response.text()).trim();
        throw new Error(text || "The tutor could not answer.");
      }
      router.refresh();
    } catch (err: unknown) {
      setSettled(null);
      setReplyError(err instanceof Error ? err.message : "The tutor could not answer.");
    } finally {
      setAnswering(false);
    }
  }

  return (
    <>
      <div className="ds-scroll" role="log" aria-live="polite" aria-relevant="additions">
        <div className="ds-column">
          {session.messages.map((message) => (
            <div key={message.id}>
              <div className={`bubble ${message.role === "user" ? "user" : "assistant"}`}>
                <p>{message.content}</p>
              </div>
              {quiz && anchor?.id === message.id ? (
                <article
                  className="bubble assistant widget-message"
                  aria-label={settled ? "Your choice" : "Choose an answer"}
                >
                  <ChoiceWidget
                    quiz={quiz}
                    busy={answering}
                    settled={settled}
                    onSubmit={(choice, explanation, transcript) => {
                      const ids = Array.isArray(choice) ? choice : [choice];
                      setSettled({ ids, note: explanation });
                      void sendAnswer(transcript);
                    }}
                  />
                </article>
              ) : null}
            </div>
          ))}
        </div>
      </div>
      {speaking ? <p className="ds-typing">Tutor is writing…</p> : null}
      {speakError ? (
        <div className="banner" role="alert">
          <p>{speakError}</p>
          <button type="button" className="ghost" onClick={() => setAttempt((value) => value + 1)}>
            Try again
          </button>
        </div>
      ) : null}
      {replyError ? (
        <div className="banner" role="alert">
          <p>{replyError}</p>
        </div>
      ) : null}
      {session.status === "completed" || session.needs_speech ? null : (
        <form
          className="ds-composer-seat"
          onSubmit={(event) => {
            event.preventDefault();
            if (choosing || answering) return;
            const data = new FormData(event.currentTarget);
            void sendAnswer(String(data.get("answer") || ""));
          }}
        >
          <div className="ds-card">
            <textarea
              className="ds-draft"
              name="answer"
              rows={1}
              required={!choosing}
              placeholder={choosing ? "Choose an answer above" : "Message"}
              aria-label="Your answer"
              disabled={choosing || answering}
              maxLength={2000}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (!choosing) event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <div className="ds-card-row">
              <button className="ds-send" type="submit" aria-label="Send" disabled={choosing || answering}>
                ↑
              </button>
            </div>
          </div>
        </form>
      )}
    </>
  );
}

function AddChildDialog({
  saving,
  notice,
  onCreate,
  onClose,
}: {
  saving: boolean;
  notice: string | null;
  onCreate: (draft: ChildDraft) => void;
  onClose: () => void;
}) {
  const nameRef = useRef<HTMLInputElement>(null);
  const readingTouched = useRef(false);
  const modalityTouched = useRef(false);
  const [draft, setDraft] = useState<ChildDraft>(blankChild);

  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    const age = Number(draft.age);
    if (!Number.isInteger(age) || age < 4 || age > 18) return;
    if (readingTouched.current && modalityTouched.current) return;
    let cancelled = false;
    void api<ProfileDefaults>(`/profile-defaults?age=${age}`)
      .then((defaults) => {
        if (cancelled) return;
        setDraft((current) => {
          if (current.age !== draft.age) return current;
          return {
            ...current,
            reading_level: readingTouched.current ? current.reading_level : defaults.reading_level,
            modality: modalityTouched.current ? current.modality : defaults.modality,
          };
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [draft.age]);

  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="prompt-dialog settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="kc-add-child-title"
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="kc-add-child-title">Add New Child</h2>
            <p>Name, age, reading level, modality, and interests.</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Close
          </button>
        </header>
        <form
          className="prompt-body"
          onSubmit={(event) => {
            event.preventDefault();
            onCreate(draft);
          }}
        >
          <label>
            Name
            <input
              ref={nameRef}
              value={draft.name}
              onChange={(event) => {
                const name = event.target.value;
                setDraft((current) => ({ ...current, name }));
              }}
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
              value={draft.age}
              onChange={(event) => {
                const age = event.target.value;
                setDraft((current) => ({ ...current, age }));
              }}
            />
          </label>
          <label>
            Reading level
            <input
              maxLength={80}
              value={draft.reading_level}
              onChange={(event) => {
                readingTouched.current = true;
                const reading_level = event.target.value;
                setDraft((current) => ({ ...current, reading_level }));
              }}
            />
          </label>
          <label>
            Modality
            <input
              maxLength={80}
              value={draft.modality}
              onChange={(event) => {
                modalityTouched.current = true;
                const modality = event.target.value;
                setDraft((current) => ({ ...current, modality }));
              }}
            />
          </label>
          <label>
            Interests
            <input
              value={draft.interests}
              placeholder="cities, fairness"
              onChange={(event) => {
                const interests = event.target.value;
                setDraft((current) => ({ ...current, interests }));
              }}
            />
          </label>
          <p className="help">
            Age, reading level, modality, and interests are saved on the child. A blank reading level or modality
            keeps the age default. Persona and the other tutor settings stay on Agent customizations.
          </p>
          {notice ? (
            <div className="banner" role="alert">
              <p>{notice}</p>
            </div>
          ) : null}
          <div className="rail-actions">
            <button className="button" type="submit" disabled={saving}>
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function TutorSettingsDialog({
  learner,
  draft,
  saving,
  notice,
  onChange,
  onSubmit,
  onClose,
}: {
  learner: Student | null;
  draft: SettingsDraft;
  saving: boolean;
  notice: string | null;
  onChange: (next: SettingsDraft) => void;
  onSubmit: (event: FormEvent) => void;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const subtitle = learner
    ? learner.age == null
      ? learner.display_name
      : `${learner.display_name} · age ${learner.age}`
    : "Choose a child to edit age, reading level, modality, and interests.";

  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        ref={panelRef}
        className="prompt-dialog settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="kc-tutor-settings-title"
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="kc-tutor-settings-title">Settings</h2>
            <p>{subtitle}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Close
          </button>
        </header>
        <form className="prompt-body" onSubmit={onSubmit}>
          <label title={hoverFor("Model")}>
            Model
            <select
              aria-label="Model"
              title={hoverFor("Model")}
              value={draft.model}
              onChange={(event) => onChange({ ...draft, model: kcModel(event.target.value) })}
            >
              {KC_MODELS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          {learner ? (
            <>
              <label title={hoverFor("Display name")}>
                Display name
                <input value={learner.display_name} title={hoverFor("Display name")} disabled readOnly />
              </label>
              <label title={hoverFor("Age")}>
                Age
                <input
                  type="number"
                  min={4}
                  max={18}
                  required
                  title={hoverFor("Age")}
                  value={draft.age}
                  onChange={(event) => onChange({ ...draft, age: event.target.value })}
                />
              </label>
              <label title={hoverFor("Reading level")}>
                Reading level
                <input
                  maxLength={80}
                  title={hoverFor("Reading level")}
                  value={draft.reading_level}
                  onChange={(event) => onChange({ ...draft, reading_level: event.target.value })}
                />
              </label>
              <label title={hoverFor("Modality")}>
                Modality
                <input
                  maxLength={80}
                  title={hoverFor("Modality")}
                  value={draft.modality}
                  onChange={(event) => onChange({ ...draft, modality: event.target.value })}
                />
              </label>
              <label title={hoverFor("Interests")}>
                Interests
                <input
                  title={hoverFor("Interests")}
                  value={draft.interests}
                  placeholder="cities, fairness"
                  onChange={(event) => onChange({ ...draft, interests: event.target.value })}
                />
              </label>
              <p className="help">
                Age, reading level, modality, and interests are sent with the next step. Voice, guidance, and
                self-explanation stay on Agent customizations.
              </p>
            </>
          ) : null}
          {notice ? (
            <div className="banner" role="alert">
              <p>{notice}</p>
            </div>
          ) : null}
          <div className="rail-actions">
            <button className="button" type="submit" disabled={saving}>
              Save settings
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function quizFor(choice: { prompt: string; choices: { id: string; text: string }[] }): KidQuiz {
  return {
    type: "single",
    prompt: choice.prompt,
    choices: choice.choices,
    explain: false,
  };
}

function Ring({ progress }: { progress: KcProgress }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const count = Math.max(progress.ring.length, 1);
  const gap = 6;
  const segment = circumference / count;
  const color = {
    known: "#1d6b45",
    fragile: "#c4491d",
    not_started: "#d5cbbd",
  };
  return (
    <figure className="kc-ring">
      <svg viewBox="0 0 140 140" role="img" aria-label={`${progress.count_label} known`}>
        {progress.ring.map((item, index) => (
          <circle
            key={item.id}
            cx="70"
            cy="70"
            r={radius}
            fill="none"
            stroke={color[item.status]}
            strokeWidth="12"
            strokeDasharray={`${Math.max(segment - gap, 1)} ${circumference}`}
            strokeDashoffset={-index * segment}
            transform="rotate(-90 70 70)"
          />
        ))}
        <text x="70" y="74" textAnchor="middle">
          {progress.count_label}
        </text>
      </svg>
      <figcaption>
        {progress.known} known
        {progress.ring.some((item) => item.status === "fragile") ? " · some fragile" : ""}
      </figcaption>
    </figure>
  );
}
