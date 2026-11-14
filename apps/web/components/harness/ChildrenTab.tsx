"use client";

import { useState } from "react";

import { BasicsFields, LearnStyleFields, PersonaFields } from "@/components/learn/ChildFields";
import { ProfilesView, type HarnessPersona } from "@/components/harness/ProfilesView";
import { TRAIT_FIELDS, traitSentence } from "@/lib/harness";
import { previewLines } from "@/lib/harness-policy";
import { api } from "@/lib/api";
import type { ChildDraft } from "@/lib/learn";

function draftFrom(persona: HarnessPersona | null): ChildDraft {
  const profile = persona?.child_profile ?? {};
  return {
    name: persona?.name || "AI_Child",
    age: String(persona?.age ?? 10),
    grade_band: String(profile.grade_band || "upper_elementary"),
    reading_level: String(profile.reading_level || "on_grade"),
    response_length: String(profile.response_length || "balanced"),
    expression_style: String(profile.expression_style || "short_phrases"),
    explanation_style: String(profile.explanation_style || "concrete_examples"),
    challenge_appetite: String(profile.challenge_appetite || "steady"),
    communication_tone: String(profile.communication_tone || "warm_and_encouraging"),
    learning_support: String(profile.learning_support || "none"),
    interest_tags: Array.isArray(profile.interest_tags) ? profile.interest_tags.map(String) : [],
    interests: String(profile.interests || ""),
    avatar_preset: "",
    avatar_url: "",
    tutor_model: String(profile.tutor_model || "gpt-4.1"),
  };
}

function profileFrom(draft: ChildDraft): Record<string, unknown> {
  return {
    grade_band: draft.grade_band,
    reading_level: draft.reading_level,
    response_length: draft.response_length,
    expression_style: draft.expression_style,
    explanation_style: draft.explanation_style,
    challenge_appetite: draft.challenge_appetite,
    communication_tone: draft.communication_tone,
    learning_support: draft.learning_support,
    interest_tags: draft.interest_tags,
    interests: draft.interests,
    tutor_model: draft.tutor_model,
  };
}

export function ChildrenTab({
  personas,
  onChange,
}: {
  personas: HarnessPersona[];
  onChange: (next: HarnessPersona[]) => void;
}) {
  const [selected, setSelected] = useState<string>(personas[0]?.id || "");
  const current = personas.find((persona) => persona.id === selected) || null;
  const [description, setDescription] = useState(current?.description || "");
  const [draft, setDraft] = useState<ChildDraft>(draftFrom(current));
  const [traits, setTraits] = useState<Record<string, number>>(current?.traits || {});
  const [preview, setPreview] = useState<string[]>([]);
  const [error, setError] = useState("");

  function open(persona: HarnessPersona) {
    setSelected(persona.id);
    setDescription(persona.description);
    setDraft(draftFrom(persona));
    setTraits(persona.traits);
    setPreview([]);
    setError("");
  }

  async function reload() {
    const next = await api<HarnessPersona[]>("/kc/harness/personas?include_archived=true");
    onChange(next);
    return next;
  }

  async function addStarter() {
    setError("");
    try {
      const next = await api<HarnessPersona[]>("/kc/harness/personas/starter", { method: "POST" });
      onChange(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the starter set.");
    }
  }

  async function addChild() {
    setError("");
    try {
      const created = await api<HarnessPersona>("/kc/harness/personas", {
        method: "POST",
        body: JSON.stringify({ description: "New test child", age: 10, child_profile: profileFrom(draftFrom(null)), traits }),
      });
      const next = await reload();
      const row = next.find((persona) => persona.id === created.id);
      if (row) open(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add a child.");
    }
  }

  async function save() {
    if (!current) return;
    setError("");
    try {
      await api(`/kc/harness/personas/${current.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          description,
          age: Number(draft.age),
          child_profile: profileFrom(draft),
          traits,
        }),
      });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save.");
    }
  }

  async function copyChild() {
    if (!current) return;
    setError("");
    try {
      const created = await api<HarnessPersona>("/kc/harness/personas", {
        method: "POST",
        body: JSON.stringify({
          description: `${description} copy`,
          age: Number(draft.age),
          child_profile: profileFrom(draft),
          traits,
        }),
      });
      const next = await reload();
      const row = next.find((persona) => persona.id === created.id);
      if (row) open(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not copy.");
    }
  }

  async function archive() {
    if (!current) return;
    await api(`/kc/harness/personas/${current.id}`, { method: "PATCH", body: JSON.stringify({ archived: true }) });
    await reload();
  }

  return (
    <div className="harness-split">
      <section className="harness-panel">
        <header className="harness-panel-head">
          <h2>Children</h2>
          <div className="harness-actions">
            <button type="button" onClick={() => void addStarter()}>
              Add the starter set
            </button>
            <button type="button" onClick={() => void addChild()}>
              Add child
            </button>
          </div>
        </header>
        {error ? <p className="banner">{error}</p> : null}
        <ul className="harness-child-list">
          {personas.filter((persona) => !persona.archived).map((persona) => (
            <li key={persona.id}>
              <button type="button" className={persona.id === selected ? "is-active" : ""} onClick={() => open(persona)}>
                <strong>{persona.name}</strong>
                <small>{persona.description || "No description"}</small>
              </button>
            </li>
          ))}
        </ul>
        {current ? (
          <form
            className="harness-editor"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <h3>{current.name}</h3>
            <label>
              Description
              <input value={description} onChange={(event) => setDescription(event.target.value)} maxLength={240} />
            </label>
            <div className="harness-two">
              <div>
                <h4>What the tutor is told</h4>
                <BasicsFields draft={draft} onChange={setDraft} lockName />
                <PersonaFields draft={draft} onChange={setDraft} showAll showAvatar={false} />
                <LearnStyleFields draft={draft} onChange={setDraft} />
              </div>
              <div>
                <h4>How the child behaves</h4>
                {TRAIT_FIELDS.map((field) => {
                  const value = traits[field.key] ?? 3;
                  return (
                    <label key={field.key} className="harness-slider">
                      <span>
                        {field.label} <strong>{value}</strong>
                      </span>
                      <input
                        type="range"
                        min={1}
                        max={5}
                        value={value}
                        aria-label={field.label}
                        onChange={(event) => setTraits({ ...traits, [field.key]: Number(event.target.value) })}
                      />
                      <small>{traitSentence(field, value)}</small>
                    </label>
                  );
                })}
              </div>
            </div>
            <div className="harness-actions">
              <button type="submit">Save</button>
              <button
                type="button"
                onClick={() => setPreview(previewLines(traits, description))}
              >
                Preview
              </button>
              <button type="button" onClick={() => void copyChild()}>
                Copy
              </button>
              <button type="button" onClick={() => void archive()}>
                Archive
              </button>
            </div>
            {preview.length > 0 ? (
              <ul>
                {preview.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : null}
          </form>
        ) : (
          <p className="help">Add the starter set to begin.</p>
        )}
      </section>
      <ProfilesView personas={personas} />
    </div>
  );
}
