"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { KcBanner } from "@/components/KcBanner";
import { KcDebugPanel } from "@/components/KcDebugPanel";
import { KcLesson } from "@/components/learn/KcLesson";
import { LearnCourseBar, LearnQuestPanel, type TutorMood } from "@/components/learn/LearnQuestPanel";
import { TutorAvatar } from "@/components/TutorAvatar";
import { api } from "@/lib/api";
import type { KcBlockProgress, KcDebugVariable, KcProgress, KcTutorCourse, KcTutorSession } from "@/lib/kc";
import type { KcDebugTurn } from "@/lib/kc-debug";
import {
  CHALLENGE_APPETITE_OPTIONS,
  COMMUNICATION_TONE_OPTIONS,
  EXPLANATION_STYLE_OPTIONS,
  EXPRESSION_STYLE_OPTIONS,
  GRADE_BAND_OPTIONS,
  INTEREST_TAG_OPTIONS,
  LEARNING_SUPPORT_OPTIONS,
  READING_LEVEL_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
  gradeBandForAge,
  hoverFor,
  normalizeExplanationStyleOption,
  normalizeReadingLevelOption,
} from "@/lib/kc-layer-fields";
import { KC_MODELS, kcModel, type KcModel } from "@/lib/kc-models";
import { tutorPath } from "@/lib/kc-tutor-path";
import { displayChildStatus, friendlyStrength, learnCoursePath, topicStars } from "@/lib/learn";
import type { Student, TutorProfile } from "@/lib/types";
import { useRouter } from "next/navigation";

type SettingsDraft = {
  model: KcModel;
  age: string;
  grade_band: string;
  reading_level: string;
  response_length: string;
  expression_style: string;
  explanation_style: string;
  challenge_appetite: string;
  communication_tone: string;
  learning_support: string;
  interest_tags: string[];
  interests: string;
};

function settingsDraft(learner: Student | null, model: string): SettingsDraft {
  const cp = learner?.child_profile;
  return {
    model: kcModel(model),
    age: learner?.age == null ? "10" : String(learner.age),
    grade_band: learner?.grade_band ?? cp?.grade_band ?? gradeBandForAge(learner?.age ?? 10),
    reading_level: normalizeReadingLevelOption(cp?.reading_level ?? learner?.reading_level),
    response_length: learner?.response_length ?? cp?.response_length ?? "balanced",
    expression_style: learner?.expression_style ?? cp?.expression_style ?? "short_phrases",
    explanation_style: normalizeExplanationStyleOption(
      learner?.explanation_style ?? cp?.explanation_style ?? learner?.modality,
    ),
    challenge_appetite: learner?.challenge_appetite ?? cp?.challenge_appetite ?? "steady",
    communication_tone: learner?.communication_tone ?? cp?.communication_tone ?? "warm_and_encouraging",
    learning_support: learner?.learning_support ?? cp?.learning_support ?? "none",
    interest_tags: [...(learner?.interest_tags ?? cp?.interest_tags ?? [])].slice(0, 4),
    interests: cp?.interests ?? learner?.interests.join(", ") ?? "",
  };
}

const ADD_NEW_CHILD = "__add_new_child__";

type ChildDraft = {
  name: string;
  age: string;
  grade_band: string;
  reading_level: string;
  response_length: string;
  expression_style: string;
  explanation_style: string;
  challenge_appetite: string;
  communication_tone: string;
  learning_support: string;
  interest_tags: string[];
  interests: string;
};

function blankChild(): ChildDraft {
  return {
    name: "",
    age: "10",
    grade_band: "upper_elementary",
    reading_level: "on_grade",
    response_length: "balanced",
    expression_style: "short_phrases",
    explanation_style: "concrete_examples",
    challenge_appetite: "steady",
    communication_tone: "warm_and_encouraging",
    learning_support: "none",
    interest_tags: [],
    interests: "",
  };
}

