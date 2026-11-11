"use client";

import { useState } from "react";
import Link from "next/link";

import { ParentFrame } from "@/components/parent/ParentFrame";
import { gradePill } from "@/lib/learn";
import { parentChats, parentProgress, type Parent } from "@/lib/parent";
import type { Student } from "@/lib/types";

export function ParentDashboard({ parent, learners }: { parent: Parent; learners: Student[] }) {
  const [pickedId, setPickedId] = useState<string | null>(learners.length === 1 ? learners[0].id : null);
  const picked = learners.find((child) => child.id === pickedId) ?? null;

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
        </header>

        <section className="parent-child-boxes" aria-label="Your children">
          <div className="progress-portfolio">
            {learners.map((child) => {
              const on = child.id === pickedId;
              return (
                <button
                  key={child.id}
                  type="button"
                  className={`progress-card${on ? " is-selected" : ""}`}
                  aria-pressed={on}
                  onClick={() => setPickedId(child.id)}
                >
                  <strong>{child.display_name}</strong>
                  <span>{gradePill(child.age, child.child_profile?.grade_band || child.grade_band)}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section aria-label={picked ? `${picked.display_name}: chats and progress` : "Chats and progress"}>
          <div className="parent-choice-grid">
            {picked ? (
              <>
                <Link className="parent-choice" href={parentChats(parent.id, picked.id)}>
                  <strong>Chats</strong>
                  <span>Read the conversations with the tutor.</span>
                </Link>
                <Link className="parent-choice" href={parentProgress(parent.id, picked.id)}>
                  <strong>Progress</strong>
                  <span>Courses, finished topics, and where they are now.</span>
                </Link>
              </>
            ) : (
              <>
                <span className="parent-choice is-disabled" aria-disabled="true">
                  <strong>Chats</strong>
                  <span>Choose a child first.</span>
                </span>
                <span className="parent-choice is-disabled" aria-disabled="true">
                  <strong>Progress</strong>
                  <span>Choose a child first.</span>
                </span>
              </>
            )}
          </div>
        </section>
      </div>
    </ParentFrame>
  );
}
