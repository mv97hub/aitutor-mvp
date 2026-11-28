"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { placementProbeCountLabel } from "@/lib/f5-placement";
import type { KcPlacementProbe, KcPlacementStepResponse, KcTutorCourse } from "@/lib/kc";

export function CoursePlacementModal({
  studentId,
  course,
  tutorId,
  onClose,
  onLaunch,
}: {
  studentId: string;
  course: KcTutorCourse;
  tutorId: string;
  onClose: () => void;
  onLaunch: (kcId?: string) => Promise<void>;
}) {
  const [stage, setStage] = useState<"choose" | "probe" | "done">("choose");
  const [probe, setProbe] = useState<KcPlacementProbe | null>(null);
  const [openAnswer, setOpenAnswer] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [doneResult, setDoneResult] = useState<KcPlacementStepResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function handleStartBeginning() {
    setBusy(true);
    setError(null);
    try {
      await api(`/kc/tutor/courses/${course.id}/placement/skip`, {
        method: "POST",
        body: JSON.stringify({ student_id: studentId }),
      });
      await onLaunch(undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the course.");
      setBusy(false);
    }
  }

  async function handleStartPlacement() {
    setBusy(true);
    setError(null);
    try {
      const res = await api<KcPlacementStepResponse>(`/kc/tutor/courses/${course.id}/placement/start`, {
        method: "POST",
        body: JSON.stringify({ student_id: studentId }),
      });
      if (res.status === "completed") {
        setDoneResult(res);
        setStage("done");
      } else if (res.probe) {
        setProbe(res.probe);
        setStage("probe");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the quick check-in.");
    } finally {
      setBusy(false);
    }
  }

  async function submitProbe(payload: { choice_id?: string; answer?: string; unsure?: boolean }) {
    if (!probe || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api<KcPlacementStepResponse>(`/kc/tutor/courses/${course.id}/placement/answer`, {
        method: "POST",
        body: JSON.stringify({
          student_id: studentId,
          kc_id: probe.kc_id,
          ...payload,
        }),
      });
      setOpenAnswer("");
      if (res.step_feedback) setFeedback(res.step_feedback);
      if (res.status === "completed") {
        setDoneResult(res);
        setProbe(null);
        setStage("done");
      } else if (res.probe) {
        setProbe(res.probe);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not check that answer.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLaunchPlaced() {
    setBusy(true);
    setError(null);
    try {
      await onLaunch(doneResult?.starting_component?.id ?? undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open your starting topic.");
      setBusy(false);
    }
  }

  // Keep tutorId referenced clearly for parent callbacks (launched via onLaunch closure).
  void tutorId;

  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={() => (!busy ? onClose() : undefined)}>
      <div
        className="prompt-dialog learn-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="placement-modal-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="placement-modal-title">
              {stage === "choose"
                ? `How would you like to start ${course.title}?`
                : stage === "probe"
                  ? `Find your starting spot · ${course.title}`
                  : "Your starting spot is ready!"}
            </h2>
            <p>
              {stage === "choose"
                ? "Start from Topic 1, or answer a few everyday questions so you can skip what you already know."
                : stage === "probe" && probe
                  ? `Question ${probe.probe_number} of up to ${probe.max_probes} · No grades, no pressure.`
                  : "We found the best place to jump in."}
            </p>
          </div>
          <button type="button" className="learn-btn ghost" disabled={busy} onClick={onClose}>
            Close
          </button>
        </header>

        <div className="prompt-body">
          {error ? (
            <div className="banner" role="alert">
              <p>{error}</p>
            </div>
          ) : null}

          {stage === "choose" ? (
            <div className="learn-entry-options">
              <button
                type="button"
                className="learn-entry-option"
                disabled={busy}
                onClick={() => void handleStartBeginning()}
              >
                <strong>Start from the beginning</strong>
                <p>Explore every topic step by step starting at Topic 1.</p>
              </button>
              <button
                type="button"
                className="learn-entry-option is-recommended"
                disabled={busy}
                onClick={() => void handleStartPlacement()}
              >
                <strong>Find my starting spot ({placementProbeCountLabel(course)})</strong>
                <p>Try a few everyday questions — skip topics you already know, with zero pressure.</p>
              </button>
            </div>
          ) : null}

          {stage === "probe" && probe ? (
            <div className="learn-placement-probe">
              {feedback ? <p className="learn-placement-feedback">{feedback}</p> : null}
              <p className="learn-placement-prompt">{probe.prompt}</p>

              {probe.input_mode === "choice" && probe.choices.length > 0 ? (
                <div className="learn-placement-choices">
                  {probe.choices.map((choice) => {
                    const isUnsure = choice.id === probe.unsure_choice_id;
                    return (
                      <button
                        key={choice.id}
                        type="button"
                        className={`learn-placement-choice${isUnsure ? " is-unsure" : ""}`}
                        disabled={busy}
                        onClick={() =>
                          void submitProbe(isUnsure ? { choice_id: choice.id, unsure: true } : { choice_id: choice.id })
                        }
                      >
                        {choice.text}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <form
                  className="learn-placement-open"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!openAnswer.trim()) return;
                    void submitProbe({ answer: openAnswer.trim() });
                  }}
                >
                  <textarea
                    rows={3}
                    value={openAnswer}
                    onChange={(event) => setOpenAnswer(event.target.value)}
                    placeholder="Share your quick idea in your own words…"
                    disabled={busy}
                  />
                  <div className="learn-actions">
                    <button
                      type="button"
                      className="learn-btn ghost"
                      disabled={busy}
                      onClick={() => void submitProbe({ unsure: true })}
                    >
                      {probe.unsure_label || "Not sure yet — teach me this!"}
                    </button>
                    <button type="submit" className="learn-btn primary" disabled={busy || !openAnswer.trim()}>
                      {busy ? "Checking…" : "Check answer"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          ) : null}

          {stage === "done" && doneResult ? (
            <div className="learn-placement-summary">
              <p className="learn-placement-prompt">{doneResult.message}</p>
              {doneResult.surmised_count ? (
                <p className="learn-quiet">
                  Credited {doneResult.surmised_count} earlier topic{doneResult.surmised_count === 1 ? "" : "s"} in{" "}
                  {doneResult.probes_used} quick question{doneResult.probes_used === 1 ? "" : "s"}.
                </p>
              ) : null}
              <div className="learn-actions">
                <span />
                <button
                  type="button"
                  className="learn-btn primary"
                  disabled={busy}
                  onClick={() => void handleLaunchPlaced()}
                >
                  {doneResult.starting_component
                    ? `Start at ${doneResult.starting_component.title} →`
                    : "Start learning →"}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
