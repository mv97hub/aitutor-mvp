"use client";

import { FormEvent, useState } from "react";

import { KcBanner } from "@/components/KcBanner";
import { api } from "@/lib/api";
import type { KcCourse } from "@/lib/kc";
import { hoverFor } from "@/lib/kc-layer-fields";
import {
  DEFAULT_TUTOR_PROFILE,
  FIELD_OPTIONS,
  LAYER_HEADINGS,
  applyChild,
  applyResult,
  applyUnit,
  courseLabel,
  emptyTesterValues,
  fieldsForLayer,
  isNumber,
  isReadOnly,
  isTextArea,
  isYesNo,
  selectCourse,
  testerPayload,
  unitsFor,
  type PromptTesterResult,
  type TesterValues,
} from "@/lib/kc-prompt-tester";
import type { Student, TutorProfile } from "@/lib/types";

export function KcPromptTester({
  courses,
  students,
  profile,
  loadError,
}: {
  courses: KcCourse[];
  students: Student[];
  profile: TutorProfile | null;
  loadError: string | null;
}) {
  const [courseId, setCourseId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [childId, setChildId] = useState("");
  const [typeFields, setTypeFields] = useState<Record<string, unknown>>({});
  const [values, setValues] = useState<TesterValues>(() => emptyTesterValues(profile ?? DEFAULT_TUTOR_PROFILE));
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(loadError);
  const [submitting, setSubmitting] = useState(false);

  const course = courses.find((item) => item.id === courseId) ?? null;
  const units = course ? unitsFor(course) : [];

  function setField(name: string, value: string) {
    setValues((current) => ({ ...current, [name]: value }));
  }

  function onCourse(nextId: string) {
    setCourseId(nextId);
    setUnitId("");
    setTypeFields({});
    const next = courses.find((item) => item.id === nextId);
    if (!next) return;
    setValues((current) => selectCourse(current, next));
  }

  function onUnit(nextId: string) {
    setUnitId(nextId);
    if (!course) return;
    const unit = units.find((item) => item.id === nextId);
    if (!unit) return;
    setTypeFields({ ...(unit.component.type_fields ?? {}) });
    setValues((current) => applyUnit(current, course, unit.component));
  }

  function onChild(nextId: string) {
    setChildId(nextId);
    const child = students.find((item) => item.id === nextId);
    if (!child) return;
    setValues((current) => applyChild(current, child));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await api<PromptTesterResult>("/kc/prompt-tester", {
        method: "POST",
        body: JSON.stringify(testerPayload(values, typeFields)),
      });
      setPrompt(result.system_prompt);
      setValues((current) => applyResult(current, result));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The prompt could not be built.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="ds-shell kc-screen kc-prompt-tester">
      <KcBanner name="KC Prompt Tester" />
      <form className="kc-prompt-form" onSubmit={(event) => void onSubmit(event)} autoComplete="off">
        <p className="kc-prompt-note">Change the settings and show the prompt. Nothing is saved.</p>
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        {LAYER_HEADINGS.map((heading) => (
          <section key={heading}>
            <h2>{heading}</h2>
            {heading === "Layer 1, Component" ? (
              <>
                <label>
                  Course
                  <select aria-label="Course" value={courseId} onChange={(event) => onCourse(event.target.value)}>
                    <option value="">{courses.length === 0 ? "No courses yet" : "Choose a course"}</option>
                    {courses.map((item) => (
                      <option key={item.id} value={item.id}>
                        {courseLabel(item)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Unit
                  <select
                    aria-label="Unit"
                    value={unitId}
                    disabled={!course}
                    onChange={(event) => onUnit(event.target.value)}
                  >
                    <option value="">{course && units.length === 0 ? "No units" : "Choose a unit"}</option>
                    {units.map((unit) => (
                      <option key={unit.id} value={unit.id}>
                        {unit.label}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}
            {heading === "Layer 2, Child" ? (
              <label>
                Child
                <select aria-label="Child" value={childId} onChange={(event) => onChild(event.target.value)}>
                  <option value="">{students.length === 0 ? "No children yet" : "Choose a child"}</option>
                  {students.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.display_name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {fieldsForLayer(heading).map((field) => {
              const hover = hoverFor(field.name);
              const value = values[field.name] ?? "";
              return (
                <label key={field.name} title={hover}>
                  <span className="kc-prompt-name">
                    {field.name}
                    {field.kind === "Derived" ? <span className="kc-prompt-derived">Derived</span> : null}
                  </span>
                  <FieldControl
                    name={field.name}
                    hover={hover}
                    value={value}
                    onChange={(next) => setField(field.name, next)}
                  />
                </label>
              );
            })}
          </section>
        ))}
        <button className="button" type="submit" disabled={submitting}>
          {submitting ? "Building the prompt" : "Show prompt"}
        </button>
      </form>
      <section className="kc-prompt-result" aria-live="polite">
        <h2>System prompt</h2>
        {prompt ? <pre>{prompt}</pre> : <p className="kc-prompt-note">Submit the form to see the prompt.</p>}
      </section>
    </main>
  );
}

function FieldControl({
  name,
  hover,
  value,
  onChange,
}: {
  name: string;
  hover: string;
  value: string;
  onChange: (value: string) => void;
}) {
  if (isReadOnly(name)) {
    return (
      <output title={hover} aria-label={name}>
        {value || "—"}
      </output>
    );
  }
  const options = FIELD_OPTIONS[name];
  if (options) {
    return (
      <select title={hover} aria-label={name} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([id, label]) => (
          <option key={id || "unset"} value={id}>
            {label}
          </option>
        ))}
      </select>
    );
  }
  if (isYesNo(name)) {
    return (
      <select title={hover} aria-label={name} value={value === "no" ? "no" : "yes"} onChange={(event) => onChange(event.target.value)}>
        <option value="yes">Yes</option>
        <option value="no">No</option>
      </select>
    );
  }
  if (isTextArea(name)) {
    return (
      <textarea title={hover} aria-label={name} value={value} onChange={(event) => onChange(event.target.value)} />
    );
  }
  return (
    <input
      type={isNumber(name) ? "number" : "text"}
      title={hover}
      aria-label={name}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
