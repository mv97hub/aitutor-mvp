"use client";

import { FormEvent, useState } from "react";

import { KcBanner } from "@/components/KcBanner";
import { BlockDataEditor } from "@/components/KcBlockCanvas";
import { ConfigControl } from "@/components/admin/KcTutorConfigFields";
import { api } from "@/lib/api";
import { safetyExcerpt } from "@/lib/ai-safety";
import type { KcBlock, KcBlockType, KcCourse } from "@/lib/kc";
import { BLOCK_LABELS, BLOCK_TYPES, blankData } from "@/lib/kc-blocks";
import { hoverFor } from "@/lib/kc-layer-fields";
import {
  DEFAULT_TUTOR_PROFILE,
  FIELD_OPTIONS,
  INTEREST_TAG_OPTIONS,
  LAYER_HEADINGS,
  activeBlockTypeFor,
  applyChild,
  applyResult,
  applyUnit,
  blocksForUnit,
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
import {
  BLOCK_CONFIG_FIELDS,
  BLOCK_CONFIG_TITLES,
  kcTutorConfigFrom,
  type KcTutorConfig,
} from "@/lib/kc-tutor-config";
import type { Student, TutorProfile } from "@/lib/types";

const TAB_LABEL: Record<(typeof LAYER_HEADINGS)[number], string> = {
  Safety: "Safety",
  "Layer 1, Component": "Component",
  "Layer 2, Child": "Child",
  "Layer 3, Voice": "Voice",
  "Layer 4, Guidance": "Guidance",
  "Layer 5, Encouragement": "Encouragement",
  "Layer 6, Metacognition": "Metacognition",
  "Layer 7, Feedback loop": "Feedback",
};

function layerTabId(heading: string): string {
  return `kc-prompt-tab-${heading.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;
}

export function KcPromptTester({
  courses,
  students,
  profile,
  profiles = [],
  loadError,
}: {
  courses: KcCourse[];
  students: Student[];
  profile: TutorProfile | null;
  profiles?: TutorProfile[];
  loadError: string | null;
}) {
  const [courseId, setCourseId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [childId, setChildId] = useState("");
  const [profileId, setProfileId] = useState(profile?.id || "default");
  const [typeFields, setTypeFields] = useState<Record<string, unknown>>({});
  const [blocks, setBlocks] = useState<KcBlock[]>([]);
  const [values, setValues] = useState<TesterValues>(() => emptyTesterValues(profile ?? DEFAULT_TUTOR_PROFILE));
  const [tutorConfig, setTutorConfig] = useState<KcTutorConfig>(() =>
    kcTutorConfigFrom(profile?.kc_tutor_config),
  );
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(loadError);
  const [submitting, setSubmitting] = useState(false);
  const [blockIndex, setBlockIndex] = useState(0);
  const [layer, setLayer] = useState<(typeof LAYER_HEADINGS)[number]>("Layer 1, Component");

  const course = courses.find((item) => item.id === courseId) ?? null;
  const units = course ? unitsFor(course) : [];
  const activeIndex = blocks.length ? Math.min(Math.max(blockIndex, 0), blocks.length - 1) : 0;
  const activeBlock = blocks[activeIndex];
  const activeBlockType = activeBlockTypeFor(values, blocks);

  function setField(name: string, value: string) {
    setValues((current) => ({ ...current, [name]: value }));
    if (name === "Move index") {
      const next = Number(value);
      if (Number.isFinite(next)) setBlockIndex(Math.max(0, Math.trunc(next) - 1));
    }
  }

  function onBlock(nextIndex: number) {
    setBlockIndex(nextIndex);
    setValues((current) => ({ ...current, "Move index": String(nextIndex + 1) }));
  }

  function setActiveBlockConfig(key: string, value: string | number | boolean) {
    setTutorConfig((current) => ({
      ...current,
      blocks: {
        ...current.blocks,
        [activeBlockType]: {
          ...current.blocks[activeBlockType],
          [key]: value,
        },
      },
    }));
  }

  function onCourse(nextId: string) {
    setCourseId(nextId);
    setUnitId("");
    setBlockIndex(0);
    setTypeFields({});
    setBlocks([]);
    const next = courses.find((item) => item.id === nextId);
    if (!next) return;
    setValues((current) => selectCourse(current, next));
  }

  function onUnit(nextId: string) {
    setUnitId(nextId);
    setBlockIndex(0);
    if (!course) return;
    const unit = units.find((item) => item.id === nextId);
    if (!unit) return;
    setTypeFields({ ...(unit.component.type_fields ?? {}) });
    setBlocks(blocksForUnit(unit.component));
    setValues((current) => applyUnit({ ...current, "Move index": "1" }, course, unit.component));
  }

  function onChild(nextId: string) {
    setChildId(nextId);
    const child = students.find((item) => item.id === nextId);
    if (!child) return;
    setValues((current) => applyChild(current, child));
  }

  function onProfile(nextId: string) {
    setProfileId(nextId);
    const chosen = profiles.find((item) => item.id === nextId) ?? profile;
    if (!chosen) return;
    const freshDefaults = emptyTesterValues(chosen);
    setValues((current) => ({
      ...current,
      Persona: freshDefaults.Persona,
      "Vocabulary register": freshDefaults["Vocabulary register"],
      "Interest weaving": freshDefaults["Interest weaving"],
      Metaphors: freshDefaults.Metaphors,
      "Humor and wit": freshDefaults["Humor and wit"],
      Sidekick: freshDefaults.Sidekick,
      "Orient framing": freshDefaults["Orient framing"],
      "Instructional stance": freshDefaults["Instructional stance"],
      "Scaffolding escalation": freshDefaults["Scaffolding escalation"],
      "Stay on course": freshDefaults["Stay on course"],
      "Misconception policy": freshDefaults["Misconception policy"],
      "Prerequisite support policy": freshDefaults["Prerequisite support policy"],
      "Encouragement style": freshDefaults["Encouragement style"],
      "Close summary depth": freshDefaults["Close summary depth"],
    }));
    setTutorConfig(kcTutorConfigFrom(chosen.kc_tutor_config));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await api<PromptTesterResult>("/kc/prompt-tester", {
        method: "POST",
        body: JSON.stringify(testerPayload(values, typeFields, blocks, tutorConfig)),
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
      <div className="kc-prompt-workspace">
        <p className="kc-prompt-note">Change the settings and show the prompt. Nothing is saved.</p>
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <div className="kc-prompt-tabs" role="tablist" aria-label="Prompt layers">
          {LAYER_HEADINGS.map((heading) => {
            const selected = layer === heading;
            return (
              <button
                key={heading}
                type="button"
                role="tab"
                id={layerTabId(heading)}
                className={`kc-prompt-tab${selected ? " is-active" : ""}`}
                aria-selected={selected}
                aria-controls="kc-prompt-layer"
                tabIndex={selected ? 0 : -1}
                onClick={() => setLayer(heading)}
              >
                {TAB_LABEL[heading]}
              </button>
            );
          })}
        </div>
        <div className="kc-prompt-columns">
      <form id="kc-prompt-form" className="kc-prompt-form" onSubmit={(event) => void onSubmit(event)} autoComplete="off">
        {LAYER_HEADINGS.map((heading) =>
          heading === layer ? (
          <div key={heading} role="tabpanel" id="kc-prompt-layer" aria-labelledby={layerTabId(heading)}>
            {heading === "Safety" ? (
              <div>
                <p className="kc-prompt-note">
                  Safety is global. It is the first section and overrides persona, child preferences, humor, and block
                  rules.
                </p>
                <pre aria-label="Safety text">
                  {safetyExcerpt(prompt) || "Show the prompt to see the Safety section."}
                </pre>
              </div>
            ) : null}
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
                {blocks.length > 0 ? (
                  <label>
                    Block
                    <select
                      aria-label="Block"
                      value={String(activeIndex)}
                      onChange={(event) => onBlock(Number(event.target.value))}
                    >
                      {blocks.map((block, index) => (
                        <option key={block.id || index} value={String(index)}>
                          {`Block ${index + 1} of ${blocks.length}: ${BLOCK_LABELS[block.type]}`}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                {activeBlock ? (
                  <div className="kc-block-body">
                    <label>
                      Block type
                      <select
                        aria-label="Active block type"
                        value={activeBlock.type}
                        onChange={(event) => {
                          const type = event.target.value as KcBlockType;
                          setBlocks((current) =>
                            current.map((item, index) =>
                              index === activeIndex ? { ...item, type, data: blankData(type) } : item,
                            ),
                          );
                        }}
                      >
                        {BLOCK_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {BLOCK_LABELS[type]}
                          </option>
                        ))}
                      </select>
                    </label>
                    <BlockDataEditor
                      block={activeBlock}
                      onChange={(data) =>
                        setBlocks((current) =>
                          current.map((item, index) => (index === activeIndex ? { ...item, data } : item)),
                        )
                      }
                    />
                  </div>
                ) : null}
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
            {heading === "Layer 3, Voice" && profiles.length > 0 ? (
              <label>
                Tutor Profile
                <select aria-label="Tutor Profile" value={profileId} onChange={(event) => onProfile(event.target.value)}>
                  {profiles.map((item) => (
                    <option key={item.id || item.slug} value={item.id || "default"}>
                      {item.name || "Default"} ({item.slug || item.id || "default"})
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
            {heading === "Layer 4, Guidance" ? (
              <div className="kc-block-body" aria-label={`Active block rules: ${BLOCK_CONFIG_TITLES[activeBlockType]}`}>
                <p>
                  <strong>Active block rules ({BLOCK_CONFIG_TITLES[activeBlockType]})</strong>
                </p>
                {BLOCK_CONFIG_FIELDS[activeBlockType].map((bfield) => (
                  <ConfigControl
                    key={`${activeBlockType}-${bfield.key}`}
                    field={bfield}
                    value={tutorConfig.blocks[activeBlockType]?.[bfield.key]}
                    onChange={(next) => setActiveBlockConfig(bfield.key, next)}
                  />
                ))}
              </div>
            ) : null}
          </div>
          ) : null,
        )}
      </form>
      <section className="kc-prompt-result" aria-live="polite">
        <div className="kc-prompt-pin">
          <button className="button" type="submit" form="kc-prompt-form" disabled={submitting}>
            {submitting ? "Building the prompt" : "Show prompt"}
          </button>
        </div>
        <div className="kc-prompt-output">
          <h2>System prompt</h2>
          {prompt ? <pre>{prompt}</pre> : <p className="kc-prompt-note">Show the prompt to see it here.</p>}
        </div>
      </section>
        </div>
      </div>
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
  if (name === "Interest tags") {
    const selected = value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    function toggle(tag: string) {
      const next = selected.includes(tag)
        ? selected.filter((item) => item !== tag)
        : selected.length < 4
          ? [...selected, tag]
          : selected;
      onChange(next.join(", "));
    }
    return (
      <div className="kc-chip-group" role="group" aria-label={name} title={hover}>
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
  const options = FIELD_OPTIONS[name];
  if (options) {
    const hasCurrent = value === "" || options.some(([id]) => id === value);
    return (
      <select title={hover} aria-label={name} value={value} onChange={(event) => onChange(event.target.value)}>
        {!hasCurrent ? <option value={value}>{value}</option> : null}
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
