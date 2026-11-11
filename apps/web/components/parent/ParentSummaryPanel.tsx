"use client";

import { useState } from "react";

import type { ParentSummary } from "@/lib/parent-summary";

/** A small parent-side chat panel. The reply is generated on click and is not saved. */
export function ParentSummaryPanel({
  parentId,
  studentId,
  sessionId,
  childName,
}: {
  parentId: string;
  studentId: string;
  sessionId: string;
  childName: string;
}) {
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState<ParentSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/parent/summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parentId, studentId, sessionId }),
      });
      if (!response.ok) {
        const text = (await response.text()).trim();
        throw new Error(text || "The summary could not be written.");
      }
      setReply((await response.json()) as ParentSummary);
    } catch (err) {
      setReply(null);
      setError(err instanceof Error ? err.message : "The summary could not be written.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="parent-summary" aria-label="Summary and talking points">
      <div className="parent-summary-head">
        <button type="button" className="button" disabled={busy} onClick={() => void generate()}>
          Generate summary and talking points
        </button>
        <span className="help">A short note about {childName}&apos;s chat. It is not saved.</span>
      </div>
      <div className="parent-summary-thread" role="log" aria-live="polite">
        {busy ? <p className="ds-typing">Writing a note for you…</p> : null}
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        {reply ? (
          <article className="bubble assistant parent-reply" aria-label="Summary and talking points">
            <p>{reply.summary}</p>
            {reply.talking_points.length > 0 ? (
              <>
                <h3>Talking points</h3>
                <ul>
                  {reply.talking_points.map((point, index) => (
                    <li key={`${index}-${point}`}>{point}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </article>
        ) : null}
      </div>
    </section>
  );
}
