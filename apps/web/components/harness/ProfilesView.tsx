"use client";

import Link from "next/link";

import { TRAIT_FIELDS, traitSentence } from "@/lib/harness";

export type HarnessPersona = {
  id: string;
  number: number;
  name: string;
  description: string;
  age: number;
  child_profile: Record<string, string | string[]>;
  traits: Record<string, number>;
  archived?: boolean;
};

function profileLine(profile: HarnessPersona["child_profile"]): string {
  const tags = Array.isArray(profile.interest_tags) ? profile.interest_tags.join(", ") : "";
  return [
    profile.grade_band,
    profile.reading_level,
    profile.response_length,
    profile.expression_style,
    profile.explanation_style,
    profile.challenge_appetite,
    profile.communication_tone,
    profile.learning_support,
    tags,
    profile.interests ? `favorites: ${profile.interests}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

export function ProfilesView({ personas, heading = "Profiles" }: { personas: HarnessPersona[]; heading?: string }) {
  const rows = personas.filter((persona) => !persona.archived);
  return (
    <section className="harness-panel" aria-label={heading}>
      <header className="harness-panel-head">
        <h2>{heading}</h2>
        <p className="help">
          What the tutor is told is the Layer 2 row. Hidden traits are how the child actually behaves.{" "}
          <Link href="/kc-test-children/profiles">Open the profiles page</Link>
        </p>
      </header>
      {rows.length === 0 ? <p className="help">No test children yet. Add the starter set from the Children tab.</p> : null}
      <ul className="harness-profile-list">
        {rows.map((persona) => (
          <li key={persona.id} className="harness-card">
            <h3>
              {persona.name} <span className="help">{persona.description}</span>
            </h3>
            <p>Age {persona.age}</p>
            <p>
              <strong>Tutor is told.</strong> {profileLine(persona.child_profile)}
            </p>
            <ul className="harness-traits">
              {TRAIT_FIELDS.map((field) => (
                <li key={field.key}>
                  <span>{field.label}</span>
                  <strong>{persona.traits[field.key] ?? 3}</strong>
                  <small>{traitSentence(field, Number(persona.traits[field.key] ?? 3))}</small>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}
