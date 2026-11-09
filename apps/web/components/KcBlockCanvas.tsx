"use client";

import { useEffect, useId, useRef, useState, useTransition } from "react";

import { saveKcBlockScope } from "@/lib/kc-actions";
import {
  BLOCK_LABELS,
  BLOCK_TYPES,
  blankBlock,
  blankChoice,
  blankData,
  newBlockId,
  scopeFromCourse,
  toggleScope,
  type McqChoice,
  type WorkedStep,
} from "@/lib/kc-blocks";
import type { KcBlock, KcBlockType } from "@/lib/kc";

export function KcBlockScope({
  courseId,
  nodeId,
  model,
  allowed,
  surface = "creator",
}: {
  courseId: string;
  nodeId: string;
  model: string;
  allowed: readonly string[] | null | undefined;
  surface?: "creator" | "studio";
}) {
  const saved = scopeFromCourse(allowed);
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<KcBlockType[]>(saved);
  const [pending, startTransition] = useTransition();
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setPicked(scopeFromCourse(allowed));
  }, [allowed]);

  useEffect(() => {
    if (!open) return;
    function onPointer(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function commit(next: KcBlockType[]) {
    setPicked(next);
    const data = new FormData();
    data.set("course_id", courseId);
    data.set("node_id", nodeId);
    data.set("model", model);
    if (surface === "studio") data.set("return_to", "studio");
    next.forEach((item) => data.append("allowed_block_types", item));
    startTransition(() => {
      saveKcBlockScope(data);
    });
  }

  return (
    <div className="kc-scope" ref={root}>
      <button
        className="button"
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        disabled={pending}
        onClick={() => setOpen((value) => !value)}
      >
        {picked.length === BLOCK_TYPES.length
          ? "AI Block Scope: All 9 blocks ▾"
          : `AI Block Scope (${picked.length} of 9) ▾`}
      </button>
      {open ? (
        <div className="kc-scope-menu" role="dialog" aria-label="AI Block Scope">
          <div className="kc-scope-actions">
            <button className="ghost" type="button" onClick={() => commit([...BLOCK_TYPES])}>
              Select All
            </button>
            <button className="ghost" type="button" onClick={() => commit(["topic_goal", "mcq"])}>
              Topic + MCQ Only
            </button>
          </div>
          {BLOCK_TYPES.map((type) => (
            <label key={type}>
              <input
                type="checkbox"
                checked={picked.includes(type)}
                onChange={() => commit(toggleScope(picked, type))}
              />
              {BLOCK_LABELS[type]}
            </label>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function KcBlockCanvas({ initial }: { initial: KcBlock[] }) {
  const [blocks, setBlocks] = useState<KcBlock[]>(initial);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  function update(index: number, next: KcBlock) {
    setBlocks(blocks.map((item, itemIndex) => (itemIndex === index ? next : item)));
  }

  function insert(index: number, type: KcBlockType) {
    const next = blocks.slice();
    next.splice(index, 0, blankBlock(type));
    setBlocks(next);
  }

  function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= blocks.length) return;
    const next = blocks.slice();
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item!);
    setBlocks(next);
  }

  function duplicate(index: number) {
    const source = blocks[index];
    if (!source) return;
    const next = blocks.slice();
    next.splice(index + 1, 0, { id: newBlockId(), type: source.type, data: structuredClone(source.data) });
    setBlocks(next);
  }

  return (
    <fieldset className="kc-block-canvas">
      <legend>Blocks</legend>
      <input type="hidden" name="blocks" value={JSON.stringify(blocks)} />
      <div className="kc-block-list">
        <InsertBar onAdd={(type) => insert(0, type)} />
        {blocks.map((block, index) => (
          <div key={block.id}>
            <article className="kc-block-card">
              <div className="kc-block-head">
                <strong>{index + 1}</strong>
                <select
                  aria-label={`Block ${index + 1} type`}
                  value={block.type}
                  onChange={(event) => {
                    const type = event.target.value as KcBlockType;
                    update(index, { ...block, type, data: blankData(type) });
                  }}
                >
                  {BLOCK_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {BLOCK_LABELS[type]}
                    </option>
                  ))}
                </select>
                <div className="kc-block-tools">
                  <button className="ghost" type="button" aria-label={`Move block ${index + 1} up`} onClick={() => move(index, -1)} disabled={index === 0}>
                    Up
                  </button>
                  <button
                    className="ghost"
                    type="button"
                    aria-label={`Move block ${index + 1} down`}
                    onClick={() => move(index, 1)}
                    disabled={index === blocks.length - 1}
                  >
                    Down
                  </button>
                  <button className="ghost" type="button" aria-label={`Duplicate block ${index + 1}`} onClick={() => duplicate(index)}>
                    Duplicate
                  </button>
                  <button
                    className="ghost"
                    type="button"
                    aria-label={collapsed[block.id] ? `Expand block ${index + 1}` : `Collapse block ${index + 1}`}
                    onClick={() => setCollapsed({ ...collapsed, [block.id]: !collapsed[block.id] })}
                  >
                    {collapsed[block.id] ? "Expand" : "Collapse"}
                  </button>
                  <button
                    className="ghost"
                    type="button"
                    aria-label={`Delete block ${index + 1}`}
                    onClick={() => setBlocks(blocks.filter((item) => item.id !== block.id))}
                  >
                    Delete
                  </button>
                </div>
              </div>
              {collapsed[block.id] ? null : (
                <div className="kc-block-body">
                  <BlockDataEditor
                    block={block}
                    onChange={(data) => update(index, { ...block, data })}
                  />
                </div>
              )}
            </article>
            <InsertBar onAdd={(type) => insert(index + 1, type)} />
          </div>
        ))}
      </div>
    </fieldset>
  );
}

function InsertBar({ onAdd }: { onAdd: (type: KcBlockType) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="kc-block-gap">
      <button className="ghost" type="button" onClick={() => setOpen((value) => !value)}>
        {open ? "Close" : "Add block"}
      </button>
      {open ? (
        <div className="kc-block-add">
          {BLOCK_TYPES.map((type) => (
            <button
              key={type}
              className="ghost"
              type="button"
              onClick={() => {
                onAdd(type);
                setOpen(false);
              }}
            >
              {BLOCK_LABELS[type]}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function BlockDataEditor({
  block,
  onChange,
}: {
  block: KcBlock;
  onChange: (data: Record<string, unknown>) => void;
}) {
  const data = block.data;
  function set(key: string, value: unknown) {
    onChange({ ...data, [key]: value });
  }
  if (block.type === "mcq") return <McqFields data={data} set={set} />;
  if (block.type === "worked_example") return <WorkedFields data={data} set={set} />;
  return (
    <>
      {fieldsFor(block.type).map((field) => (
        <Field key={field.key} field={field} data={data} set={set} />
      ))}
    </>
  );
}

type TextField = { key: string; label: string; kind: "text" | "lines" | "number" | "enum"; options?: readonly string[] };

function fieldsFor(type: KcBlockType): TextField[] {
  if (type === "topic_goal") {
    return [
      { key: "topic", label: "Topic", kind: "text" },
      { key: "goal", label: "Goal", kind: "text" },
      { key: "acceptance_criteria", label: "Acceptance criteria", kind: "text" },
      { key: "teaching_notes", label: "Teaching notes", kind: "text" },
    ];
  }
  if (type === "case_study") {
    return [
      { key: "case_a", label: "Case A", kind: "text" },
      { key: "case_b", label: "Case B", kind: "text" },
      { key: "prediction_prompt", label: "Prediction prompt", kind: "text" },
      { key: "invariant_principle", label: "Invariant principle", kind: "text" },
      { key: "transfer_prompt", label: "Transfer prompt", kind: "text" },
      { key: "transfer_expected", label: "Transfer expected", kind: "text" },
    ];
  }
  if (type === "socratic") {
    return [
      { key: "central_dilemma", label: "Central dilemma", kind: "text" },
      { key: "initial_probe", label: "Opening probe", kind: "text" },
      { key: "counterexamples", label: "Counterexamples, one per line", kind: "lines" },
      { key: "target_synthesis", label: "Target synthesis", kind: "text" },
    ];
  }
  if (type === "curiosity") {
    return [
      { key: "phenomenon_hook", label: "Phenomenon hook", kind: "text" },
      { key: "prediction_question", label: "Prediction question", kind: "text" },
      { key: "bridge_to_unit", label: "Bridge to unit", kind: "text" },
      { key: "wonder_branches", label: "Wonder branches, one per line", kind: "lines" },
    ];
  }
  if (type === "spot_the_flaw") {
    return [
      { key: "rookie_work", label: "Rookie work", kind: "text" },
      { key: "flaw_description", label: "Flaw description", kind: "text" },
      { key: "underlying_misconception", label: "Underlying misconception", kind: "text" },
      { key: "corrected_version", label: "Corrected version", kind: "text" },
    ];
  }
  if (type === "teach_back") {
    return [
      { key: "peer_persona_prompt", label: "Peer prompt", kind: "text" },
      { key: "required_concepts", label: "Required concepts, one per line", kind: "lines" },
      { key: "peer_follow_up_question", label: "Peer follow-up", kind: "text" },
    ];
  }
  return [
    { key: "recall_prompt", label: "Recall prompt", kind: "text" },
    { key: "expected_fact", label: "Expected fact", kind: "text" },
    { key: "elaborative_why_prompt", label: "Elaborative why prompt", kind: "text" },
    { key: "expected_why_rationale", label: "Expected why rationale", kind: "text" },
  ];
}

function Field({
  field,
  data,
  set,
}: {
  field: TextField;
  data: Record<string, unknown>;
  set: (key: string, value: unknown) => void;
}) {
  if (field.kind === "number") {
    return (
      <label>
        {field.label}
        <input
          aria-label={field.label}
          inputMode="numeric"
          value={String(data[field.key] ?? 0)}
          onChange={(event) => set(field.key, Number(event.target.value || 0))}
        />
      </label>
    );
  }
  if (field.kind === "enum" && field.options) {
    const current = typeof data[field.key] === "string" ? String(data[field.key]) : field.options[0];
    return (
      <label>
        {field.label}
        <select aria-label={field.label} value={current} onChange={(event) => set(field.key, event.target.value)}>
          {field.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    );
  }
  if (field.kind === "lines") {
    const lines = Array.isArray(data[field.key]) ? (data[field.key] as string[]) : [];
    return (
      <label>
        {field.label}
        <textarea
          aria-label={field.label}
          rows={3}
          value={lines.join("\n")}
          onChange={(event) => set(field.key, event.target.value.split("\n"))}
        />
      </label>
    );
  }
  return (
    <label>
      {field.label}
      <textarea
        aria-label={field.label}
        rows={2}
        value={typeof data[field.key] === "string" ? String(data[field.key]) : ""}
        onChange={(event) => set(field.key, event.target.value)}
      />
    </label>
  );
}

function asChoices(value: unknown): McqChoice[] {
  if (!Array.isArray(value) || value.length === 0) return [blankChoice(0, true), blankChoice(1)];
  return value.map((item, index) => {
    const choice = item && typeof item === "object" ? (item as Partial<McqChoice>) : {};
    return {
      id: typeof choice.id === "string" && choice.id ? choice.id : blankChoice(index).id,
      text: typeof choice.text === "string" ? choice.text : "",
      is_correct: choice.is_correct === true,
      distractor_rationale: typeof choice.distractor_rationale === "string" ? choice.distractor_rationale : "",
      misconception_code: typeof choice.misconception_code === "string" ? choice.misconception_code : "",
    };
  });
}

function McqFields({ data, set }: { data: Record<string, unknown>; set: (key: string, value: unknown) => void }) {
  const correctGroup = useId();
  const mode = data.mode === "dynamic" ? "dynamic" : "static";
  const choices = asChoices(data.choices);
  return (
    <>
      <label>
        Mode
        <select aria-label="MCQ mode" value={mode} onChange={(event) => set("mode", event.target.value)}>
          <option value="static">Static</option>
          <option value="dynamic">Dynamic</option>
        </select>
      </label>
      {mode === "static" ? (
        <>
          <Field field={{ key: "question_stem", label: "Question stem", kind: "text" }} data={data} set={set} />
          {choices.map((choice, index) => (
            <div className="kc-pair" key={choice.id}>
              <input
                aria-label={`Choice ${choice.id} text`}
                value={choice.text}
                placeholder={`Choice ${choice.id}`}
                onChange={(event) => {
                  const next = choices.slice();
                  next[index] = { ...choice, text: event.target.value };
                  set("choices", next);
                }}
              />
              <label className="kc-check">
                <input
                  type="radio"
                  name={correctGroup}
                  aria-label={`Choice ${choice.id} is correct`}
                  checked={choice.is_correct}
                  onChange={() => set("choices", choices.map((item, itemIndex) => ({ ...item, is_correct: itemIndex === index })))}
                />
                Correct
              </label>
              <textarea
                aria-label={`Choice ${choice.id} distractor rationale`}
                rows={2}
                value={choice.distractor_rationale}
                placeholder="Distractor rationale"
                onChange={(event) => {
                  const next = choices.slice();
                  next[index] = { ...choice, distractor_rationale: event.target.value };
                  set("choices", next);
                }}
              />
              <input
                aria-label={`Choice ${choice.id} misconception code`}
                value={choice.misconception_code}
                placeholder="Misconception code"
                onChange={(event) => {
                  const next = choices.slice();
                  next[index] = { ...choice, misconception_code: event.target.value };
                  set("choices", next);
                }}
              />
            </div>
          ))}
          {choices.length < 5 ? (
            <button className="ghost" type="button" onClick={() => set("choices", [...choices, blankChoice(choices.length)])}>
              Add choice
            </button>
          ) : null}
          <Field field={{ key: "correct_explanation", label: "Correct explanation", kind: "text" }} data={data} set={set} />
        </>
      ) : (
        <>
          <Field field={{ key: "target_skill", label: "Target skill", kind: "text" }} data={data} set={set} />
          <Field field={{ key: "distractor_guidance", label: "Distractor guidance", kind: "text" }} data={data} set={set} />
          <Field
            field={{ key: "difficulty", label: "Difficulty", kind: "enum", options: ["foundation", "standard", "stretch"] }}
            data={data}
            set={set}
          />
          <Field field={{ key: "num_choices", label: "Number of choices", kind: "number" }} data={data} set={set} />
          <Field field={{ key: "stem_constraints", label: "Stem constraints", kind: "text" }} data={data} set={set} />
        </>
      )}
    </>
  );
}

function asSteps(value: unknown): WorkedStep[] {
  if (!Array.isArray(value) || value.length === 0) {
    return [
      { step_text: "", rationale: "" },
      { step_text: "", rationale: "" },
    ];
  }
  return value.map((item) => {
    const step = item && typeof item === "object" ? (item as Partial<WorkedStep>) : {};
    return {
      step_text: typeof step.step_text === "string" ? step.step_text : "",
      rationale: typeof step.rationale === "string" ? step.rationale : "",
    };
  });
}

function WorkedFields({ data, set }: { data: Record<string, unknown>; set: (key: string, value: unknown) => void }) {
  const steps = asSteps(data.steps);
  const faded = typeof data.faded_step_index === "number" ? data.faded_step_index : Math.max(steps.length - 1, 0);
  return (
    <>
      <Field field={{ key: "problem_statement", label: "Problem statement", kind: "text" }} data={data} set={set} />
      {steps.map((step, index) => (
        <div className="kc-pair" key={index}>
          <input
            aria-label={`Step ${index + 1} text`}
            value={step.step_text}
            placeholder="Step text"
            onChange={(event) => {
              const next = steps.slice();
              next[index] = { ...step, step_text: event.target.value };
              set("steps", next);
            }}
          />
          <input
            aria-label={`Step ${index + 1} rationale`}
            value={step.rationale}
            placeholder="Rationale"
            onChange={(event) => {
              const next = steps.slice();
              next[index] = { ...step, rationale: event.target.value };
              set("steps", next);
            }}
          />
        </div>
      ))}
      {steps.length < 6 ? (
        <button
          className="ghost"
          type="button"
          onClick={() => set("steps", [...steps, { step_text: "", rationale: "" }])}
        >
          Add step
        </button>
      ) : null}
      <label>
        Faded step, starting at 0
        <input
          aria-label="Faded step, starting at 0"
          inputMode="numeric"
          value={String(faded)}
          onChange={(event) => set("faded_step_index", Number(event.target.value || 0))}
        />
      </label>
      <Field field={{ key: "solo_problem", label: "Solo problem", kind: "text" }} data={data} set={set} />
      <Field field={{ key: "solo_expected_answer", label: "Solo expected answer", kind: "text" }} data={data} set={set} />
    </>
  );
}
