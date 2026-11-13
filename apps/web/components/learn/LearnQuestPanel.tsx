"use client";

import Link from "next/link";

import { BrandMark } from "@/components/BrandMark";
import { TutorAvatar } from "@/components/TutorAvatar";
import type { KcProgress, KcTutorSession } from "@/lib/kc";
import { displayChildStatus, topicStars } from "@/lib/learn";
import type { TutorProfile } from "@/lib/types";

export type TutorMood = "ready" | "thinking" | "first_try" | "retry";

const MOOD_LINE: Record<TutorMood, string> = {
  ready: "Ready to explore together!",
  thinking: "Thinking of a great hint...",
  first_try: "Boom! Nailed it on the first try!",
  retry: "Let's break this down step by step.",
};

export function LearnCourseBar({
  homeHref,
  title,
  done,
  total,
  stars,
  tutor,
  debugOpen,
  panelOpen,
  onDebug,
  onPanel,
}: {
  homeHref: string;
  title: string;
  done: number;
  total: number;
  stars: number;
  tutor: { name?: string; avatar_preset?: string; avatar_url?: string | null; description?: string };
  debugOpen: boolean;
  panelOpen: boolean;
  onDebug: () => void;
  onPanel: () => void;
}) {
  return (
    <header className="learn-course-bar">
      <BrandMark />
      <div className="learn-course-title">
        <Link href={homeHref} className="learn-back">
          ← Back to My Courses
        </Link>
        <h1>{title}</h1>
        <span className="learn-pill">
          {done}/{total} Topics Done · ★ {stars}
        </span>
      </div>
      <div className="learn-course-tools">
        <button type="button" className="learn-btn ghost learn-panel-toggle" aria-pressed={panelOpen} onClick={onPanel}>
          Quest map
        </button>
        <span className="learn-tutor-chip" title={tutor.description || tutor.name || "Tutor"}>
          <TutorAvatar preset={tutor.avatar_preset} avatarUrl={tutor.avatar_url} name={tutor.name} size="sm" />
          <strong>{tutor.name || "Tutor"}</strong>
        </span>
        <button
          type="button"
          className="learn-btn"
          aria-pressed={debugOpen}
          aria-expanded={debugOpen}
          aria-controls="kc-debug-panel"
          onClick={onDebug}
        >
          {debugOpen ? "Hide Debug" : "Debug"}
        </button>
      </div>
    </header>
  );
}

export function LearnQuestPanel({
  tutor,
  mood,
  progress,
  session,
  activeId,
  onOpenTopic,
}: {
  tutor: TutorProfile;
  mood: TutorMood;
  progress: KcProgress | null;
  session: KcTutorSession | null;
  activeId: string;
  onOpenTopic: (kcId: string) => void;
}) {
  const topics = (progress?.units ?? []).filter((unit) => !unit.patch);
  const discovered = topics.filter((unit) => unit.status === "completed" && (unit.core_truth || "").trim());
  return (
    <div className="cb-quest-stack">
      <p className="cb-muted-copy" role="status">
        {tutor.name || "Tutor"} · {MOOD_LINE[mood]}
      </p>
      <ol className="cb-topic-list" aria-label="Course quest trail">
        {topics.map((unit, index) => {
          const label = displayChildStatus(unit.child_status, unit.status, unit.mastery);
          const selectable = label === "Locked" ? "Up Next" : label;
          const shown =
            unit.practice_bonus && label === "Completed" ? "Completed (Practice Bonus Available)" : selectable;
          const active = unit.id === activeId;
          const done = label === "Mastered" || label === "Completed";
          const locked = label === "Locked";
          const stars = topicStars(unit);
          return (
            <li key={unit.id}>
              <button
                type="button"
                className={`cb-topic${active ? " is-current" : ""}${locked ? " is-locked" : ""}`}
                onClick={() => onOpenTopic(unit.id)}
              >
                <span className={`cb-num${done ? " is-done" : ""}`}>{index + 1}</span>
                <span>
                  <strong>{unit.title}</strong>
                  <small>
                    {active ? "Here now" : shown}
                    {unit.status === "completed" ? ` · ${stars} stars` : ""}
                  </small>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <article>
        <h2 className="cb-course-title">What I&apos;ve discovered</h2>
        {discovered.length === 0 ? <p className="cb-muted-copy">Core ideas show up here as you finish topics.</p> : null}
        <ul className="cb-topic-list">
          {discovered.map((unit) => (
            <li key={unit.id}>
              <strong>{unit.title}</strong>
              <p className="cb-muted-copy">{unit.core_truth}</p>
            </li>
          ))}
        </ul>
      </article>
    </div>
  );
}

