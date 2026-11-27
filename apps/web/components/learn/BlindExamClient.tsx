"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { BrandMark } from "@/components/BrandMark";
import {
  formatExamPercent,
  formatHakeGain,
  type BlindExamAttemptSummary,
  type BlindExamPublic,
  type ExamPhase,
} from "@/lib/blind-exam";
import { learnCoursePath } from "@/lib/learn";

export function BlindExamClient({
  studentId,
  studentName,
  courseId,
  courseTitle,
  tutorModel,
  phase,
  initialExam,
  initialPreScore,
  initialLatestAttempt,
}: {
  studentId: string;
  studentName: string;
  courseId: string;
  courseTitle: string;
  tutorModel?: string | null;
  phase: ExamPhase;
  initialExam: BlindExamPublic | null;
  initialPreScore: number | null;
  initialLatestAttempt: BlindExamAttemptSummary | null;
}) {
  const [exam, setExam] = useState<BlindExamPublic | null>(initialExam);
  const [loading, setLoading] = useState(!initialExam);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<BlindExamAttemptSummary | null>(null);

  useEffect(() => {
    if (exam) return;
    let active = true;
    setLoading(true);
    setError(null);
    fetch("/api/kc/exam/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ courseId, phase, tutorModel: tutorModel || undefined }),
    })
      .then(async (res) => {
        const data = (await res.json()) as { exam?: BlindExamPublic; detail?: string };
        if (!res.ok || !data.exam) throw new Error(data.detail || "Could not load this check.");
        if (active) setExam(data.exam);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Could not load this check.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [courseId, exam, phase, tutorModel]);

  const title = phase === "pre" ? "Quick check before you begin" : "See what you learned";
  const subtitle =
    phase === "pre"
      ? "Answer calmly in your own words. It is completely fine if you do not know some of these yet."
      : "Try these new scenarios on your own. There is no tutor or hint for this check.";

  const totalItems = exam?.items.length ?? 0;
  const answeredCount = exam
    ? exam.items.filter((item) => (answers[item.id] || "").trim().length > 0).length
    : 0;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!exam || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/kc/exam/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          courseId,
          examId: exam.id,
          studentId,
          answers,
          tutorModel: tutorModel || undefined,
        }),
      });
      const data = (await res.json()) as BlindExamAttemptSummary & { detail?: string };
      if (!res.ok || !data.id) {
        throw new Error(data.detail || "Could not submit your answers.");
      }
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit your answers.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="blind-exam-page">
      <header className="blind-exam-bar">
        <BrandMark />
        <div className="blind-exam-heading">
          <span className="blind-exam-pill">{phase === "pre" ? "Pre-Test" : "Post-Test"}</span>
          <h1>{title}</h1>
          <p>
            {courseTitle}
            {studentName ? ` · ${studentName}` : ""}
          </p>
        </div>
        <Link className="learn-text-link" href={`/kc-progress?student=${encodeURIComponent(studentId)}&course=${encodeURIComponent(courseId)}`}>
          Detailed Progress
        </Link>
      </header>

      <p className="blind-exam-sub">{subtitle}</p>

      {error ? (
        <div className="banner" role="alert">
          <p>{error}</p>
        </div>
      ) : null}

      {loading ? (
        <section className="blind-exam-card" aria-live="polite">
          <p>Preparing quiet scenario questions…</p>
        </section>
      ) : result ? (
        <section className="blind-exam-card blind-exam-result" aria-live="polite">
          <h2>{phase === "pre" ? "Pre-test recorded" : "Post-test complete"}</h2>
          <div className="blind-exam-metrics">
            <div>
              <span>Score</span>
              <strong>{formatExamPercent(result.raw_score)}</strong>
            </div>
            {result.mcq_score !== null ? (
              <div>
                <span>Scenario choices</span>
                <strong>{formatExamPercent(result.mcq_score)}</strong>
              </div>
            ) : null}
            {result.transfer_score !== null ? (
              <div>
                <span>Short explanations</span>
                <strong>{formatExamPercent(result.transfer_score)}</strong>
              </div>
            ) : null}
            {phase === "post" && result.paired_pre_score !== null ? (
              <div>
                <span>Pre → Post</span>
                <strong>
                  {formatExamPercent(result.paired_pre_score)} → {formatExamPercent(result.raw_score)}
                </strong>
              </div>
            ) : null}
            {phase === "post" && result.hake_g !== null ? (
              <div>
                <span>Normalized gain (g)</span>
                <strong>{formatHakeGain(result.hake_g)}</strong>
              </div>
            ) : null}
          </div>
          <div className="blind-exam-actions">
            <Link className="button is-primary" href={learnCoursePath(studentId, courseId)}>
              {phase === "pre" ? "Start course lessons" : "Back to course"}
            </Link>
            <Link
              className="button"
              href={`/kc-progress?student=${encodeURIComponent(studentId)}&course=${encodeURIComponent(courseId)}`}
            >
              View progress
            </Link>
          </div>
        </section>
      ) : exam ? (
        <form className="blind-exam-form" onSubmit={handleSubmit}>
          {initialLatestAttempt ? (
            <p className="blind-exam-note">
              Earlier {phase === "pre" ? "pre-test" : "post-test"} score on file:{" "}
              <strong>{formatExamPercent(initialLatestAttempt.raw_score)}</strong>
              {phase === "post" && initialPreScore !== null
                ? ` (Pre-test: ${formatExamPercent(initialPreScore)})`
                : ""}
            </p>
          ) : null}

          {exam.items.map((item, idx) => (
            <fieldset key={item.id} className="blind-exam-card">
              <legend className="blind-exam-q-num">
                Question {idx + 1} of {totalItems}
              </legend>
              <p className="blind-exam-prompt">{item.prompt}</p>
              {item.kind === "short_transfer" ? (
                <textarea
                  className="blind-exam-textarea"
                  rows={3}
                  placeholder="Write 1–3 clear sentences in your own words…"
                  value={answers[item.id] ?? ""}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [item.id]: e.target.value }))}
                />
              ) : (
                <div className="blind-exam-choices" role="radiogroup" aria-label={`Question ${idx + 1}`}>
                  {item.choices.map((choice) => {
                    const checked = answers[item.id] === choice.id;
                    return (
                      <label
                        key={choice.id}
                        className={checked ? "blind-exam-choice is-selected" : "blind-exam-choice"}
                      >
                        <input
                          type="radio"
                          name={item.id}
                          value={choice.id}
                          checked={checked}
                          onChange={() => setAnswers((prev) => ({ ...prev, [item.id]: choice.id }))}
                        />
                        <span>
                          <strong>{choice.id.toUpperCase()}.</strong> {choice.text}
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
            </fieldset>
          ))}

          <div className="blind-exam-submit-row">
            <span className="blind-exam-progress">
              {answeredCount} of {totalItems} answered
            </span>
            <button type="submit" className="button is-primary" disabled={submitting || answeredCount === 0}>
              {submitting ? "Scoring…" : phase === "pre" ? "Save pre-test" : "Submit post-test"}
            </button>
          </div>
        </form>
      ) : null}
    </main>
  );
}
