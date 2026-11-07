"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { api } from "@/lib/api";
import { hoverFor } from "@/lib/kc-layer-fields";
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
  ["short", "Minimum (1 try)"],
  ["standard", "Standard (2 tries)"],
  ["long", "Wide (3 tries)"],
] as const;

const POLICIES = [["retry_once", "Retry once"]] as const;

const ENRICHMENT = [
  ["direct", "Direct"],
  ["on_request", "On request"],
  ["offer", "Offer"],
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
  title,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly (readonly [string, string])[];
  help?: string;
  title?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label title={title}>
      {label}
      <select title={title} value={value} onChange={(event) => onChange(event.target.value)}>
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
          misconception_policy: draft.misconception_policy || "retry_once",
          self_explanation: draft.self_explanation !== false,
          enrichment: draft.enrichment || "on_request",
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
          One tutor profile for every student. The component, the child, and the feedback loop are not settings on this
          screen. Name, age, reading level, modality, and interests stay on the child.
        </p>
        {loading ? <p className="help">Loading the profile.</p> : null}
        {draft ? (
          <form className="agent-form" onSubmit={(event) => void onSubmit(event)}>
            <h3 className="agent-layer">Layer 3, Voice</h3>
            <Choice
              label="Persona"
              value={draft.persona}
              options={PERSONAS}
              title={hoverFor("Persona")}
              help={hoverFor("Persona")}
              onChange={setPersona}
            />
            <Choice
              label="Reading voice"
              value={draft.lexicon}
              options={VOICES}
              title={hoverFor("Lexicon")}
              help={hoverFor("Lexicon")}
              onChange={setVoice}
            />
            <Choice
              label="Metaphor set"
              value={draft.metaphors}
              options={METAPHORS}
              title={hoverFor("Metaphors")}
              help={hoverFor("Metaphors")}
              onChange={(metaphors) => {
                setSaved(false);
                setDraft({ ...draft, metaphors });
              }}
            />
            <Choice
              label="Sidekick"
              value={draft.sidekick}
              options={SIDEKICKS}
              title={hoverFor("Sidekick")}
              help={hoverFor("Sidekick")}
              onChange={(sidekick) => {
                setSaved(false);
                setDraft({ ...draft, sidekick });
              }}
            />
            <label className="check" title={hoverFor("Use interests")}>
              <input
                type="checkbox"
                checked={draft.use_interests}
                title={hoverFor("Use interests")}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, use_interests: event.target.checked });
                }}
              />
              <span>
                Use interests
                <span className="help">{hoverFor("Use interests")}</span>
              </span>
            </label>
            <h3 className="agent-layer">Layer 4, Guidance</h3>
            <label title={hoverFor("Instructive")}>
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
                title={hoverFor("Instructive")}
                aria-valuemin={1}
                aria-valuemax={5}
                aria-valuenow={draft.instructive}
                aria-valuetext={`${draft.instructive} ${level.label}. ${hoverFor("Instructive")}`}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, instructive: Number(event.target.value) });
                }}
              />
              <span className="agent-scale">
                <span>1 Asks first</span>
                <span>3 Short lead-in</span>
                <span>5 Explains more</span>
              </span>
              <span className="help">{hoverFor("Instructive")}</span>
            </label>
            <Choice
              label="Struggle window"
              value={draft.struggle_window}
              options={WINDOWS}
              title={hoverFor("Struggle window")}
              help={hoverFor("Struggle window")}
              onChange={(struggle_window) => {
                setSaved(false);
                setDraft({ ...draft, struggle_window });
              }}
            />
            <label className="check" title={hoverFor("Stay on course")}>
              <input
                type="checkbox"
                checked={draft.stay_on_course}
                title={hoverFor("Stay on course")}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, stay_on_course: event.target.checked });
                }}
              />
              <span>
                Stay on course
                <span className="help">{hoverFor("Stay on course")}</span>
              </span>
            </label>
            <Choice
              label="Misconception policy"
              value={draft.misconception_policy || "retry_once"}
              options={POLICIES}
              title={hoverFor("Misconception policy")}
              help={hoverFor("Misconception policy")}
              onChange={(misconception_policy) => {
                setSaved(false);
                setDraft({ ...draft, misconception_policy });
              }}
            />
            <Choice
              label="Enrichment"
              value={draft.enrichment || "on_request"}
              options={ENRICHMENT}
              title={hoverFor("Enrichment")}
              help={hoverFor("Enrichment")}
              onChange={(enrichment) => {
                setSaved(false);
                setDraft({ ...draft, enrichment });
              }}
            />
            <label className="check" title={hoverFor("Anti-spoiler")}>
              <input type="checkbox" checked={draft.anti_spoiler} disabled title={hoverFor("Anti-spoiler")} />
              <span>
                Anti-spoiler <span className="deprecated">Deprecated</span>
                <span className="help">{hoverFor("Anti-spoiler")}</span>
              </span>
            </label>
            <label className="check" title={hoverFor("One question")}>
              <input type="checkbox" checked={draft.one_question} disabled title={hoverFor("One question")} />
              <span>
                One question <span className="deprecated">Deprecated</span>
                <span className="help">{hoverFor("One question")}</span>
              </span>
            </label>
            <h3 className="agent-layer">Layer 5, Encouragement</h3>
            <label className="check" title={hoverFor("Growth-mindset praise")}>
              <input type="checkbox" checked={draft.growth_praise} disabled title={hoverFor("Growth-mindset praise")} />
              <span>
                Growth-mindset praise only <span className="deprecated">Deprecated</span>
                <span className="help">{hoverFor("Growth-mindset praise")}</span>
              </span>
            </label>
            <h3 className="agent-layer">Layer 6, Metacognition</h3>
            <label className="check" title={hoverFor("Self-explanation")}>
              <input
                type="checkbox"
                checked={draft.self_explanation !== false}
                title={hoverFor("Self-explanation")}
                onChange={(event) => {
                  setSaved(false);
                  setDraft({ ...draft, self_explanation: event.target.checked });
                }}
              />
              <span>
                Self-explanation
                <span className="help">{hoverFor("Self-explanation")}</span>
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
