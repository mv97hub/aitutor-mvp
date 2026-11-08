"use client";

import { useEffect, useRef, useState, useTransition } from "react";

import { saveKcBlockScope } from "@/lib/kc-actions";
import {
  BLOCK_LABELS,
  BLOCK_TYPES,
  blankBlock,
  blankData,
  newBlockId,
  scopeFromCourse,
  toggleScope,
} from "@/lib/kc-blocks";
import type { KcBlock, KcBlockType } from "@/lib/kc";

type Step = { action: string; reason: string };

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
                  <BlockFields
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

function BlockFields({ block, onChange }: { block: KcBlock; onChange: (data: Record<string, unknown>) => void }) {
  const data = block.data;
  function set(key: string, value: unknown) {
    onChange({ ...data, [key]: value });
  }
  if (block.type === "mcq") return <McqFields data={data} set={set} />;
  if (block.type === "worked_example") return <WorkedFields data={data} set={set} />;
  if (block.type === "case_study") return <CaseFields data={data} set={set} />;
  return (
    <>
      {fieldsFor(block.type).map((field) => (
        <Field key={field.key} field={field} data={data} set={set} />
      ))}
    </>
  );
}

type TextField = { key: string; label: string; kind: "text" | "lines" | "number" | "check" };

function fieldsFor(type: KcBlockType): TextField[] {
  if (type === "topic_goal") {
    return [
      { key: "topic", label: "Topic", kind: "text" },
      { key: "goal", label: "Goal", kind: "text" },
      { key: "reveal_after_recall", label: "Reveal after recall", kind: "check" },
      { key: "contrast_note", label: "Contrast note", kind: "text" },
      { key: "common_mixup", label: "Common mix-up", kind: "text" },
      { key: "why_it_matters", label: "Why it matters", kind: "text" },
    ];
  }
  if (type === "socratic") {
    return [
      { key: "opening_question", label: "Opening question", kind: "text" },
      { key: "probe_if_shallow", label: "Probe if shallow", kind: "text" },
      { key: "probe_if_close", label: "Probe if close", kind: "text" },
      { key: "target_insight", label: "Target insight", kind: "text" },
      { key: "max_exchanges", label: "Max exchanges", kind: "number" },
    ];
  }
  if (type === "curiosity") {
    return [
      { key: "hook_question", label: "Hook question", kind: "text" },
      { key: "expected_hunch", label: "Expected hunch", kind: "text" },
      { key: "reveal", label: "Reveal", kind: "text" },
      { key: "why_surprising", label: "Why it is surprising", kind: "text" },
      { key: "bridge_to_goal", label: "Bridge to the goal", kind: "text" },
    ];
  }
  if (type === "spot_the_flaw") {
    return [
      { key: "artifact", label: "Artifact", kind: "text" },
      { key: "flaw_location", label: "Flaw location", kind: "text" },
      { key: "why_its_wrong", label: "Why it is wrong", kind: "text" },
      { key: "fix", label: "Fix", kind: "text" },
      { key: "transfer_question", label: "Transfer question", kind: "text" },
    ];
  }
  if (type === "teach_back") {
    return [
      { key: "prompt", label: "Prompt", kind: "text" },
      { key: "must_include", label: "Must include, one per line", kind: "lines" },
      { key: "rubric_note", label: "Rubric note", kind: "text" },
      { key: "follow_up_if_thin", label: "Follow up if thin", kind: "text" },
    ];
  }
  return [
    { key: "prompt", label: "Prompt", kind: "text" },
    { key: "acceptable_points", label: "Acceptable points, one per line", kind: "lines" },
    { key: "partial_credit_note", label: "Partial credit note", kind: "text" },
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
  if (field.kind === "check") {
    return (
      <label className="kc-check">
        <input
          type="checkbox"
          aria-label={field.label}
          checked={data[field.key] !== false}
          onChange={(event) => set(field.key, event.target.checked)}
        />
        {field.label}
      </label>
    );
  }
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

function McqFields({ data, set }: { data: Record<string, unknown>; set: (key: string, value: unknown) => void }) {
  const mode = data.mode === "dynamic" ? "dynamic" : "static";
  const options = four(data.options);
  const whyWrong = four(data.why_wrong);
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
          <Field field={{ key: "question", label: "Question", kind: "text" }} data={data} set={set} />
          {options.map((option, index) => (
            <label key={index}>
              {`Option ${index + 1}`}
              <input
                aria-label={`Option ${index + 1}`}
                value={option}
                onChange={(event) => {
                  const next = options.slice();
                  next[index] = event.target.value;
                  set("options", next);
                }}
              />
            </label>
          ))}
          <label>
            Correct option
            <select
              aria-label="Correct option"
              value={String(data.correct_index ?? 0)}
              onChange={(event) => set("correct_index", Number(event.target.value))}
            >
              {options.map((_, index) => (
                <option key={index} value={index}>
                  {index + 1}
                </option>
              ))}
            </select>
          </label>
          <Field field={{ key: "why_correct", label: "Why it is correct", kind: "text" }} data={data} set={set} />
          {whyWrong.map((reason, index) => (
            <label key={index}>
              {`Why option ${index + 1} is wrong`}
              <textarea
                aria-label={`Why option ${index + 1} is wrong`}
                rows={2}
                value={reason}
                onChange={(event) => {
                  const next = whyWrong.slice();
                  next[index] = event.target.value;
                  set("why_wrong", next);
                }}
              />
            </label>
          ))}
        </>
      ) : (
        <>
          <Field field={{ key: "generation_prompt", label: "Generation prompt", kind: "text" }} data={data} set={set} />
          <Field field={{ key: "why_correct_guidance", label: "Why-correct guidance", kind: "text" }} data={data} set={set} />
          <Field field={{ key: "why_wrong_guidance", label: "Why-wrong guidance", kind: "text" }} data={data} set={set} />
        </>
      )}
    </>
  );
}

