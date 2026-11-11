"use client";

import { useRef } from "react";

import { TutorAvatar, TutorAvatarPicker } from "@/components/TutorAvatar";
import {
  CHALLENGE_APPETITE_OPTIONS,
  COMMUNICATION_TONE_OPTIONS,
  EXPLANATION_STYLE_OPTIONS,
  EXPRESSION_STYLE_OPTIONS,
  GRADE_BAND_OPTIONS,
  INTEREST_TAG_OPTIONS,
  LEARNING_SUPPORT_OPTIONS,
  READING_LEVEL_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
  gradeBandForAge,
} from "@/lib/kc-layer-fields";
import { KC_MODEL_OPTIONS } from "@/lib/kc-models";
import {
  challengeChoices,
  explanationChoices,
  initials,
  toneChoices,
  type ChildDraft,
} from "@/lib/learn";

export function ChildMark({
  name,
  preset,
  avatarUrl,
  size = "xl",
}: {
  name: string;
  preset?: string;
  avatarUrl?: string;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  if ((preset && preset.length > 0) || (avatarUrl && avatarUrl.length > 0)) {
    return <TutorAvatar preset={preset || "default_circle"} avatarUrl={avatarUrl} name={name} size={size} />;
  }
  return (
    <span className={`learn-initials learn-initials-${size}`} aria-hidden="true">
      {initials(name)}
    </span>
  );
}

export function InterestChips({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  function toggle(tag: string) {
    if (selected.includes(tag)) {
      onChange(selected.filter((item) => item !== tag));
      return;
    }
    if (selected.length < 4) onChange([...selected, tag]);
  }
  return (
    <div className="kc-chip-group" role="group" aria-label="Interest tags">
      {INTEREST_TAG_OPTIONS.map(([id, label]) => {
        const active = selected.includes(id);
        return (
          <button
            key={id}
            type="button"
            className={`kc-chip${active ? " is-active" : ""}`}
            aria-pressed={active}
            onClick={() => toggle(id)}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export function ChoiceChips({
  legend,
  value,
  options,
  onChange,
}: {
  legend: string;
  value: string;
  options: [string, string][];
  onChange: (next: string) => void;
}) {
  return (
    <fieldset className="learn-choices">
      <legend>{legend}</legend>
      <div className="kc-chip-group">
        {options.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`kc-chip${value === id ? " is-active" : ""}`}
            aria-pressed={value === id}
            onClick={() => onChange(id)}
          >
            {label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly (readonly [string, string])[];
  onChange: (next: string) => void;
}) {
  return (
    <label className="learn-field">
      {label}
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([id, text]) => (
          <option key={id} value={id}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

export function PersonaFields({
  draft,
  onChange,
  showAll,
  showAvatar,
  includeCore = true,
}: {
  draft: ChildDraft;
  onChange: (next: ChildDraft) => void;
  showAll: boolean;
  showAvatar: boolean;
  includeCore?: boolean;
}) {
  return (
    <div className="learn-fields">
      {showAvatar ? (
        <TutorAvatarPicker
          preset={draft.avatar_preset || "default_circle"}
          avatarUrl={draft.avatar_url || null}
          onChangePreset={(avatar_preset) =>
            onChange({ ...draft, avatar_preset: avatar_preset === "default_circle" ? "" : avatar_preset, avatar_url: "" })
          }
          onChangeUrl={(avatar_url) => onChange({ ...draft, avatar_url: avatar_url ?? "" })}
        />
      ) : null}
      {showAll ? (
        <>
          <SelectField
            label="Reading level"
            value={draft.reading_level}
            options={READING_LEVEL_OPTIONS}
            onChange={(reading_level) => onChange({ ...draft, reading_level })}
          />
          <SelectField
            label="Response length"
            value={draft.response_length}
            options={RESPONSE_LENGTH_OPTIONS}
            onChange={(response_length) => onChange({ ...draft, response_length })}
          />
          <SelectField
            label="Expression style"
            value={draft.expression_style}
            options={EXPRESSION_STYLE_OPTIONS}
            onChange={(expression_style) => onChange({ ...draft, expression_style })}
          />
          {includeCore ? (
            <>
              <SelectField
                label="Explanation style"
                value={draft.explanation_style}
                options={EXPLANATION_STYLE_OPTIONS}
                onChange={(explanation_style) => onChange({ ...draft, explanation_style })}
              />
              <SelectField
                label="Challenge appetite"
                value={draft.challenge_appetite}
                options={CHALLENGE_APPETITE_OPTIONS}
                onChange={(challenge_appetite) => onChange({ ...draft, challenge_appetite })}
              />
              <SelectField
                label="Communication tone"
                value={draft.communication_tone}
                options={COMMUNICATION_TONE_OPTIONS}
                onChange={(communication_tone) => onChange({ ...draft, communication_tone })}
              />
            </>
          ) : null}
          <SelectField
            label="Learning support"
            value={draft.learning_support}
            options={LEARNING_SUPPORT_OPTIONS}
            onChange={(learning_support) => onChange({ ...draft, learning_support })}
          />
        </>
      ) : null}
    </div>
  );
}

export function BasicsFields({
  draft,
  onChange,
  lockName,
}: {
  draft: ChildDraft;
  onChange: (next: ChildDraft) => void;
  lockName?: boolean;
}) {
  const gradeTouched = useRef(false);
  return (
    <div className="learn-fields">
      {lockName ? (
        <p className="learn-readonly">
          <span>Name</span>
          <strong>{draft.name}</strong>
        </p>
      ) : (
        <label className="learn-field">
          Name
          <input
            value={draft.name}
            onChange={(event) => onChange({ ...draft, name: event.target.value })}
            required
            maxLength={120}
            autoComplete="off"
            aria-label="Name"
          />
        </label>
      )}
      <label className="learn-field">
        Age
        <input
          type="number"
          inputMode="numeric"
          min={4}
          max={18}
          required
          aria-label="Age"
          value={draft.age}
          onChange={(event) => {
            const age = event.target.value;
            const parsed = Number(age);
            onChange({
              ...draft,
              age,
              grade_band: gradeTouched.current ? draft.grade_band : gradeBandForAge(Number.isFinite(parsed) ? parsed : null),
            });
          }}
        />
      </label>
      <SelectField
        label="Grade band"
        value={draft.grade_band}
        options={GRADE_BAND_OPTIONS}
        onChange={(grade_band) => {
          gradeTouched.current = true;
          onChange({ ...draft, grade_band });
        }}
      />
      <SelectField
        label="AI Model"
        value={draft.tutor_model}
        options={KC_MODEL_OPTIONS}
        onChange={(tutor_model) => onChange({ ...draft, tutor_model })}
      />
      <div className="learn-field">
        <span>Interest tags</span>
        <InterestChips
          selected={draft.interest_tags}
          onChange={(interest_tags) => onChange({ ...draft, interest_tags })}
        />
      </div>
      <label className="learn-field">
        Favorite things
        <input
          value={draft.interests}
          maxLength={120}
          aria-label="Favorite things"
          placeholder="Minecraft redstone, golden retrievers, soccer"
          onChange={(event) => onChange({ ...draft, interests: event.target.value })}
        />
      </label>
    </div>
  );
}

export function LearnStyleFields({
  draft,
  onChange,
}: {
  draft: ChildDraft;
  onChange: (next: ChildDraft) => void;
}) {
  return (
    <div className="learn-fields">
      <ChoiceChips
        legend="Explanation style"
        value={draft.explanation_style}
        options={explanationChoices()}
        onChange={(explanation_style) => onChange({ ...draft, explanation_style })}
      />
      <ChoiceChips
        legend="Challenge appetite"
        value={draft.challenge_appetite}
        options={challengeChoices()}
        onChange={(challenge_appetite) => onChange({ ...draft, challenge_appetite })}
      />
      <ChoiceChips
        legend="Communication tone"
        value={draft.communication_tone}
        options={toneChoices()}
        onChange={(communication_tone) => onChange({ ...draft, communication_tone })}
      />
    </div>
  );
}
