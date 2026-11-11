"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { BrandMark } from "@/components/BrandMark";
import { ChildMark } from "@/components/learn/ChildFields";
import { ParentFrame } from "@/components/parent/ParentFrame";
import { api } from "@/lib/api";
import { gradePill } from "@/lib/learn";
import { parentHome, toggledIds, type Parent } from "@/lib/parent";
import type { Student } from "@/lib/types";

export function ParentSettings({
  parent,
  students,
  linkedIds,
  error,
}: {
  parent: Parent;
  students: Student[];
  linkedIds: string[];
  error: string | null;
}) {
  const router = useRouter();
  const [picked, setPicked] = useState<string[]>(linkedIds);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(error);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setProblem(null);
    setNotice(null);
    try {
      await api<Student[]>(`/parents/${parent.id}/students`, {
        method: "PUT",
        body: JSON.stringify({ student_ids: picked }),
      });
      if (picked.length > 0) {
        router.push(parentHome(parent.id));
        router.refresh();
        return;
      }
      setNotice("Saved. No children are linked, so there is nothing to open yet.");
    } catch (err) {
      setProblem(err instanceof Error ? err.message : "Could not save your children.");
    } finally {
      setSaving(false);
    }
  }

  const onlyChild = linkedIds.length === 1 ? linkedIds[0] : null;

  return (
    <ParentFrame parentId={parent.id} parentName={parent.name} studentId={onlyChild} current="settings">
      <div className="parent-work">
        <BrandMark />
        <header className="parent-work-head">
          <h1>Your children</h1>
          <p>Tick the children you want to follow. You can change this any time.</p>
        </header>
        <p className="parent-links">
          <Link className="learn-text-link" href="/parent">
            Switch parent
          </Link>
        </p>
      {problem ? (
        <div className="banner" role="alert">
          <p>{problem}</p>
        </div>
      ) : null}
      <form className="parent-settings-form" onSubmit={(event) => void save(event)}>
        {students.length === 0 ? <p className="learn-quiet">No children have been added yet.</p> : null}
        <ul className="parent-check-list" aria-label="Children">
          {students.map((student) => {
            const on = picked.includes(student.id);
            return (
              <li key={student.id}>
                <label className={`parent-check${on ? " is-on" : ""}`}>
                  <input
                    type="checkbox"
                    checked={on}
                    disabled={saving}
                    onChange={(event) => setPicked((current) => toggledIds(current, student.id, event.target.checked))}
                  />
                  <ChildMark
                    name={student.display_name}
                    preset={student.child_profile?.avatar_preset}
                    avatarUrl={student.child_profile?.avatar_url}
                    size="md"
                  />
                  <span>
                    <strong>{student.display_name}</strong>
                    <span className="learn-quiet">
                      {gradePill(student.age, student.child_profile?.grade_band || student.grade_band)}
                    </span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        <div className="parent-actions">
          <button className="learn-btn primary" type="submit" disabled={saving || students.length === 0}>
            {saving ? "Saving…" : "Save children"}
          </button>
          <span className="learn-quiet" role="status" aria-live="polite">
            {notice ?? `${picked.length} selected`}
          </span>
        </div>
      </form>
      </div>
    </ParentFrame>
  );
}
