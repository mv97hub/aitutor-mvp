"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { BrandMark } from "@/components/BrandMark";
import { initials } from "@/lib/learn";
import { api } from "@/lib/api";
import { childCountLabel, landingPathFor, type Parent } from "@/lib/parent";

export function ParentLanding({ parents, error }: { parents: Parent[]; error: string | null }) {
  const router = useRouter();
  const [adding, setAdding] = useState(parents.length === 0 && !error);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    const cleaned = name.trim();
    if (!cleaned || saving) return;
    setSaving(true);
    setProblem(null);
    try {
      const parent = await api<Parent>("/parents", { method: "POST", body: JSON.stringify({ name: cleaned }) });
      router.push(landingPathFor(parent));
      router.refresh();
    } catch (err) {
      setProblem(err instanceof Error ? err.message : "Could not add that parent.");
      setSaving(false);
    }
  }

  return (
    <main className="learn-shell parent-shell">
      <BrandMark />
      <section className="learn-chooser">
        <p className="eyebrow">Parent portal</p>
        <h1>Who is checking in?</h1>
        <p className="lede">
          Pick your name to see your children&apos;s chats and progress. There is no password yet, so anyone with this
          page can open any parent.
        </p>
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <div className="learn-child-grid">
          {parents.map((parent) => (
            <button
              key={parent.id}
              type="button"
              className="learn-child-card parent-card"
              onClick={() => {
                router.push(landingPathFor(parent));
              }}
            >
              <span className="learn-initials learn-initials-xl" aria-hidden="true">
                {initials(parent.name)}
              </span>
              <strong>{parent.name}</strong>
              <span className="learn-quiet">{childCountLabel(parent.child_count)}</span>
            </button>
          ))}
          {adding ? (
            <form className="learn-child-card learn-add-card parent-add-form" onSubmit={(event) => void create(event)}>
              <label>
                Your name
                <input
                  type="text"
                  name="parent-name"
                  value={name}
                  maxLength={120}
                  autoFocus
                  placeholder="For example, Sam"
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              {problem ? (
                <p className="parent-problem" role="alert">
                  {problem}
                </p>
              ) : null}
              <span className="parent-add-actions">
                <button className="learn-btn primary" type="submit" disabled={saving || name.trim().length === 0}>
                  {saving ? "Adding…" : "Add parent"}
                </button>
                <button className="learn-btn ghost" type="button" onClick={() => setAdding(false)} disabled={saving}>
                  Cancel
                </button>
              </span>
            </form>
          ) : (
            <button type="button" className="learn-child-card learn-add-card" onClick={() => setAdding(true)}>
              <span className="learn-add-mark" aria-hidden="true">
                +
              </span>
              <strong>Add a Parent</strong>
              <span className="learn-quiet">Then choose which children you follow</span>
            </button>
          )}
        </div>
      </section>
    </main>
  );
}
