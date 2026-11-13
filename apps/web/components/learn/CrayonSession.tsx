"use client";

import { useState, type ReactNode } from "react";

import { Button, Crayon, SegmentedControl } from "@/components/crayon";

export type CrayonStep = "done" | "current" | "upcoming";

const MODES = [
  { value: "learn", label: "Learn" },
  { value: "practice", label: "Practice" },
  { value: "quiz", label: "Quiz" },
] as const;

export function CrayonSession({
  backHref,
  courseTitle,
  topicTitle,
  goal,
  steps,
  quest,
  tools,
  children,
}: {
  backHref: string;
  courseTitle: string;
  topicTitle: string;
  goal: string;
  steps: readonly CrayonStep[];
  quest: ReactNode;
  tools?: ReactNode;
  children: ReactNode;
}) {
  const [mode, setMode] = useState("learn");
  const pills = steps.length > 0 ? steps : (["upcoming", "upcoming", "upcoming"] as const);

  return (
    <Crayon className="cb-session-page">
      <header className="cb-session-head">
        <img className="cb-logo" src="/kinder-computers-logo.png" alt="" width={32} height={32} />
        <Button square href={backHref} aria-label="Back">
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
            <path d="M14 6 L8 12 L14 18" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
        </Button>
        <div className="cb-session-heading">
          <p className="cb-eyebrow">{topicTitle}</p>
          <h1 className="cb-session-title">{courseTitle}</h1>
        </div>
        <SegmentedControl label="Session mode" value={mode} options={MODES} onChange={setMode} />
        <div className="cb-steps" aria-label="Steps">
          {pills.map((step, index) => (
            <span key={`${step}-${index}`} className={`cb-step is-${step}`} />
          ))}
        </div>
        {tools}
      </header>
      <div className="cb-session-body">
        <aside className="cb-quest" aria-label="Quest map">
          {quest}
        </aside>
        <div className="cb-session-main">
          <details className="cb-topics-acc">
            <summary>Topics</summary>
            {quest}
          </details>
          <section className="cb-chat" aria-label="Lesson">
            <p className="cb-goal">Today&apos;s goal: {goal}</p>
            {children}
          </section>
        </div>
      </div>
    </Crayon>
  );
}
