"use client";

import { useState } from "react";
import Link from "next/link";

import { BrandMark } from "@/components/BrandMark";
import { ChildMark } from "@/components/learn/ChildFields";
import { ParentFrame } from "@/components/parent/ParentFrame";
import { gradePill } from "@/lib/learn";
import { parentChats, parentProgress, type Parent } from "@/lib/parent";
import type { Student } from "@/lib/types";

export function ParentDashboard({ parent, learners }: { parent: Parent; learners: Student[] }) {
  const [pickedId, setPickedId] = useState<string | null>(learners.length === 1 ? learners[0].id : null);
  const picked = learners.find((child) => child.id === pickedId) ?? null;

  return (
    <ParentFrame parentId={parent.id} parentName={parent.name} studentId={picked?.id} current="home">
      <div className="parent-work">
        <BrandMark />
        <header className="parent-work-head">
          <h1>Hello, {parent.name}</h1>
          <p>Choose a child, then look at their chats or their progress.</p>
        </header>
        <p className="parent-links">
          <Link className="learn-text-link" href="/parent">
            Switch parent
          </Link>
        </p>

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
