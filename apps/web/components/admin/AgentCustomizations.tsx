"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { api } from "@/lib/api";
import type { TutorProfile } from "@/lib/types";

const PERSONAS = [
  ["curious-co-explorer", "Curious co-explorer"],
  ["tactical-coach", "Tactical coach"],
  ["debate-moderator", "Debate moderator"],
  ["patient-explainer", "Patient explainer"],
] as const;

const VOICES = [
  ["early-concrete", "Early concrete"],
  ["middle-grade-vivid", "Middle-grade vivid"],
  ["precise-visual", "Precise visual"],
  ["analytical-high-school", "Analytical high-school"],
] as const;

const METAPHORS = [
  ["playground-sports", "Playground and sports"],
  ["buildings-machines", "Buildings and machines"],
  ["policy-cause", "Policy and cause-and-effect"],
  ["none", "None (plain language only)"],
] as const;

const SIDEKICKS = [
  ["bumbling-partner", "Bumbling partner"],
  ["rookie-picture", "Rookie who trusts a picture"],
  ["pundit", "Pundit who skips the chain"],
  ["off", "Off"],
] as const;

const WINDOWS = [
  ["short", "Short (1 miss)"],
  ["standard", "Standard (2)"],
  ["long", "Long (3)"],
] as const;

const VOICE_FOR: Record<string, string> = {
  "curious-co-explorer": "middle-grade-vivid",
  "tactical-coach": "precise-visual",
  "debate-moderator": "analytical-high-school",
  "patient-explainer": "early-concrete",
};

const INSTRUCTIVE: Record<number, { label: string; detail: string }> = {
  1: {
    label: "Socratic",
    detail: "One short question. Almost no explanation until they try.",
  },
  2: {
    label: "Mostly questions",
    detail: "One short question. A real explanation starts after two misses.",
  },
  3: {
    label: "Balanced",
    detail: "A short explanation, then one question. Today's teach-then-ask.",
  },
  4: {
    label: "Mostly instructive",
    detail: "The fact and why it matters, then one question. The first miss gets the longer explanation.",
  },
  5: {
    label: "Instructive",
    detail:
      "A fuller lesson first: the fact, a picture, why it matters, then one question. Stuck students get the longer explanation sooner.",
  },
};

function Choice({
  label,
  value,
  options,
  help,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly (readonly [string, string])[];
  help?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([id, text]) => (
          <option key={id} value={id}>
            {text}
          </option>
        ))}
      </select>
      {help ? <span className="help">{help}</span> : null}
    </label>
  );
}

