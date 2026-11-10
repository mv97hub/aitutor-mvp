"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { BrandMark } from "@/components/BrandMark";
import { BasicsFields, ChildMark, LearnStyleFields, PersonaFields } from "@/components/learn/ChildFields";
import { api } from "@/lib/api";
import {
  blankChildDraft,
  childDraftError,
  childWriteBody,
  gradePill,
  interestLabel,
  type ChildDraft,
  type LearnerCard,
} from "@/lib/learn";
import type { Student } from "@/lib/types";

export function ChildChooser({ learners, error }: { learners: LearnerCard[]; error: string | null }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  return (
    <main className="learn-shell">
      <BrandMark />
      <section className="learn-chooser">
        <p className="eyebrow">Child experience</p>
        <h1>Who&apos;s learning today?</h1>
        <p className="lede">Pick a learner to see their courses, stars, and tutor.</p>
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <div className="learn-child-grid">
          {learners.map((card) => {
            const student = card.student;
            const tags = (student.child_profile?.interest_tags || student.interest_tags || []).slice(0, 3);
            const courses = card.in_progress_course_count;
            return (
              <button
                key={student.id}
                type="button"
                className="learn-child-card"
                onClick={() => router.push(`/learn/${student.id}`)}
              >
                <ChildMark
                  name={student.display_name}
                  preset={student.child_profile?.avatar_preset}
                  avatarUrl={student.child_profile?.avatar_url}
                />
                <strong>{student.display_name}</strong>
                <span className="learn-pill">{gradePill(student.age, student.child_profile?.grade_band || student.grade_band)}</span>
                {tags.length > 0 ? (
                  <span className="learn-tag-row">
                    {tags.map((tag) => (
                      <span key={tag} className="learn-tag">
                        {interestLabel(tag)}
                      </span>
                    ))}
                  </span>
                ) : (
                  <span className="learn-quiet">No interests yet</span>
                )}
                <span className="learn-activity">
                  {courses} {courses === 1 ? "course" : "courses"} in progress · {card.stars} stars
                </span>
              </button>
            );
          })}
          <button type="button" className="learn-child-card learn-add-card" onClick={() => setOpen(true)}>
            <span className="learn-add-mark" aria-hidden="true">
              +
            </span>
            <strong>Add a Learner</strong>
            <span className="learn-quiet">Name, avatar, and how they like to learn</span>
          </button>
        </div>
      </section>
      {open ? (
        <AddLearnerWizard
          onClose={() => setOpen(false)}
          onCreated={(student) => {
            setOpen(false);
            router.push(`/learn/${student.id}`);
            router.refresh();
          }}
        />
      ) : null}
    </main>
  );
}

function AddLearnerWizard({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (student: Student) => void;
}) {
  const [step, setStep] = useState<1 | 2>(1);
  const [draft, setDraft] = useState<ChildDraft>(blankChildDraft);
  const [showAll, setShowAll] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function createLearner() {
    const problem = childDraftError(draft);
    if (problem) {
      setNotice(problem);
      setStep(1);
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      const student = await api<Student>("/students", {
        method: "POST",
        body: JSON.stringify(childWriteBody(draft, { includeName: true })),
      });
      onCreated(student);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Could not add that learner.");
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
        aria-labelledby="add-learner-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p className="eyebrow">Step {step} of 2</p>
            <h2 id="add-learner-title">{step === 1 ? "The basics" : "How I like to learn"}</h2>
          </div>
          <button type="button" className="learn-btn ghost" onClick={onClose}>
            Close
          </button>
        </header>
        <form
          className="prompt-body"
          onSubmit={(event) => {
            event.preventDefault();
            if (step === 1) {
              const problem = childDraftError(draft);
              if (problem) {
                setNotice(problem);
                return;
              }
              setNotice(null);
              setStep(2);
              return;
            }
            void createLearner();
          }}
        >
          {step === 1 ? (
            <>
              <BasicsFields draft={draft} onChange={setDraft} />
              <div className="learn-field">
                <span>Avatar</span>
                <PersonaFields draft={draft} onChange={setDraft} showAll={false} showAvatar />
              </div>
            </>
          ) : (
            <>
              <LearnStyleFields draft={draft} onChange={setDraft} />
              <label className="learn-toggle">
                <input
                  type="checkbox"
                  checked={showAll}
                  onChange={(event) => setShowAll(event.target.checked)}
                />
                Full 12-setting view
              </label>
              {showAll ? (
                <PersonaFields draft={draft} onChange={setDraft} showAll showAvatar={false} includeCore={false} />
              ) : null}
            </>
          )}
          {notice ? (
            <div className="banner" role="alert">
              <p>{notice}</p>
            </div>
          ) : null}
          <div className="learn-actions">
            {step === 2 ? (
              <button type="button" className="learn-btn ghost" onClick={() => setStep(1)}>
                Back
              </button>
            ) : (
              <span />
            )}
            <button className="learn-btn primary" type="submit" disabled={saving}>
              {step === 1 ? "Next" : saving ? "Creating…" : "Create learner"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
