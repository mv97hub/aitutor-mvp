"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { TutorAvatar } from "@/components/TutorAvatar";
import { Block, Button, Card, Crayon, ProgressBar, SectionTitle, TopBar, type CrayonTone } from "@/components/crayon";
import { BasicsFields, PersonaFields } from "@/components/learn/ChildFields";
import { api } from "@/lib/api";
import type { KcTutorCourse } from "@/lib/kc";
import {
  childDraftError,
  childWriteBody,
  courseMinutes,
  draftFromStudent,
  explorerFor,
  sumStars,
  type ChildDraft,
} from "@/lib/learn";
import { LEARN_MOBILE } from "@/lib/learn-mobile";
import type { Student, TutorProfile } from "@/lib/types";

export function ChildHome({
  student,
  courses,
  tutors,
  error,
  basePath = "/learn",
}: {
  student: Student;
  courses: KcTutorCourse[];
  tutors: TutorProfile[];
  error: string | null;
  basePath?: string;
}) {
  const phone = basePath === LEARN_MOBILE;
  const router = useRouter();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [picker, setPicker] = useState<{ course: KcTutorCourse; mode: "start" | "change" } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const stars = sumStars(courses);
  const rank = explorerFor(stars);
  const inProgress = courses
    .filter((course) => course.started && !course.course_complete)
    .sort((a, b) => (b.last_active_at || "").localeCompare(a.last_active_at || ""));
  const fresh = courses.filter((course) => !course.started);
  const done = courses.filter((course) => course.course_complete);
  const hero = inProgress[0];

  async function continueCourse(courseId: string) {
    setBusy(true);
    setNotice(null);
    try {
      await api("/kc/tutor/start", {
        method: "POST",
        body: JSON.stringify({ student_id: student.id, course_id: courseId }),
      });
      router.push(`${basePath}/${student.id}/course/${courseId}`);
      router.refresh();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Could not open that course.");
    } finally {
      setBusy(false);
    }
  }

  async function chooseTutor(tutorId: string) {
    if (!picker) return;
    setBusy(true);
    setNotice(null);
    try {
      if (picker.mode === "change") {
        await api(`/kc/tutor/courses/${picker.course.id}/tutor`, {
          method: "POST",
          body: JSON.stringify({ student_id: student.id, tutor_profile_id: tutorId }),
        });
        setPicker(null);
        router.refresh();
      } else {
        await api("/kc/tutor/start", {
          method: "POST",
          body: JSON.stringify({
            student_id: student.id,
            course_id: picker.course.id,
            tutor_profile_id: tutorId,
          }),
        });
        const courseId = picker.course.id;
        setPicker(null);
        router.push(`${basePath}/${student.id}/course/${courseId}`);
        router.refresh();
      }
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Could not save that tutor.");
    } finally {
      setBusy(false);
    }
  }

  const masteredTopics = courses.reduce((sum, course) => sum + (course.known_count ?? 0), 0);
  const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const minutesWeek = courses.reduce((sum, course) => {
    const activeAt = course.last_active_at ? Date.parse(course.last_active_at) : Number.NaN;
    if (!Number.isFinite(activeAt) || activeAt < weekAgo) return sum;
    return sum + courseMinutes(course);
  }, 0);
  const mascotName = hero?.tutor?.name || tutors.find((tutor) => tutor.id === student.preferred_tutor_profile_id)?.name || tutors[0]?.name || "Tutor";
  const encouragement = hero
    ? `Pick up ${hero.title} where you left off.`
    : `You are a ${rank.explorer_rank}. Pick a course and keep going.`;
  const catalog = [...inProgress, ...fresh, ...done];

  function resumeLearning() {
    if (hero) {
      void continueCourse(hero.id);
      return;
    }
    if (fresh[0]) setPicker({ course: fresh[0], mode: "start" });
  }

  return (
    <Crayon className={phone ? "learn-mobile-shell" : undefined}>
      <TopBar
        appName="Kinder Computers"
        studentName={student.display_name}
        items={[
          { href: `${basePath}/${student.id}`, label: "Home", active: true },
          { href: `/kc-progress?student=${encodeURIComponent(student.id)}`, label: "My Progress" },
        ]}
      />
      <main className="cb-page">
        {error || notice ? (
          <div className="banner" role="alert">
            <p>{error || notice}</p>
          </div>
        ) : null}
        <Block as="section" tone="yellow" className="cb-hero">
          <div>
            <h1>Hi, {student.display_name}!</h1>
            <p>{encouragement}</p>
            <div className="cb-hero-actions">
              <Button tone="primary" disabled={busy || (!hero && fresh.length === 0)} onClick={resumeLearning}>
                Continue learning
              </Button>
              <Button href={basePath}>Switch learner</Button>
              <Button type="button" onClick={() => setSettingsOpen(true)}>
                My Settings
              </Button>
            </div>
          </div>
          <span className="cb-mascot" role="img" aria-label={mascotName}>
            {mascotName.slice(0, 1).toUpperCase()}
          </span>
        </Block>
        <section className="cb-stats" aria-label="This week">
          <Block className="cb-stat">
            <span className="cb-badge">0</span>
            <p>Streak</p>
          </Block>
          <Block className="cb-stat">
            <span className="cb-badge">{masteredTopics}</span>
            <p>Topics mastered</p>
          </Block>
          <Block className="cb-stat">
            <span className="cb-badge">{minutesWeek}</span>
            <p>Minutes this week</p>
          </Block>
          <Block className="cb-stat">
            <span className="cb-badge">{stars}</span>
            <p>Stars</p>
          </Block>
        </section>
        <SectionTitle>My courses</SectionTitle>
        {catalog.length === 0 ? (
          <p className="cb-muted-copy">No courses yet. A new course will show up here when it is ready.</p>
        ) : (
          <div className="cb-course-grid">
            {catalog.map((course, index) => (
              <CourseCard
                key={course.id}
                course={course}
                band={BANDS[index % BANDS.length]}
                busy={busy}
                fresh={!course.started}
                onContinue={() => (course.started ? void continueCourse(course.id) : setPicker({ course, mode: "start" }))}
                onChangeTutor={() => setPicker({ course, mode: course.started ? "change" : "start" })}
              />
            ))}
          </div>
        )}
      </main>
      {settingsOpen ? (
        <SettingsModal
          student={student}
          onClose={() => setSettingsOpen(false)}
          onSaved={() => {
            setSettingsOpen(false);
            router.refresh();
          }}
        />
      ) : null}
      {picker ? (
        <TutorPicker
          course={picker.course}
          mode={picker.mode}
          tutors={tutors}
          preferredId={student.preferred_tutor_profile_id}
          busy={busy}
          onClose={() => setPicker(null)}
          onChoose={(tutorId) => void chooseTutor(tutorId)}
        />
      ) : null}
    </Crayon>
  );
}