export function AgentCustomizations() {
  const [draft, setDraft] = useState<TutorProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api<TutorProfile>("/tutor-profile")
      .then((profile) => {
        if (!cancelled) {
          setDraft(profile);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load the tutor profile.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function setPersona(persona: string) {
    setSaved(false);
    setDraft((current) => {
      if (!current) return current;
      if (current.voice_override) return { ...current, persona };
      return { ...current, persona, lexicon: VOICE_FOR[persona] ?? current.lexicon };
    });
  }

  function setVoice(lexicon: string) {
    setSaved(false);
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        lexicon,
        voice_override: lexicon !== VOICE_FOR[current.persona],
      };
    });
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const savedProfile = await api<TutorProfile>("/tutor-profile", {
        method: "PUT",
        body: JSON.stringify({
          instructive: draft.instructive,
          persona: draft.persona,
          lexicon: draft.lexicon,
          voice_override: draft.voice_override,
          metaphors: draft.metaphors,
          sidekick: draft.sidekick,
          struggle_window: draft.struggle_window,
          anti_spoiler: draft.anti_spoiler,
          one_question: draft.one_question,
          use_interests: draft.use_interests,
          stay_on_course: draft.stay_on_course,
          growth_praise: draft.growth_praise,
        }),
      });
      setDraft(savedProfile);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the tutor profile.");
    } finally {
      setSaving(false);
    }
  }

  const level = draft ? INSTRUCTIVE[draft.instructive] ?? INSTRUCTIVE[3] : INSTRUCTIVE[3];

  return (
    <AdminFrame current="customizations" sidebar={<div className="ds-side-spacer" />}>
      <article className="editor">
        <p className="eyebrow">Administration</p>
        <h2>Agent Customizations</h2>
        <p className="help">
          One tutor profile for every student. Name, age, reading level, modality, and interests stay on the child.
        </p>
        {loading ? <p className="help">Loading the profile.</p> : null}
        {draft ? (
          <form className="agent-form" onSubmit={(event) => void onSubmit(event)}>
            <label>
              How instructive
              <span className="agent-level">
                {draft.instructive} · {level.label}
              </span>
              <input
                type="range"
                min={1}
                max={5}
                step={1}
                value={draft.instructive}
                aria-valuemin={1}
                aria-valuemax={5}
                aria-valuenow={draft.instructive}
                aria-valuetext={`${draft.instructive} ${level.label}. ${level.detail}`}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, instructive: Number(event.target.value) });
                }}
              />
              <span className="agent-scale">
                <span>1 Socratic</span>
                <span>3 Balanced</span>
                <span>5 Instructive</span>
              </span>
              <span className="help">{level.detail}</span>
            </label>
            <Choice
              label="Persona"
              value={draft.persona}
              options={PERSONAS}
              onChange={setPersona}
            />
            <Choice
              label="Reading voice"
              value={draft.lexicon}
              options={VOICES}
              help="Follows the persona unless you pick a different voice."
              onChange={setVoice}
            />
            <Choice
              label="Metaphor set"
              value={draft.metaphors}
              options={METAPHORS}
              onChange={(metaphors) => {
                setSaved(false);
                setDraft({ ...draft, metaphors });
              }}
            />
            <Choice
              label="Sidekick"
              value={draft.sidekick}
              options={SIDEKICKS}
              help="Used only on teach-back."
              onChange={(sidekick) => {
                setSaved(false);
                setDraft({ ...draft, sidekick });
              }}
            />
            <Choice
              label="Struggle window"
              value={draft.struggle_window}
              options={WINDOWS}
              help="Then the tutor states the worked answer and explains why."
              onChange={(struggle_window) => {
                setSaved(false);
                setDraft({ ...draft, struggle_window });
              }}
            />
            <label className="check">
              <input
                type="checkbox"
                checked={draft.anti_spoiler}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, anti_spoiler: event.target.checked });
                }}
              />
              <span>
                Anti-spoiler
                <span className="help">
                  On: hide the answer until the struggle window. Off: confirm a correct idea as soon as they attempt it.
                </span>
              </span>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={draft.one_question}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, one_question: event.target.checked });
                }}
              />
              <span>
                One question
                <span className="help">On: never stack a second question.</span>
              </span>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={draft.use_interests}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, use_interests: event.target.checked });
                }}
              />
              <span>
                Use student interests
                <span className="help">
                  On: hobbies appear inside examples. Off: examples stay on the subject.
                </span>
              </span>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={draft.stay_on_course}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, stay_on_course: event.target.checked });
                }}
              />
              <span>
                Stay on the course
                <span className="help">
                  On: go deep on this course, unit, and quest, including closely related ideas. A different subject gets a short acknowledgment, then back to the course. Off: the tutor can follow the student's tangent.
                </span>
              </span>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={draft.growth_praise}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, growth_praise: event.target.checked });
                }}
              />
              <span>
                Growth-mindset praise only
                <span className="help">On by default. Turn it off to allow praise for a correct result.</span>
              </span>
            </label>
            {error ? (
              <div className="banner" role="alert">
                <p>{error}</p>
              </div>
            ) : null}
            {saved ? <p className="note">Saved. This profile applies to every student.</p> : null}
            <div className="rail-actions">
              <button className="button" type="submit" disabled={saving}>
                {saving ? "Saving" : "Save profile"}
              </button>
            </div>
          </form>
        ) : null}
        {!loading && !draft && error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
      </article>
    </AdminFrame>
  );
}
