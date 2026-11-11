"use client";

import { useState } from "react";
import Link from "next/link";

import { when } from "@/components/KcSessionView";
import { ChildMark } from "@/components/learn/ChildFields";
import { ParentFrame } from "@/components/parent/ParentFrame";
import { gradePill } from "@/lib/learn";
import {
  parentChats,
  parentProgress,
  type Parent,
  type ParentDashboardChild,
  type ParentDashboardSummary,
} from "@/lib/parent";
import type { Student } from "@/lib/types";

function countWord(count: number, one: string, many: string) {
  return `${count} ${count === 1 ? one : many}`;
}

function sinceMonday(iso: string) {
  const label = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  }).format(new Date(iso));
  return `Since ${label}`;
}

function ProgressLine({ child }: { child: ParentDashboardChild }) {
  const courses = `${countWord(child.courses_started, "course", "courses")} started · ${countWord(child.courses_finished, "course", "courses")} finished`;
  const totals = `${countWord(child.stars, "star", "stars")} · ${countWord(child.finished_topics, "topic", "topics")} finished`;
  const now = child.current_course_title
    ? `Now in ${child.current_course_title}${child.current_topic_title ? ` — ${child.current_topic_title}` : ""}`
    : "No course in progress";
  return (
    <>
      <span>{courses}</span>
      <span className="learn-quiet">{totals}</span>
      <span className="learn-quiet">{now}</span>
    </>
  );
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
  const weekSessions = household.reduce((sum, child) => sum + child.week.sessions, 0);
  const weekTopics = household.reduce((sum, child) => sum + child.week.topics_finished, 0);
  const weekStars = household.reduce((sum, child) => sum + child.week.stars, 0);

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

        <div className="parent-board">
          <section className="parent-board-card" aria-label="Recent activity">
            <h2>Recent activity</h2>
            <p className="learn-quiet">The last 10 tutor chats across your children.</p>
            {summary && summary.recent.length === 0 ? <p className="learn-quiet">No tutor chats yet.</p> : null}
            <ul className="parent-activity">
              {(summary?.recent ?? []).map((item) => (
                <li key={item.id}>
                  <Link href={parentChats(parent.id, item.student_id)}>
                    <strong>
                      {item.student_display_name} · {item.kc_title}
                    </strong>
                    <span className="learn-quiet">
                      {item.course_title} · {item.status.replaceAll("_", " ")} · {when(item.updated_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          <section className="parent-board-card" aria-label="This week">
            <h2>This week</h2>
            <p className="learn-quiet">
              {summary ? sinceMonday(summary.week_starts_at) : "Monday through today, New York time."} Stars count
              topics finished in that time, using the same points the child earns.
            </p>
            {summary ? (
              <p>
                {countWord(weekSessions, "chat", "chats")} · {countWord(weekTopics, "topic", "topics")} finished ·{" "}
                {countWord(weekStars, "star", "stars")}
              </p>
            ) : null}
            <ul className="parent-week-list">
              {household.map((child) => (
                <li key={child.student_id}>
                  <strong>{child.display_name}</strong>
                  <span className="learn-quiet">
                    {countWord(child.week.sessions, "chat", "chats")} ·{" "}
                    {countWord(child.week.topics_finished, "topic", "topics")} finished ·{" "}
                    {countWord(child.week.stars, "star", "stars")}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="parent-board-card" aria-label="Progress">
            <h2>Progress</h2>
            <ul className="parent-week-list">
              {household.map((child) => (
                <li key={child.student_id}>
                  <Link href={parentProgress(parent.id, child.student_id, child.current_course_id || undefined)}>
                    <strong>{child.display_name}</strong>
                    <ProgressLine child={child} />
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          <section className="parent-board-card" aria-label="Pick up where they left off">
            <h2>Pick up where they left off</h2>
            {household.every((child) => !child.current_course_id) ? (
              <p className="learn-quiet">No course in progress.</p>
            ) : null}
            <ul className="parent-week-list">
              {household
                .filter((child) => child.current_course_id)
                .map((child) => (
                  <li key={child.student_id}>
                    <Link href={parentProgress(parent.id, child.student_id, child.current_course_id || undefined)}>
                      <strong>{child.display_name}</strong>
                      <span>{child.current_course_title}</span>
                      {child.current_topic_title ? <span className="learn-quiet">{child.current_topic_title}</span> : null}
                      {child.last_active_at ? (
                        <span className="learn-quiet">Last active {when(child.last_active_at)}</span>
                      ) : null}
                    </Link>
                  </li>
                ))}
            </ul>
          </section>
        </div>

        <section className="learn-section" aria-label="Choose a child">
          <h2>Your children</h2>
          <div className="learn-child-grid parent-child-grid">
            {learners.map((child) => {
              const on = child.id === pickedId;
              return (
                <button
                  key={child.id}
                  type="button"
                  className={`learn-child-card parent-card${on ? " is-picked" : ""}`}
                  aria-pressed={on}
                  onClick={() => setPickedId(child.id)}
                >
                  <ChildMark
                    name={child.display_name}
                    preset={child.child_profile?.avatar_preset}
                    avatarUrl={child.child_profile?.avatar_url}
                  />
                  <strong>{child.display_name}</strong>
                  <span className="learn-pill">
                    {gradePill(child.age, child.child_profile?.grade_band || child.grade_band)}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        {picked ? (
          <section className="learn-section" aria-label={`${picked.display_name}: what to look at`}>
            <h2>{picked.display_name}</h2>
            <div className="parent-choice-grid">
              <Link className="parent-choice" href={parentChats(parent.id, picked.id)}>
                <strong>Chats</strong>
                <span className="learn-quiet">Read the conversations with the tutor, with a short summary on request.</span>
              </Link>
              <Link className="parent-choice" href={parentProgress(parent.id, picked.id)}>
                <strong>Progress</strong>
                <span className="learn-quiet">Courses, finished topics, and where they are now.</span>
              </Link>
            </div>
          </section>
        ) : (
          <p className="learn-quiet parent-hint">Pick a child above to continue.</p>
        )}
      </div>
    </ParentFrame>
  );
}
