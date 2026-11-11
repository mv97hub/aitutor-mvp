"use client";

import Link from "next/link";
import { useState } from "react";

import { when } from "@/components/KcSessionView";
import { ParentFrame } from "@/components/parent/ParentFrame";
import { ProgressRecommend } from "@/components/progress/ProgressRecommend";
import { ProgressTotals } from "@/components/progress/ProgressTotals";
import {
  parentChats,
  parentProgress,
  type Parent,
  type ParentDashboardChild,
  type ParentDashboardSummary,
  type ParentWeekCounts,
} from "@/lib/parent";
import type { Student } from "@/lib/types";

const EMPTY_WEEK: ParentWeekCounts = {
  sessions: 0,
  topics_finished: 0,
  stars: 0,
  blocks_passed: 0,
  blocks_revealed: 0,
  days_active: 0,
};

function sinceMonday(iso: string) {
  const label = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  }).format(new Date(iso));
  return `Since ${label}`;
}

function sumWeek(children: ParentDashboardChild[]): ParentWeekCounts {
  return children.reduce(
    (sum, child) => ({
      sessions: sum.sessions + child.week.sessions,
      topics_finished: sum.topics_finished + child.week.topics_finished,
      stars: sum.stars + child.week.stars,
      blocks_passed: sum.blocks_passed + child.week.blocks_passed,
      blocks_revealed: sum.blocks_revealed + child.week.blocks_revealed,
      days_active: sum.days_active + child.week.days_active,
    }),
    { ...EMPTY_WEEK },
  );
}

function weekIsEmpty(week: ParentWeekCounts) {
  return (
    week.sessions === 0 &&
    week.topics_finished === 0 &&
    week.stars === 0 &&
    week.blocks_passed === 0 &&
    week.blocks_revealed === 0 &&
    week.days_active === 0
  );
}

function latestActive(children: ParentDashboardChild[]): string | null {
  let best: string | null = null;
  let bestAt = Number.NEGATIVE_INFINITY;
  for (const child of children) {
    if (!child.last_active_at) continue;
    const at = Date.parse(child.last_active_at);
    if (Number.isNaN(at) || at < bestAt) continue;
    best = child.last_active_at;
    bestAt = at;
  }
  return best;
}

function nextStepLine(child: ParentDashboardChild, named: boolean) {
  const who = named ? `${child.display_name}: ` : "";
  if (!child.current_course_title) return `${who}No course in progress.`;
  const topic = child.current_topic_title ? ` — ${child.current_topic_title}` : "";
  return `${who}${child.current_course_title}${topic}`;
}

