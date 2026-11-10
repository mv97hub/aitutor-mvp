"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { BrandMark } from "@/components/BrandMark";
import { TutorAvatar } from "@/components/TutorAvatar";
import { BasicsFields, ChildMark, PersonaFields } from "@/components/learn/ChildFields";
import { api } from "@/lib/api";
import type { KcTutorCourse } from "@/lib/kc";
import {
  STAR_TOOLTIP,
  childDraftError,
  childWriteBody,
  courseMinutes,
  draftFromStudent,
  explorerFor,
  gradePill,
  sumStars,
  type ChildDraft,
} from "@/lib/learn";
import type { Student, TutorProfile } from "@/lib/types";

export function ChildHome({
  student,
  courses,
  tutors,
  error,
}: {
  student: Student;
  courses: KcTutorCourse[];
  tutors: TutorProfile[];
  error: string | null;
}) {
  const router = useRouter();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [picker, setPicker] = useState<{ course: KcTutorCourse; mode: "start" | "change" } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [completedOpen, setCompletedOpen] = useState(false);

  const stars = sumStars(courses);
  const rank = explorerFor(stars);
  const inProgress = courses
    .filter((course) => course.started && !course.course_complete)
    .sort((a, b) => (b.last_active_at || "").localeCompare(a.last_active_at || ""));
  const fresh = courses.filter((course) => !course.started);
  const done = courses.filter((course) => course.course_complete);
  const hero = inProgress[0];
  const rest = inProgress.slice(1);

  async function continueCourse(courseId: string) {
    setBusy(true);
    setNotice(null);
    try {
      await api("/kc/tutor/start", {
        method: "POST",
        body: JSON.stringify({ student_id: student.id, course_id: courseId }),
      });
      router.push(`/learn/${student.id}/course/${courseId}`);
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
        router.push(`/learn/${student.id}/course/${courseId}`);
        router.refresh();
      }
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Could not save that tutor.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="learn-shell">
      <BrandMark />
      <header className="learn-home-bar">
        <div className="learn-who">
          <ChildMark
            name={student.display_name}
            preset={student.child_profile?.avatar_preset}
            avatarUrl={student.child_profile?.avatar_url}
            size="lg"
          />
          <div>
            <h1>Hi, {student.display_name}!</h1>
            <Link href="/learn" className="learn-switch">
              Switch learner
            </Link>
          </div>
        </div>
        <div className="learn-home-actions">
          <span className="learn-stars" title={STAR_TOOLTIP}>
            ★ {stars}
          </span>
          <button type="button" className="learn-btn" onClick={() => setSettingsOpen(true)}>
            My Settings
          </button>
          <Link className="learn-text-link" href={`/kc-progress?student=${student.id}`}>
            Detailed progress
          </Link>
        </div>
      </header>

      <section className="learn-rank" aria-label="Explorer level">
        <div>
          <p className="eyebrow">Mastery stars</p>
          <h2>
            Level {rank.explorer_level}: {rank.explorer_rank}
          </h2>
        </div>
        <div className="learn-rank-bar" title={STAR_TOOLTIP}>
          <span style={{ width: `${rank.explorer_percent}%` }} />
        </div>
        <p className="learn-quiet">
          {rank.explorer_next == null
            ? `${stars} stars`
            : `${stars} stars · ${rank.explorer_next - stars} to the next level`}
        </p>
      </section>

      {error || notice ? (
        <div className="banner" role="alert">
          <p>{error || notice}</p>
        </div>
      ) : null}

      <section className="learn-section">
        <h2>Continue learning</h2>
        {inProgress.length === 0 ? (
          <p className="learn-quiet">No courses in progress yet. Start one below.</p>
        ) : (
          <div className="learn-continue">
            {hero ? (
              <CourseCard
                course={hero}
                hero
                busy={busy}
                onContinue={() => void continueCourse(hero.id)}
                onChangeTutor={() => setPicker({ course: hero, mode: "change" })}
              />
            ) : null}
            {rest.map((course) => (
              <CourseCard
                key={course.id}
                course={course}
                busy={busy}
                onContinue={() => void continueCourse(course.id)}
                onChangeTutor={() => setPicker({ course, mode: "change" })}
              />
            ))}
          </div>
        )}
      </section>

      <section className="learn-section">
        <h2>Start a new course</h2>
        {fresh.length === 0 ? (
          <p className="learn-quiet">Every ready course is already started.</p>
        ) : (
          <div className="learn-catalog">
            {fresh.map((course) => (
              <article key={course.id} className="learn-course-card">
                <h3>{course.title}</h3>
                <p>{course.description || "A new set of topics to explore."}</p>
                <p className="learn-meta">
                  {course.component_count ?? 0} topics · ~{courseMinutes(course)} min
                </p>
                <button
                  type="button"
                  className="learn-btn primary"
                  disabled={busy}
                  onClick={() => setPicker({ course, mode: "start" })}
                >
                  Choose tutor & start
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      {done.length > 0 ? (
        <section className="learn-section">
          <button type="button" className="learn-disclosure" onClick={() => setCompletedOpen((open) => !open)}>
            Completed courses ({done.length})
          </button>
          {completedOpen ? (
            <ul className="learn-done-list">
              {done.map((course) => (
                <li key={course.id}>
                  <strong>{course.title}</strong>
                  <span>Finished · ★ {course.stars ?? 0}</span>
                  <button type="button" className="learn-btn" disabled={busy} onClick={() => void continueCourse(course.id)}>
                    Review
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

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
    </main>
  );
}

function CourseCard({
  course,
  hero,
  busy,
  onContinue,
  onChangeTutor,
}: {
  course: KcTutorCourse;
  hero?: boolean;
  busy: boolean;
  onContinue: () => void;
  onChangeTutor: () => void;
}) {
  const total = course.component_count ?? 0;
  const completed = course.completed_count ?? 0;
  const percent = course.percent ?? 0;
  const topic = course.current_topic?.title;
  return (
    <article className={`learn-course-card${hero ? " is-hero" : ""}`}>
      {hero ? <p className="eyebrow">Jump right back in</p> : null}
      <h3>{course.title}</h3>
      {course.tutor ? (
        <p className="learn-guided">
          <TutorAvatar
            preset={course.tutor.avatar_preset}
            avatarUrl={course.tutor.avatar_url}
            name={course.tutor.name}
            size="sm"
          />
          Guided by {course.tutor.name}
        </p>
      ) : null}
      {topic ? <p className="learn-meta">Currently on: {topic}</p> : null}
      <div className="learn-progress" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </div>
      <p className="learn-meta">
        {completed} of {total} topics complete · {percent}% · ★ {course.stars ?? 0}
      </p>
      <div className="learn-actions">
        <button type="button" className="learn-btn primary" disabled={busy} onClick={onContinue}>
          Continue
        </button>
        <button type="button" className="learn-btn" disabled={busy} onClick={onChangeTutor}>
          Change tutor
        </button>
      </div>
    </article>
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
