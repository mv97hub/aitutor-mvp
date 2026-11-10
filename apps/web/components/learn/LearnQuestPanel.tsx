"use client";

import Link from "next/link";

import { TutorAvatar } from "@/components/TutorAvatar";
import type { KcBlockProgress, KcProgress, KcTutorSession } from "@/lib/kc";
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
    <div className="learn-quest-stack">
      <article className={`learn-companion${mood === "thinking" ? " is-thinking" : ""}`}>
        <TutorAvatar preset={tutor.avatar_preset} avatarUrl={tutor.avatar_url} name={tutor.name} size="lg" />
        <h2>{tutor.name || "Tutor"}</h2>
        <p>{tutor.description || "Your guide for this course."}</p>
        <p className="learn-mood" role="status">
          {MOOD_LINE[mood]}
        </p>
      </article>
      <ol className="learn-trail" aria-label="Course quest trail">
        {topics.map((unit, index) => {
          const label = displayChildStatus(unit.child_status, unit.status, unit.mastery);
          const shown = unit.practice_bonus && label === "Completed" ? "Completed (Practice Bonus Available)" : label;
          const locked = label === "Locked";
          const active = unit.id === activeId;
          const stars = topicStars(unit);
          return (
            <li key={unit.id} className={`is-${label.toLowerCase().replace(/\s+/g, "-")}${active ? " is-here" : ""}`}>
              <button type="button" disabled={locked} onClick={() => onOpenTopic(unit.id)}>
                <span className="learn-trail-index">{locked ? "🔒" : label === "Mastered" || label === "Completed" ? "✓" : index + 1}</span>
                <span>
                  <strong>Topic {index + 1}</strong>
                  <small>{unit.title}</small>
                  <small>
                    {active ? "Here Now" : shown}
                    {unit.status === "completed" ? ` · ★ ${stars}` : ""}
                  </small>
                  {active && session?.block_progress?.length ? <BlockDots blocks={session.block_progress} /> : null}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <article className="learn-discovered">
        <h2>What I&apos;ve discovered</h2>
        {discovered.length === 0 ? <p className="learn-quiet">Core ideas show up here as you finish topics.</p> : null}
        <ul>
          {discovered.map((unit) => (
            <li key={unit.id}>
              <strong>{unit.title}</strong>
              <p>{unit.core_truth}</p>
            </li>
          ))}
        </ul>
      </article>
    </div>
  );
}

function BlockDots({ blocks }: { blocks: KcBlockProgress[] }) {
  const active = blocks.find((item) => item.status === "active");
  const step = (active?.index ?? blocks.filter((item) => item.status === "completed").length) + 1;
  return (
    <span className="learn-dots" aria-label={`Step ${Math.min(step, blocks.length)} of ${blocks.length}`}>
      {blocks.map((item) => (
        <i key={item.id} className={`is-${item.status}`} />
      ))}
      <em>
        Step {Math.min(step, blocks.length)} of {blocks.length}
      </em>
    </span>
  );
}
