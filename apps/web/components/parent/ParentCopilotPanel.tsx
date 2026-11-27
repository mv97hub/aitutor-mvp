"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import {
  BIOMARKER_LABELS,
  COURSE_MODE_OPTIONS,
  absoluteShareUrl,
  activeLockLabels,
  formatHakeGain,
  formatPercent,
  trajectoryTone,
  type CourseMode,
  type ParentCopilotSummary,
  type ParentPolicyLocks,
  type TeacherShareMeta,
} from "@/lib/parent-copilot";

export function ParentCopilotPanel({
  parentId,
  summary: initialSummary,
}: {
  parentId: string;
  summary: ParentCopilotSummary;
}) {
  const [summary, setSummary] = useState<ParentCopilotSummary>(initialSummary);
  const [selectedCourseId, setSelectedCourseId] = useState<string>(initialSummary.courses[0]?.course_id ?? "");
  const [interestDraft, setInterestDraft] = useState<string>(() => {
    const firstCourse = initialSummary.courses[0];
    return firstCourse?.parent_policy_locks?.anchor_in_interest ?? initialSummary.interests[0] ?? "";
  });
  const [savingLocks, setSavingLocks] = useState(false);
  const [lockNotice, setLockNotice] = useState<string | null>(null);
  const [lockError, setLockError] = useState<string | null>(null);

  const [shareLabel, setShareLabel] = useState("");
  const [shareScope, setShareScope] = useState<string>("all");
  const [creatingShare, setCreatingShare] = useState(false);
  const [freshShare, setFreshShare] = useState<TeacherShareMeta | null>(null);
  const [shareError, setShareError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const selectedCourse = summary.courses.find((c) => c.course_id === selectedCourseId) ?? summary.courses[0] ?? null;
  const latestDigest = summary.digests[0] ?? null;
  const tone = trajectoryTone(summary.trajectory_state);

  function selectCourse(courseId: string) {
    setSelectedCourseId(courseId);
    const next = summary.courses.find((c) => c.course_id === courseId);
    setInterestDraft(next?.parent_policy_locks?.anchor_in_interest ?? summary.interests[0] ?? "");
    setLockNotice(null);
    setLockError(null);
  }

  async function saveIntervention(opts: { courseId: string; locks?: ParentPolicyLocks; courseMode?: CourseMode }) {
    setSavingLocks(true);
    setLockNotice(null);
    setLockError(null);
    try {
      const updated = await api<{
        course_id: string;
        course_mode: CourseMode;
        parent_policy_locks: ParentPolicyLocks;
        next_session_guidance: string;
      }>(`/parents/${parentId}/children/${summary.student_id}/interventions/apply`, {
        method: "POST",
        body: JSON.stringify({
          course_id: opts.courseId,
          ...(opts.courseMode ? { course_mode: opts.courseMode } : {}),
          ...(opts.locks ? { locks: opts.locks } : {}),
        }),
      });
      setSummary((prev) => ({
        ...prev,
        courses: prev.courses.map((course) =>
          course.course_id === updated.course_id
            ? {
                ...course,
                course_mode: updated.course_mode,
                parent_policy_locks: updated.parent_policy_locks,
              }
            : course,
        ),
      }));
      setLockNotice("Saved for the next lesson. Active lessons stay unchanged until the next topic opens.");
    } catch (err) {
      setLockError(err instanceof Error ? err.message : "Could not save guidance settings.");
    } finally {
      setSavingLocks(false);
    }
  }

  async function createShare(event: React.FormEvent) {
    event.preventDefault();
    if (creatingShare) return;
    setCreatingShare(true);
    setShareError(null);
    setFreshShare(null);
    setCopied(false);
    try {
      const created = await api<TeacherShareMeta>(
        `/parents/${parentId}/children/${summary.student_id}/teacher-shares`,
        {
          method: "POST",
          body: JSON.stringify({
            course_id: shareScope === "all" ? null : shareScope,
            label: shareLabel.trim(),
            expires_in_days: 30,
          }),
        },
      );
      setFreshShare(created);
      setShareLabel("");
      setSummary((prev) => ({
        ...prev,
        teacher_shares: [created, ...prev.teacher_shares],
      }));
    } catch (err) {
      setShareError(err instanceof Error ? err.message : "Could not create teacher share link.");
    } finally {
      setCreatingShare(false);
    }
  }

  async function revokeShare(shareId: string) {
    setShareError(null);
    try {
      const revoked = await api<TeacherShareMeta>(
        `/parents/${parentId}/children/${summary.student_id}/teacher-shares/${shareId}`,
        { method: "DELETE" },
      );
      setSummary((prev) => ({
        ...prev,
        teacher_shares: prev.teacher_shares.map((item) => (item.id === revoked.id ? revoked : item)),
      }));
      if (freshShare?.id === shareId) setFreshShare(null);
    } catch (err) {
      setShareError(err instanceof Error ? err.message : "Could not revoke that link.");
    }
  }

  async function copyFreshLink() {
    if (!freshShare?.share_path || typeof window === "undefined") return;
    const url = absoluteShareUrl(freshShare.share_path, window.location.origin);
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const currentLocks: ParentPolicyLocks = selectedCourse?.parent_policy_locks ?? {};
  const currentMode: CourseMode = selectedCourse?.course_mode ?? "mastery";

  return (
    <section className="copilot-stack" aria-label={`${summary.display_name} Co-Pilot`}>
      {/* 1. Trajectory & Flourishing Biomarkers */}
      <div className="copilot-card">
        <div className="copilot-card-head">
          <div>
            <h2>Learning Trajectory · {summary.display_name}</h2>
            <p className="learn-quiet">{summary.trajectory_meta.description}</p>
          </div>
          <span className={`copilot-badge is-${tone}`}>{summary.trajectory_meta.label}</span>
        </div>

        <div className="copilot-bio-grid" aria-label="Flourishing biomarkers">
          {BIOMARKER_LABELS.map((item) => (
            <div key={item.key} className="copilot-bio-tile">
              <strong>{summary.biomarkers[item.key] ?? 0}</strong>
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 2. Dinner-Table Talking Points & Latest Digest */}
      <div className="copilot-card">
        <h2>Dinner-Table Talking Points</h2>
        {latestDigest ? (
          <>
            <p className="copilot-summary-line">
              <strong>{latestDigest.kc_title || "Recent lesson"}:</strong> {latestDigest.summary}
            </p>
            <ul className="copilot-talking-list">
              {latestDigest.talking_points.map((point, idx) => (
                <li key={idx}>{point}</li>
              ))}
            </ul>
            {latestDigest.recommended_interventions.length > 0 && selectedCourse ? (
              <div className="copilot-rec-row">
                <span className="learn-quiet">Suggested for next lesson:</span>
                {latestDigest.recommended_interventions.map((rec) => (
                  <button
                    key={rec.key}
                    type="button"
                    className="learn-btn"
                    disabled={savingLocks}
                    title={rec.reason}
                    onClick={() =>
                      void saveIntervention({
                        courseId: latestDigest.course_id || selectedCourse.course_id,
                        locks: rec.payload,
                      })
                    }
                  >
                    + {rec.label}
                  </button>
                ))}
              </div>
            ) : null}
          </>
        ) : (
          <p className="learn-quiet">
            Talking points appear automatically as soon as {summary.display_name} finishes a lesson component.
          </p>
        )}
      </div>

      {/* 3. Per-Course Co-Pilot Controls (Course Mode + Policy Locks) */}
      {selectedCourse ? (
        <div className="copilot-card">
          <div className="copilot-card-head">
            <div>
              <h2>Course Guidance Controls</h2>
              <p className="learn-quiet">
                Applies only to {summary.display_name} on this course (never edits shared tutor presets or live lessons).
              </p>
            </div>
            <label className="learn-field">
              Course
              <select
                aria-label="Course for guidance controls"
                value={selectedCourse.course_id}
                onChange={(e) => selectCourse(e.target.value)}
              >
                {summary.courses.map((c) => (
                  <option key={c.course_id} value={c.course_id}>
                    {c.title} ({c.known_count}/{c.total_components} known)
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="copilot-course-stats">
            <span>
              <strong>Mastered:</strong> {selectedCourse.known_count}/{selectedCourse.total_components}
            </span>
            <span>
              <strong>Needs review:</strong> {selectedCourse.fragile_count}
            </span>
            <span>
              <strong>Blind Pre → Post:</strong> {formatPercent(selectedCourse.blind_exam.latest_pre_score)} →{" "}
              {formatPercent(selectedCourse.blind_exam.latest_post_score)} (Hake{" "}
              {formatHakeGain(selectedCourse.blind_exam.hake_g)})
            </span>
          </div>

          {selectedCourse.active_misconceptions.length > 0 ? (
            <div className="copilot-misc-box">
              <strong>Watch for these misconceptions:</strong>
              <ul>
                {selectedCourse.active_misconceptions.slice(0, 3).map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="copilot-mode-row" role="group" aria-label="Course mode">
            {COURSE_MODE_OPTIONS.map((opt) => {
              const active = currentMode === opt.id;
              return (
                <button
                  key={opt.id}
                  type="button"
                  className={`copilot-mode-btn${active ? " is-active" : ""}`}
                  aria-pressed={active}
                  disabled={savingLocks}
                  onClick={() =>
                    void saveIntervention({
                      courseId: selectedCourse.course_id,
                      courseMode: opt.id,
                    })
                  }
                >
                  <strong>{opt.label}</strong>
                  <span>{opt.hint}</span>
                </button>
              );
            })}
          </div>

          <div className="copilot-lock-grid">
            <label className="copilot-toggle">
              <input
                type="checkbox"
                checked={Boolean(currentLocks.more_guided_examples)}
                disabled={savingLocks}
                onChange={(e) =>
                  void saveIntervention({
                    courseId: selectedCourse.course_id,
                    locks: { more_guided_examples: e.target.checked },
                  })
                }
              />
              <span>More guided examples</span>
            </label>
            <label className="copilot-toggle">
              <input
                type="checkbox"
                checked={Boolean(currentLocks.gentler_socratic)}
                disabled={savingLocks}
                onChange={(e) =>
                  void saveIntervention({
                    courseId: selectedCourse.course_id,
                    locks: { gentler_socratic: e.target.checked },
                  })
                }
              />
              <span>Gentler Socratic challenge</span>
            </label>
            <label className="copilot-toggle">
              <input
                type="checkbox"
                checked={Boolean(currentLocks.stretch_challenge)}
                disabled={savingLocks}
                onChange={(e) =>
                  void saveIntervention({
                    courseId: selectedCourse.course_id,
                    locks: { stretch_challenge: e.target.checked },
                  })
                }
              />
              <span>Stretch challenge on mastery</span>
            </label>
          </div>

          <div className="copilot-anchor-row">
            <input
              type="text"
              maxLength={80}
              placeholder="Anchor examples in an interest (e.g. soccer, dogs, space)"
              value={interestDraft}
              disabled={savingLocks}
              onChange={(e) => setInterestDraft(e.target.value)}
            />
            <button
              type="button"
              className="learn-btn"
              disabled={savingLocks}
              onClick={() =>
                void saveIntervention({
                  courseId: selectedCourse.course_id,
                  locks: { anchor_in_interest: interestDraft.trim() || undefined },
                })
              }
            >
              {currentLocks.anchor_in_interest && !interestDraft.trim() ? "Clear anchor" : "Set anchor"}
            </button>
          </div>

          {activeLockLabels(currentLocks).length > 0 ? (
            <p className="learn-quiet">Active locks: {activeLockLabels(currentLocks).join(" · ")}</p>
          ) : null}
          {lockNotice ? (
            <p className="copilot-notice" role="status">
              {lockNotice}
            </p>
          ) : null}
          {lockError ? (
            <p className="banner" role="alert">
              {lockError}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* 4. Revocable Teacher Share Links */}
      <div className="copilot-card">
        <h2>Share Read-Only Snapshot with a Teacher</h2>
        <p className="learn-quiet">
          Teachers see mastered/fragile topics, active misconceptions, the 8 thinking skills, and blind Pre/Post gain —
          never raw chat transcripts. Revoke any link instantly.
        </p>

        <form className="copilot-share-form" onSubmit={(e) => void createShare(e)}>
          <input
            type="text"
            maxLength={120}
            placeholder="Label (e.g. Ms. Patel — 5th Grade)"
            value={shareLabel}
            disabled={creatingShare}
            onChange={(e) => setShareLabel(e.target.value)}
          />
          <select
            aria-label="Course scope for teacher share"
            value={shareScope}
            disabled={creatingShare}
            onChange={(e) => setShareScope(e.target.value)}
          >
            <option value="all">All courses</option>
            {summary.courses.map((c) => (
              <option key={c.course_id} value={c.course_id}>
                Only: {c.title}
              </option>
            ))}
          </select>
          <button className="learn-btn primary" type="submit" disabled={creatingShare}>
            {creatingShare ? "Creating…" : "Create link"}
          </button>
        </form>

        {freshShare?.share_path ? (
          <div className="copilot-fresh-share" role="status">
            <p>
              <strong>One-time link ready</strong> (shown once — copy it now):
            </p>
            <code>{freshShare.share_path}</code>
            <button type="button" className="learn-btn" onClick={() => void copyFreshLink()}>
              {copied ? "Copied!" : "Copy full URL"}
            </button>
          </div>
        ) : null}

        {shareError ? (
          <p className="banner" role="alert">
            {shareError}
          </p>
        ) : null}

        {summary.teacher_shares.length > 0 ? (
          <ul className="copilot-share-list">
            {summary.teacher_shares.map((item) => (
              <li key={item.id} className={`copilot-share-item is-${item.status}`}>
                <div>
                  <strong>{item.label || "Teacher snapshot"}</strong>
                  <span className="learn-quiet">
                    {item.course_title ? `Scope: ${item.course_title}` : "Scope: All courses"} · Key {item.token_prefix}… ·{" "}
                    {item.status}
                  </span>
                </div>
                {item.status === "active" ? (
                  <button
                    type="button"
                    className="learn-btn"
                    onClick={() => void revokeShare(item.id)}
                  >
                    Revoke
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}