export function ParentDashboard({
  parent,
  learners,
  summary,
  summaryError,
}: {
  parent: Parent;
  learners: Student[];
  summary: ParentDashboardSummary | null;
  summaryError: string | null;
}) {
  const [pickedId, setPickedId] = useState<string | null>(learners.length === 1 ? learners[0].id : null);
  const picked = learners.find((child) => child.id === pickedId) ?? null;
  const household = summary?.children ?? [];
  const scoped = picked ? household.filter((child) => child.student_id === picked.id) : household;
  const showEachChild = !picked && scoped.length > 0;
  const week = sumWeek(scoped);
  const mastered = scoped.reduce((sum, child) => sum + child.topics_mastered, 0);
  const fragile = scoped.reduce((sum, child) => sum + child.topics_fragile, 0);
  const stars = scoped.reduce((sum, child) => sum + child.stars, 0);
  const coursesStarted = scoped.reduce((sum, child) => sum + child.courses_started, 0);
  const coursesFinished = scoped.reduce((sum, child) => sum + child.courses_finished, 0);
  const lastActive = latestActive(scoped);
  const recent = (summary?.recent ?? []).filter((item) => !picked || item.student_id === picked.id);
  const attention = scoped.flatMap((child) =>
    child.attention.map((item, index) => ({
      key: `${child.student_id}-${item.course_id}-${index}`,
      href: parentProgress(parent.id, child.student_id, item.course_id),
      text: showEachChild
        ? `${child.display_name}: ${item.detail ? `${item.title}. ${item.detail}` : item.title}`
        : item.detail
          ? `${item.title}. ${item.detail}`
          : item.title,
    })),
  ).slice(0, 3);
  const anyoneInACourse = scoped.some((child) => child.current_course_title);

  return (
    <ParentFrame
      parentId={parent.id}
      parentName={parent.name}
      studentId={picked?.id}
      learners={learners}
      onStudentChange={setPickedId}
      current="home"
    >
      <div className="parent-work">
        <header className="parent-work-head">
          <h1>Dashboard</h1>
          <p>{parent.name}</p>
        </header>
        <p className="parent-links">
          <Link className="learn-text-link" href="/parent">
            Switch parent
          </Link>
        </p>

        {summaryError ? (
          <div className="banner" role="alert">
            <p>{summaryError}</p>
          </div>
        ) : null}

        <div className="parent-dashboard">
          <section aria-label="This week">
            <h2>This week</h2>
            {summary ? <p>{sinceMonday(summary.week_starts_at)}</p> : null}
            {lastActive ? <p>Last active {when(lastActive)}</p> : null}
            <ProgressTotals
              label="This week"
              items={[
                { label: "Chats", value: week.sessions },
                { label: "Topics finished", value: week.topics_finished },
                { label: "Stars", value: week.stars },
                { label: "Blocks passed", value: week.blocks_passed },
                { label: "Blocks revealed", value: week.blocks_revealed },
                { label: "Days with a chat", value: week.days_active },
              ]}
            />
            {weekIsEmpty(week) ? <p>Nothing this week yet.</p> : null}
            {showEachChild ? (
              <ul className="progress-list" aria-label="Each child this week">
                {scoped.map((child) => (
                  <li key={child.student_id}>
                    <Link href={parentProgress(parent.id, child.student_id)}>
                      <span>{child.display_name}</span>
                      <span className="progress-row-status">
                        {child.week.sessions} chats · {child.week.topics_finished} finished · {child.week.stars} stars
                        · {child.week.blocks_passed} passed · {child.week.blocks_revealed} revealed ·{" "}
                        {child.week.days_active} days
                        {child.last_active_at ? ` · Last active ${when(child.last_active_at)}` : ""}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          <section aria-label="Topics">
            <h2>Topics</h2>
            <ProgressTotals
              label="Topics"
              items={[
                { label: "Mastered", value: mastered },
                { label: "Completed but fragile", value: fragile },
                { label: "Stars", value: stars },
                { label: "Courses started", value: coursesStarted },
                { label: "Courses finished", value: coursesFinished },
              ]}
            />
            {showEachChild ? (
              <ul className="progress-list" aria-label="Each child">
                {scoped.map((child) => (
                  <li key={child.student_id}>
                    <Link href={parentProgress(parent.id, child.student_id)}>
                      <span>{child.display_name}</span>
                      <span className="progress-row-status">
                        {child.topics_mastered} mastered · {child.topics_fragile} fragile · {child.stars} stars ·{" "}
                        {child.courses_started} started · {child.courses_finished} finished
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          <ProgressRecommend heading="Needs attention">
            {attention.length === 0 ? (
              <p>Nothing to revisit.</p>
            ) : (
              <ul>
                {attention.map((item) => (
                  <li key={item.key}>
                    <Link href={item.href}>{item.text}</Link>
                  </li>
                ))}
              </ul>
            )}
          </ProgressRecommend>

          <ProgressRecommend heading="Next step">
            {showEachChild || anyoneInACourse ? (
              <ul>
                {scoped.map((child) => (
                  <li key={child.student_id}>
                    <Link href={parentProgress(parent.id, child.student_id, child.current_course_id || undefined)}>
                      {nextStepLine(child, showEachChild)}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No course in progress.</p>
            )}
          </ProgressRecommend>

          <section aria-label="Recent activity">
            <h2>Recent activity</h2>
            {recent.length === 0 ? <p>No tutor chats yet.</p> : null}
            {recent.length > 0 ? (
              <ul className="progress-list" aria-label="Recent activity">
                {recent.map((item) => (
                  <li key={item.id}>
                    <Link href={parentChats(parent.id, item.student_id)}>
                      <span>
                        {item.student_display_name} · {item.kc_title}
                      </span>
                      <span className="progress-row-status">
                        {item.course_title} · {item.status.replaceAll("_", " ")} · {when(item.updated_at)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        </div>
      </div>
    </ParentFrame>
  );
}