function CaseFields({ data, set }: { data: Record<string, unknown>; set: (key: string, value: unknown) => void }) {
  const options = Array.isArray(data.decision_options) ? (data.decision_options as string[]) : ["", ""];
  return (
    <>
      <Field field={{ key: "scenario", label: "Scenario", kind: "text" }} data={data} set={set} />
      <Field field={{ key: "decision_point", label: "Decision point", kind: "text" }} data={data} set={set} />
      {options.map((option, index) => (
        <label key={index}>
          {`Decision option ${index + 1}`}
          <input
            aria-label={`Decision option ${index + 1}`}
            value={option}
            onChange={(event) => {
              const next = options.slice();
              next[index] = event.target.value;
              set("decision_options", next);
            }}
          />
        </label>
      ))}
      <button className="ghost" type="button" onClick={() => set("decision_options", [...options, ""])}>
        Add decision option
      </button>
      <label>
        Best option
        <select
          aria-label="Best option"
          value={String(data.best_option_index ?? 0)}
          onChange={(event) => set("best_option_index", Number(event.target.value))}
        >
          {options.map((_, index) => (
            <option key={index} value={index}>
              {index + 1}
            </option>
          ))}
        </select>
      </label>
      <Field field={{ key: "why_best", label: "Why it is best", kind: "text" }} data={data} set={set} />
      <Field field={{ key: "why_others", label: "Why the others fall short", kind: "text" }} data={data} set={set} />
      <Field field={{ key: "follow_up_question", label: "Follow-up question", kind: "text" }} data={data} set={set} />
      <Field field={{ key: "what_transfers", label: "What transfers", kind: "text" }} data={data} set={set} />
    </>
  );
}

function WorkedFields({ data, set }: { data: Record<string, unknown>; set: (key: string, value: unknown) => void }) {
  const steps = Array.isArray(data.steps) ? (data.steps as Step[]) : [{ action: "", reason: "" }];
  return (
    <>
      <Field field={{ key: "problem", label: "Problem", kind: "text" }} data={data} set={set} />
      {steps.map((step, index) => (
        <div className="kc-pair" key={index}>
          <input
            aria-label={`Step ${index + 1} action`}
            value={step.action}
            placeholder="Action"
            onChange={(event) => {
              const next = steps.slice();
              next[index] = { ...step, action: event.target.value };
              set("steps", next);
            }}
          />
          <input
            aria-label={`Step ${index + 1} reason`}
            value={step.reason}
            placeholder="Reason"
            onChange={(event) => {
              const next = steps.slice();
              next[index] = { ...step, reason: event.target.value };
              set("steps", next);
            }}
          />
        </div>
      ))}
      <button className="ghost" type="button" onClick={() => set("steps", [...steps, { action: "", reason: "" }])}>
        Add step
      </button>
      <Field field={{ key: "faded_step_index", label: "Faded step, starting at 0", kind: "number" }} data={data} set={set} />
      <Field field={{ key: "solo_problem", label: "Solo problem", kind: "text" }} data={data} set={set} />
      <Field field={{ key: "solo_check", label: "Solo check", kind: "text" }} data={data} set={set} />
    </>
  );
}

function four(value: unknown): string[] {
  const items = Array.isArray(value) ? value.map((item) => String(item ?? "")) : [];
  return [0, 1, 2, 3].map((index) => items[index] ?? "");
}