function childCreateBody(draft: ChildDraft) {
  const age = Number(draft.age);
  const interests = draft.interests
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return {
    display_name: draft.name.trim(),
    age,
    grade_band: draft.grade_band || gradeBandForAge(age),
    reading_level: draft.reading_level || "on_grade",
    response_length: draft.response_length || "balanced",
    expression_style: draft.expression_style || "short_phrases",
    explanation_style: draft.explanation_style || "concrete_examples",
    modality: draft.explanation_style || "concrete_examples",
    challenge_appetite: draft.challenge_appetite || "steady",
    communication_tone: draft.communication_tone || "warm_and_encouraging",
    learning_support: draft.learning_support || "none",
    interest_tags: draft.interest_tags.slice(0, 4),
    interests,
    child_profile: {
      grade_band: draft.grade_band || gradeBandForAge(age),
      reading_level: draft.reading_level || "on_grade",
      response_length: draft.response_length || "balanced",
      expression_style: draft.expression_style || "short_phrases",
      explanation_style: draft.explanation_style || "concrete_examples",
      challenge_appetite: draft.challenge_appetite || "steady",
      communication_tone: draft.communication_tone || "warm_and_encouraging",
      learning_support: draft.learning_support || "none",
      interest_tags: draft.interest_tags.slice(0, 4),
      interests: draft.interests.trim().slice(0, 120),
    },
  };
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
  tutorProfiles = [],
  studentId,
  courseId,
  kcId,
  model,
  progress,
  session,
  error,
  variables,
  turns,
  variant = "workbench",
}: {
  students: Student[];
  courses: KcTutorCourse[];
  tutorProfiles?: TutorProfile[];
  studentId: string;
  courseId: string;
  kcId: string;
  model: string;
  progress: KcProgress | null;
  session: KcTutorSession | null;
  error: string | null;
  variables: KcDebugVariable[];
  turns: KcDebugTurn[];
  variant?: "workbench" | "learn";
}) {
  const learnMode = variant === "learn";
  const [debugOpen, setDebugOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [mood, setMood] = useState<TutorMood>("ready");
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
  const [profiles, setProfiles] = useState<TutorProfile[]>(tutorProfiles);
  const [switchingTutor, setSwitchingTutor] = useState(false);
  const roster = students.concat(
    createdStudents.filter((student) => !students.some((row) => row.id === student.id)),
  );

  useEffect(() => {
    setPickedStudent(studentId);
  }, [studentId]);

  useEffect(() => {
    if (tutorProfiles.length > 0) {
      setProfiles(tutorProfiles);
      return;
    }
    let cancelled = false;
    api<TutorProfile[]>("/tutor-profiles")
      .then((rows) => {
        if (!cancelled && rows.length > 0) setProfiles(rows);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [tutorProfiles]);

  const resolvedTutorId =
    session?.tutor_profile_id ||
    learner?.preferred_tutor_profile_id ||
    profiles.find((p) => p.is_default)?.id ||
    "default";
  const [selectedTutorId, setSelectedTutorId] = useState<string>(resolvedTutorId);

  useEffect(() => {
    setSelectedTutorId(resolvedTutorId);
  }, [resolvedTutorId]);

  const activeTutor =
    profiles.find((p) => p.id === selectedTutorId || p.slug === selectedTutorId) ??
    profiles.find((p) => p.is_default || p.id === "default") ?? {
      id: session?.tutor_profile_id || "default",
      name: session?.tutor_name || "Default",
      slug: session?.tutor_slug || "default",
      description:
        session?.tutor_description ||
        "Standard balanced AI Tutor profile using research-backed guided discovery and adaptive child vocabulary.",
      avatar_preset: session?.avatar_preset || "default_circle",
      avatar_url: session?.avatar_url ?? null,
      is_default: true,
      instructive: 3,
      persona: "coach",
      lexicon: "adaptive_to_child",
      voice_override: false,
      metaphors: "everyday",
      sidekick: "none",
      struggle_window: "standard",
      anti_spoiler: true,
      one_question: true,
      use_interests: true,
      stay_on_course: true,
      growth_praise: true,
      misconception_policy: "explain_and_retry_once",
      self_explanation: true,
      enrichment: "on_request",
    };

  async function selectActiveTutor(nextTutorId: string) {
    setSelectedTutorId(nextTutorId);
    const targetStudentId = studentId || pickedStudent;
    if (!targetStudentId || targetStudentId === ADD_NEW_CHILD) return;
    setSwitchingTutor(true);
    try {
      await api<Student>(`/students/${targetStudentId}/tutor-profile`, {
        method: "PUT",
        body: JSON.stringify({
          tutor_profile_id: nextTutorId === "default" ? "default" : nextTutorId,
        }),
      });
      router.refresh();
    } catch (err) {
      setRestartNotice(err instanceof Error ? err.message : "Could not switch tutor profile.");
    } finally {
      setSwitchingTutor(false);
    }
  }

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
            grade_band: draft.grade_band,
            reading_level: draft.reading_level,
            response_length: draft.response_length,
            expression_style: draft.expression_style,
            explanation_style: draft.explanation_style,
            modality: draft.explanation_style,
            challenge_appetite: draft.challenge_appetite,
            communication_tone: draft.communication_tone,
            learning_support: draft.learning_support,
            interest_tags: draft.interest_tags.slice(0, 4),
            interests: draft.interests
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
            child_profile: {
              grade_band: draft.grade_band,
              reading_level: draft.reading_level,
              response_length: draft.response_length,
              expression_style: draft.expression_style,
              explanation_style: draft.explanation_style,
              challenge_appetite: draft.challenge_appetite,
              communication_tone: draft.communication_tone,
              learning_support: draft.learning_support,
              interest_tags: draft.interest_tags.slice(0, 4),
              interests: draft.interests.trim().slice(0, 120),
            },
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
  const topics = (progress?.units ?? []).filter((unit) => !unit.patch);
  const topicIndex = topics.findIndex((unit) => unit.id === (session?.kc_id || openKc));
  const nextTopic =
    topicIndex >= 0
      ? topics.slice(topicIndex + 1).find((unit) => displayChildStatus(unit.child_status, unit.status, unit.mastery) !== "Locked")
      : null;
  const currentTopic = topicIndex >= 0 ? topics[topicIndex] : null;
  const homeHref = `/learn/${studentId}`;

  function openLearnTopic(nextKc: string) {
    router.push(learnCoursePath(studentId, courseId, { kc: nextKc }));
    router.refresh();
  }

  return (
    <main className={`ds-shell kc-screen${learnMode ? " learn-course" : ""}${debugOpen ? " is-debug" : ""}${panelOpen ? " is-panel" : ""}`}>
      {learnMode ? (
        <LearnCourseBar
          homeHref={homeHref}
          title={course?.title || progress?.title || "Course"}
          done={progress?.completed_count ?? course?.completed_count ?? 0}
          total={progress?.total_count ?? course?.component_count ?? 0}
          stars={course?.stars ?? progress?.stars ?? 0}
          tutor={activeTutor}
          debugOpen={debugOpen}
          panelOpen={panelOpen}
          onDebug={() => setDebugOpen((open) => !open)}
          onPanel={() => setPanelOpen((open) => !open)}
        />
      ) : (
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
      )}
      <aside className={learnMode ? "ds-side learn-quest" : "ds-side kc-tutor-side"}>
        {learnMode ? (
          <LearnQuestPanel
            tutor={activeTutor}
            mood={mood}
            progress={progress}
            session={session}
            activeId={session?.kc_id || openKc}
            onOpenTopic={openLearnTopic}
          />
        ) : (
        <>
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
          <div className="kc-tutor-selector" aria-label="Active Tutor Selector">
            <label>
              Tutor
              <div className="kc-tutor-selector-row">
                <TutorAvatar
                  preset={activeTutor.avatar_preset}
                  avatarUrl={activeTutor.avatar_url}
                  name={activeTutor.name}
                  size="sm"
                />
                <select
                  aria-label="Tutor"
                  value={selectedTutorId}
                  disabled={switchingTutor}
                  onChange={(event) => void selectActiveTutor(event.target.value)}
                >
                  {(profiles.length > 0 ? profiles : [activeTutor]).map((item) => (
                    <option key={item.id || item.slug} value={item.id || "default"}>
                      {item.name || "Default"}
                    </option>
                  ))}
                </select>
              </div>
            </label>
            {activeTutor.description ? (
              <small className="kc-tutor-selector-desc">{activeTutor.description}</small>
            ) : null}
          </div>
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
            {progress.next_course ? (
              <a
                className="button kc-next-course"
                href={tutorPath({ student: studentId, course: progress.next_course.id, model })}
              >
                Open {progress.next_course.title}
              </a>
            ) : null}
            {progress.cards.length === 0 && progress.ring.every((item) => item.status === "known") ? (
              <p className="ds-quiet">Every target component is known.</p>
            ) : null}
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
        </>
        )}
      </aside>
      <section className="ds-stage">
        {learnMode && error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        {session && !learnMode ? (
          <header className="ds-header">
            <BlockProgressBanner session={session} />
            <p className="kc-step">
              {session.title} · {session.recipe} · {session.step_label}
              {session.status === "completed" ? ` · score ${session.score ?? 0}` : ""}
            </p>
          </header>
        ) : null}
        {session && learnMode ? (
          <header className="ds-header learn-topic-head">
            <TutorAvatar
              preset={session.avatar_preset || activeTutor.avatar_preset}
              avatarUrl={session.avatar_url ?? activeTutor.avatar_url}
              name={session.tutor_name || activeTutor.name}
              size="sm"
            />
            <div>
              <strong>{session.title}</strong>
              <span>
                Step {Math.min((session.active_block_index ?? session.step) + 1, session.total_blocks || 1)} of{" "}
                {session.total_blocks || 1}
              </span>
              <span className="learn-step-bar" aria-hidden="true">
                <i style={{ width: `${session.completion_pct ?? 0}%` }} />
              </span>
            </div>
          </header>
        ) : null}
        {session?.redirect && !learnMode ? <p className="kc-redirect">Next card: {session.redirect.title}</p> : null}
        {!session ? (
          <div className="ds-empty">
            <p>{error || (learnMode ? "This course is opening." : "A card opens one component.")}</p>
          </div>
        ) : null}
        {session ? (
          <KcLesson
            key={session.id}
            session={session}
            model={model}
            activeTutor={activeTutor}
            learnMode={learnMode}
            onActivity={setMood}
            nextTopic={nextTopic ? { id: nextTopic.id, title: nextTopic.title } : null}
            homeHref={homeHref}
            topicCompleteStars={currentTopic ? topicStars(currentTopic) : 0}
            topicStrength={friendlyStrength(currentTopic?.what_was_strong)}
            onOpenTopic={openLearnTopic}
            courseDone={Boolean(progress?.course_complete) && session.status === "completed" && !nextTopic}
          />
        ) : null}
      </section>
      {debugOpen ? <KcDebugPanel variables={variables} turns={turns} /> : null}
    </main>
  );
}

function BlockProgressBanner({ session }: { session: KcTutorSession }) {
  if (typeof session.total_blocks !== "number") return null;
  const total = session.total_blocks;
  const completed = session.completed_blocks ?? 0;
  const pct = Math.max(0, Math.min(100, session.completion_pct ?? 0));
  const active = session.block_progress?.find((item) => item.status === "active");
  const index = session.active_block_index ?? active?.index ?? session.step;
  const typeLabel = active?.type_label ?? "";
  return (
    <div className="kc-block-progress" aria-label="Component block progress">
      <p>
        {completed} / {total} Blocks Complete · {pct}%
      </p>
      {total > 0 && typeLabel ? (
        <p>
          Block {index + 1} of {total}: {typeLabel}
          {session.active_substep_label ? <span className="kc-substep">{session.active_substep_label}</span> : null}
        </p>
      ) : null}
      <div className="kc-block-bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Blocks complete">
        <span style={{ width: `${pct}%` }} />
      </div>
      {session.block_progress?.length ? (
        <ol className="kc-block-pills">
          {session.block_progress.map((item, position) => (
            <li key={item.id || position} className={`is-${item.status}`} title={pillTitle(item)}>
              <strong>{(item.index ?? position) + 1}</strong>
              <span>{item.type_label}</span>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

function pillTitle(item: KcBlockProgress): string {
  if (item.status === "upcoming") return "Upcoming";
  if (item.status === "active") {
    const attempts = item.attempts ? `${item.attempts} ${item.attempts === 1 ? "attempt" : "attempts"}` : "";
    return ["Active", item.outcome, attempts].filter(Boolean).join(" · ");
  }
  const attempts = item.attempts ? `${item.attempts} ${item.attempts === 1 ? "attempt" : "attempts"}` : "";
  return [item.outcome || "Completed", attempts].filter(Boolean).join(" · ");
}

function InterestTagChips({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  function toggle(tag: string) {
    if (selected.includes(tag)) {
      onChange(selected.filter((item) => item !== tag));
      return;
    }
    if (selected.length < 4) {
      onChange([...selected, tag]);
    }
  }
  return (
    <div className="kc-chip-group" role="group" aria-label="Interest tags" title={hoverFor("Interest tags")}>
      {INTEREST_TAG_OPTIONS.map(([id, label]) => {
        const active = selected.includes(id);
        return (
          <button
            key={id}
            type="button"
            className={`kc-chip${active ? " is-active" : ""}`}
            aria-pressed={active}
            onClick={() => toggle(id)}
          >
            {label}
          </button>
        );
      })}
    </div>
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
  const gradeTouched = useRef(false);
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
            <p>Layer 2 child persona settings.</p>
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
          <label title={hoverFor("Age")}>
            Age
            <input
              type="number"
              inputMode="numeric"
              min={5}
              max={18}
              required
              title={hoverFor("Age")}
              value={draft.age}
              onChange={(event) => {
                const age = event.target.value;
                const parsed = Number(age);
                setDraft((current) => ({
                  ...current,
                  age,
                  grade_band: gradeTouched.current ? current.grade_band : gradeBandForAge(parsed),
                }));
              }}
            />
          </label>
          <label title={hoverFor("Grade band")}>
            Grade band
            <select
              aria-label="Grade band"
              title={hoverFor("Grade band")}
              value={draft.grade_band}
              onChange={(event) => {
                gradeTouched.current = true;
                setDraft((current) => ({ ...current, grade_band: event.target.value }));
              }}
            >
              {GRADE_BAND_OPTIONS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label title={hoverFor("Reading level")}>
            Reading level
            <select
              aria-label="Reading level"
              title={hoverFor("Reading level")}
              value={draft.reading_level}
              onChange={(event) => setDraft((current) => ({ ...current, reading_level: event.target.value }))}
            >
              {READING_LEVEL_OPTIONS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label title={hoverFor("Response length")}>
            Response length
            <select
              aria-label="Response length"
              title={hoverFor("Response length")}
              value={draft.response_length}
              onChange={(event) => setDraft((current) => ({ ...current, response_length: event.target.value }))}
            >
              {RESPONSE_LENGTH_OPTIONS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label title={hoverFor("Expression style")}>
            Expression style
            <select
              aria-label="Expression style"
              title={hoverFor("Expression style")}
              value={draft.expression_style}
              onChange={(event) => setDraft((current) => ({ ...current, expression_style: event.target.value }))}
            >
              {EXPRESSION_STYLE_OPTIONS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label title={hoverFor("Explanation style")}>
            Explanation style
            <select
              aria-label="Explanation style"
              title={hoverFor("Explanation style")}
              value={draft.explanation_style}
              onChange={(event) => setDraft((current) => ({ ...current, explanation_style: event.target.value }))}
            >
              {EXPLANATION_STYLE_OPTIONS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label title={hoverFor("Challenge appetite")}>
            Challenge appetite
            <select
              aria-label="Challenge appetite"
              title={hoverFor("Challenge appetite")}
              value={draft.challenge_appetite}
              onChange={(event) => setDraft((current) => ({ ...current, challenge_appetite: event.target.value }))}
            >
              {CHALLENGE_APPETITE_OPTIONS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label title={hoverFor("Communication tone")}>
            Communication tone
            <select
              aria-label="Communication tone"
              title={hoverFor("Communication tone")}
              value={draft.communication_tone}
              onChange={(event) => setDraft((current) => ({ ...current, communication_tone: event.target.value }))}
            >
              {COMMUNICATION_TONES_OR_OPTIONS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label title={hoverFor("Learning support")}>
            Learning support
            <select
              aria-label="Learning support"
              title={hoverFor("Learning support")}
              value={draft.learning_support}
              onChange={(event) => setDraft((current) => ({ ...current, learning_support: event.target.value }))}
            >
              {LEARNING_SUPPORT_OPTIONS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label title={hoverFor("Interest tags")}>
            Interest tags (up to 4)
            <InterestTagChips
              selected={draft.interest_tags}
              onChange={(interest_tags) => setDraft((current) => ({ ...current, interest_tags }))}
            />
          </label>
          <label title={hoverFor("Interests")}>
            Specific favorites
            <input
              maxLength={120}
              value={draft.interests}
              placeholder="Minecraft redstone, golden retrievers, soccer goalie"
              onChange={(event) => {
                const interests = event.target.value;
                setDraft((current) => ({ ...current, interests }));
              }}
            />
          </label>
          <p className="help">
            Layer 2 child settings are saved on the child. Voice and block teaching rules stay on Agent customizations.
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

const COMMUNICATION_TONES_OR_OPTIONS = COMMUNICATION_TONE_OPTIONS;

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
    : "Choose a child to edit Layer 2 child persona settings.";

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
                  min={5}
                  max={18}
                  required
                  title={hoverFor("Age")}
                  value={draft.age}
                  onChange={(event) => {
                    const age = event.target.value;
                    const parsed = Number(age);
                    onChange({
                      ...draft,
                      age,
                      grade_band: Number.isInteger(parsed) ? gradeBandForAge(parsed) : draft.grade_band,
                    });
                  }}
                />
              </label>
              <label title={hoverFor("Grade band")}>
                Grade band
                <select
                  aria-label="Grade band"
                  title={hoverFor("Grade band")}
                  value={draft.grade_band}
                  onChange={(event) => onChange({ ...draft, grade_band: event.target.value })}
                >
                  {GRADE_BAND_OPTIONS.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label title={hoverFor("Reading level")}>
                Reading level
                <select
                  aria-label="Reading level"
                  title={hoverFor("Reading level")}
                  value={draft.reading_level}
                  onChange={(event) => onChange({ ...draft, reading_level: event.target.value })}
                >
                  {READING_LEVEL_OPTIONS.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label title={hoverFor("Response length")}>
                Response length
                <select
                  aria-label="Response length"
                  title={hoverFor("Response length")}
                  value={draft.response_length}
                  onChange={(event) => onChange({ ...draft, response_length: event.target.value })}
                >
                  {RESPONSE_LENGTH_OPTIONS.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label title={hoverFor("Expression style")}>
                Expression style
                <select
                  aria-label="Expression style"
                  title={hoverFor("Expression style")}
                  value={draft.expression_style}
                  onChange={(event) => onChange({ ...draft, expression_style: event.target.value })}
                >
                  {EXPRESSION_STYLE_OPTIONS.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label title={hoverFor("Explanation style")}>
                Explanation style
                <select
                  aria-label="Explanation style"
                  title={hoverFor("Explanation style")}
                  value={draft.explanation_style}
                  onChange={(event) => onChange({ ...draft, explanation_style: event.target.value })}
                >
                  {EXPLANATION_STYLE_OPTIONS.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label title={hoverFor("Challenge appetite")}>
                Challenge appetite
                <select
                  aria-label="Challenge appetite"
                  title={hoverFor("Challenge appetite")}
                  value={draft.challenge_appetite}
                  onChange={(event) => onChange({ ...draft, challenge_appetite: event.target.value })}
                >
                  {CHALLENGE_APPETITE_OPTIONS.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label title={hoverFor("Communication tone")}>
                Communication tone
                <select
                  aria-label="Communication tone"
                  title={hoverFor("Communication tone")}
                  value={draft.communication_tone}
                  onChange={(event) => onChange({ ...draft, communication_tone: event.target.value })}
                >
                  {COMMUNICATION_TONE_OPTIONS.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label title={hoverFor("Learning support")}>
                Learning support
                <select
                  aria-label="Learning support"
                  title={hoverFor("Learning support")}
                  value={draft.learning_support}
                  onChange={(event) => onChange({ ...draft, learning_support: event.target.value })}
                >
                  {LEARNING_SUPPORT_OPTIONS.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label title={hoverFor("Interest tags")}>
                Interest tags (up to 4)
                <InterestTagChips
                  selected={draft.interest_tags}
                  onChange={(interest_tags) => onChange({ ...draft, interest_tags })}
                />
              </label>
              <label title={hoverFor("Interests")}>
                Specific favorites
                <input
                  maxLength={120}
                  title={hoverFor("Interests")}
                  value={draft.interests}
                  placeholder="Minecraft redstone, golden retrievers, soccer goalie"
                  onChange={(event) => onChange({ ...draft, interests: event.target.value })}
                />
              </label>
              <p className="help">
                Layer 2 child settings are sent with the next step. Voice, guidance, and block teaching rules stay on
                Agent customizations.
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

function Ring({ progress }: { progress: KcProgress }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const count = Math.max(progress.ring.length, 1);
  const gap = 6;
  const segment = circumference / count;
  const color = {
    known: "#1d6b45",
    fragile: "#e6a317",
    not_started: "#d5cbbd",
  };
  const completed = progress.ring.filter((item) => item.status === "known" || item.status === "fragile").length;
  const fragile = progress.ring.filter((item) => item.status === "fragile").length;
  const caption = `${completed} completed, ${fragile} fragile`;
  return (
    <figure className="kc-ring">
      <svg viewBox="0 0 140 140" role="img" aria-label={caption}>
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
            data-status={item.status}
            aria-label={`${item.title}: ${item.status}`}
          />
        ))}
        <text x="70" y="74" textAnchor="middle">
          {progress.count_label}
        </text>
      </svg>
      <figcaption>{caption}</figcaption>
    </figure>
  );
}
