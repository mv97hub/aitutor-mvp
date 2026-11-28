"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { retentionPercent } from "@/lib/f5-placement";
import type { KcWarmupItem, KcWarmupSubmitResponse } from "@/lib/kc";

export function MemoryWarmupCard({
  studentId,
  courseId,
  warmups,
}: {
  studentId: string;
  courseId: string;
  warmups: KcWarmupItem[];
}) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<KcWarmupSubmitResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!warmups.length) return null;
  const active = warmups[0];

  async function submit(payload: { choice_id?: string; answer?: string }) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api<KcWarmupSubmitResponse>(
        `/kc/tutor/courses/${courseId}/warmups/${active.kc_id}/submit`,
        {
          method: "POST",
          body: JSON.stringify({ student_id: studentId, ...payload }),
        },
      );
      setResult(res);
      setAnswer("");
      if (res.passed) {
        router.refresh();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not check that warmup.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="learn-warmup-card" aria-label="Quick memory boost">
      <div className="learn-warmup-head">
        <div>
          <p className="eyebrow">Quick 2-min memory boost</p>
          <strong>{active.title}</strong>
        </div>
        <span className="learn-warmup-pill">{retentionPercent(active)}% fresh</span>
      </div>

      {!expanded && !result ? (
        <div className="learn-warmup-intro">
          <p className="learn-quiet">
            It&apos;s been a little while since you practiced this. One quick recall keeps it locked in!
          </p>
          <button type="button" className="learn-btn primary" onClick={() => setExpanded(true)}>
            Do 2-min boost
          </button>
        </div>
      ) : null}

      {expanded && !result ? (
        <div className="learn-warmup-body">
          <p className="learn-warmup-prompt">{active.prompt}</p>
          {error ? (
            <p className="learn-warmup-error" role="alert">
              {error}
            </p>
          ) : null}
          {active.input_mode === "choice" && active.choices.length > 0 ? (
            <div className="learn-placement-choices">
              {active.choices.map((choice) => (
                <button
                  key={choice.id}
                  type="button"
                  className="learn-placement-choice"
                  disabled={busy}
                  onClick={() => void submit({ choice_id: choice.id })}
                >
                  {choice.text}
                </button>
              ))}
            </div>
          ) : (
            <form
              className="learn-warmup-form"
              onSubmit={(event) => {
                event.preventDefault();
                if (!answer.trim()) return;
                void submit({ answer: answer.trim() });
              }}
            >
              <input
                type="text"
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                placeholder="Type what you remember…"
                disabled={busy}
              />
              <button type="submit" className="learn-btn primary" disabled={busy || !answer.trim()}>
                {busy ? "Checking…" : "Check"}
              </button>
            </form>
          )}
        </div>
      ) : null}

      {result ? (
        <div className="learn-warmup-result">
          <p>{result.feedback}</p>
          {!result.passed ? (
            <button
              type="button"
              className="learn-btn"
              onClick={() => {
                setResult(null);
                setExpanded(true);
              }}
            >
              Try once more
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