const BANDS: CrayonTone[] = ["sky", "pink", "yellow", "green", "blue"];


function CourseCard({
  course,
  band,
  busy,
  fresh,
  onContinue,
  onChangeTutor,
}: {
  course: KcTutorCourse;
  band: CrayonTone;
  busy: boolean;
  fresh: boolean;
  onContinue: () => void;
  onChangeTutor: () => void;
}) {
  const total = course.component_count ?? 0;
  const completed = course.completed_count ?? 0;
  const topic = course.current_topic?.title;
  const description = [course.description, topic ? `Currently on: ${topic}` : "", course.tutor ? `Guided by ${course.tutor.name}` : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <Card band={band}>
      <h3 className="cb-course-title">{course.title}</h3>
      <p className="cb-muted-copy">{description || "A set of topics to explore."}</p>
      <ProgressBar value={completed} max={total || 1} caption={`${completed} of ${total} topics`} />
      <div className="cb-card-actions">
        <Button tone="primary" disabled={busy} onClick={onContinue}>
          {fresh ? "Start" : "Continue"}
        </Button>
        {fresh ? null : (
          <Button disabled={busy} onClick={onChangeTutor}>
            Change tutor
          </Button>
        )}
      </div>
    </Card>
  );
}

function TutorPicker({
  course,
  mode,
  tutors,
  preferredId,
  busy,
  onClose,
  onChoose,
}: {
  course: KcTutorCourse;
  mode: "start" | "change";
  tutors: TutorProfile[];
  preferredId?: string | null;
  busy: boolean;
  onClose: () => void;
  onChoose: (tutorId: string) => void;
}) {
  const [picked, setPicked] = useState(course.tutor?.id || preferredId || tutors.find((tutor) => tutor.is_default)?.id || tutors[0]?.id || "");
  const selected = tutors.find((tutor) => tutor.id === picked);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const ordered = useMemo(() => tutors, [tutors]);

  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="prompt-dialog learn-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pick-tutor-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="pick-tutor-title">Choose your tutor for {course.title}</h2>
            <p>Pick who will teach this course. You can change them later.</p>
          </div>
          <button type="button" className="learn-btn ghost" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="prompt-body">
          {ordered.length === 0 ? <p>No tutors are available yet.</p> : null}
          <div className="learn-tutor-grid">
            {ordered.map((tutor) => {
              const id = tutor.id || "";
              const active = id === picked;
              return (
                <button
                  key={id}
                  type="button"
                  className={`learn-tutor-card${active ? " is-selected" : ""}`}
                  aria-pressed={active}
                  onClick={() => setPicked(id)}
                >
                  <TutorAvatar preset={tutor.avatar_preset} avatarUrl={tutor.avatar_url} name={tutor.name} size="lg" />
                  <strong>{tutor.name || "Tutor"}</strong>
                  <span className="learn-badge-row">
                    {tutor.is_default ? <span className="learn-badge">Recommended</span> : null}
                    {preferredId && id === preferredId ? <span className="learn-badge">Last used</span> : null}
                  </span>
                  <p>{tutor.description || "A patient guide for this course."}</p>
                </button>
              );
            })}
          </div>
          <div className="learn-actions">
            <span />
            <button
              type="button"
              className="learn-btn primary"
              disabled={busy || !picked}
              onClick={() => onChoose(picked)}
            >
              {mode === "change"
                ? `Learn with ${selected?.name || "this tutor"}`
                : `Start learning with ${selected?.name || "this tutor"}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SettingsModal({
  student,
  onClose,
  onSaved,
}: {
  student: Student;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<ChildDraft>(draftFromStudent(student));
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function save() {
    const problem = childDraftError(draft);
    if (problem) {
      setNotice(problem);
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      await api(`/students/${student.id}`, {
        method: "PATCH",
        body: JSON.stringify(childWriteBody(draft, { includeName: false })),
      });
      onSaved();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="prompt-dialog learn-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="child-settings-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="child-settings-title">My Settings</h2>
            <p>Avatar, interests, and how {student.display_name} likes to learn.</p>
          </div>
          <button type="button" className="learn-btn ghost" onClick={onClose}>
            Close
          </button>
        </header>
        <form
          className="prompt-body"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <BasicsFields draft={draft} onChange={setDraft} lockName />
          <PersonaFields draft={draft} onChange={setDraft} showAll showAvatar />
          {notice ? (
            <div className="banner" role="alert">
              <p>{notice}</p>
            </div>
          ) : null}
          <div className="learn-actions">
            <span />
            <button className="learn-btn primary" type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save settings"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
