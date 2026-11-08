"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { useRouter } from "next/navigation";

import { KcBanner } from "@/components/KcBanner";
import { KcCreatorComposer } from "@/components/KcComposer";
import { markKcComplete, pushKcComponent, saveKcComponent } from "@/lib/kc-actions";
import {
  TYPE_LABELS,
  type KcComponent,
  type KcCourse,
  type KcCreatorThread,
  type KcMisconception,
  type KcType,
} from "@/lib/kc";
import {
  CREATE_DRAFT_MESSAGE,
  beginFastCreate,
  creatorHref,
  emptyComponentIds,
  gapLabel,
  readFastCreate,
  stepFastCreate,
  writeFastCreate,
  type FastAction,
  type FastRecord,
} from "@/lib/kc-fast-create";
import { kcModel } from "@/lib/kc-models";

const acted = new Set<string>();

function actionKey(record: FastRecord, action: FastAction): string {
  const id = record.ids[record.index] ?? "";
  if (action.type === "open") return `${record.token}:open:${action.componentId}:${record.done}`;
  if (action.type === "draft") return `${record.token}:draft:${id}:${record.baseline}`;
  if (action.type === "push") return `${record.token}:push:${id}:${record.done}`;
  if (action.type === "complete") return `${record.token}:complete:${id}:${record.done}`;
  return `${record.token}:none`;
}

export function KcCreator({
  courses,
  course,
  component,
  thread,
  model,
  error,
}: {
  courses: KcCourse[];
  course: KcCourse | null;
  component: KcComponent | null;
  thread: KcCreatorThread | null;
  model: string;
  error: string | null;
}) {
  const router = useRouter();
  const rows = course ? [...course.components, ...course.patches] : [];
  const [record, setRecord] = useState<FastRecord | null>(null);
  const [ready, setReady] = useState(false);
  const draftFormRef = useRef<HTMLFormElement>(null);
  const pushFormRef = useRef<HTMLFormElement>(null);
  const completeRef = useRef<HTMLButtonElement>(null);
  const booted = useRef(false);
  const lock = useRef(false);
  const gap =
    record?.gapId && component?.id === record.gapId && component.missing.length > 0
      ? gapLabel(component.missing)
      : null;
  const notice = error || gap;

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    setRecord(readFastCreate());
    setReady(true);
  }, []);

  useEffect(() => {
    if (record && !record.active) lock.current = false;
  }, [record]);

  useEffect(() => {
    if (!ready || !record?.active) return;
    const next = stepFastCreate(record, {
      courseId: course?.id ?? null,
      componentId: component?.id ?? null,
      messageCount: thread?.messages.length ?? 0,
      hasDraft: Boolean(thread?.draft),
      missing: component?.missing ?? [],
      markedComplete: Boolean(component?.marked_complete),
      error,
    });
    if (!runFastAction(next.action, next.record)) return;
    if (next.record !== record) {
      writeFastCreate(next.record);
      setRecord(next.record);
    }

    function runFastAction(action: FastAction, committed: FastRecord): boolean {
      if (action.type === "none") return true;
      const key = actionKey(committed, action);
      if (acted.has(key)) return true;
      try {
        if (action.type === "open") {
          const href = creatorHref(action.courseId, action.componentId, action.model);
          const here = `${window.location.pathname}${window.location.search}`;
          if (here === href && error) {
            const stopped = { ...committed, active: false };
            writeFastCreate(stopped);
            setRecord(stopped);
            return true;
          }
          acted.add(key);
          router.push(href);
          return true;
        }
        if (action.type === "draft") {
          const form = draftFormRef.current;
          const field = form?.querySelector("textarea[name=message]");
          if (!form || !(field instanceof HTMLTextAreaElement) || field.disabled) return false;
          field.value = CREATE_DRAFT_MESSAGE;
          const select = form.querySelector("select[name=model]");
          if (select instanceof HTMLSelectElement) select.value = action.model;
          acted.add(key);
          form.requestSubmit();
          return true;
        }
        if (action.type === "push") {
          const form = pushFormRef.current;
          if (!form) return false;
          acted.add(key);
          form.requestSubmit();
          return true;
        }
        const button = completeRef.current;
        const form = button?.form;
        if (!button || !form || button.disabled) return false;
        acted.add(key);
        form.requestSubmit(button);
        return true;
      } catch {
        acted.delete(key);
        return false;
      }
    }
  }, [ready, record, course, component, thread, error, router]);

  function chosenModel() {
    const select = document.querySelector(".kc-creator-stage select[name=model]");
    if (select instanceof HTMLSelectElement && select.value) return kcModel(select.value);
    return model;
  }

  function startFastCreate() {
    if (!course || record?.active || lock.current) return;
    lock.current = true;
    booted.current = true;
    const next = beginFastCreate(course.id, emptyComponentIds(course.components), chosenModel());
    if (!next.active) lock.current = false;
    writeFastCreate(next);
    setRecord(next);
    setReady(true);
  }

  function openCourse(id: string) {
    const next = courses.find((item) => item.id === id);
    const first = next?.components[0] ?? next?.patches[0];
    const params = new URLSearchParams();
    params.set("course", id);
    if (first) params.set("kc", first.id);
    if (model) params.set("model", model);
    router.push(`/kc-creator?${params.toString()}`);
  }

  return (
    <main className="ds-shell studio-shell kc-screen">
      <KcBanner name="KC Creator">
        <div className="kc-fast">
          {record ? (
            <span className="kc-fast-count" aria-live="polite">
              {record.done} / {record.ids.length}
            </span>
          ) : null}
          <button className="button" type="button" onClick={startFastCreate} disabled={!course || Boolean(record?.active)}>
            Fast Create All
          </button>
        </div>
      </KcBanner>
      <aside className="ds-side">
        {courses.length === 0 ? (
          <p className="ds-quiet">No courses yet</p>
        ) : (
          <label className="kc-course-pick">
            Course
            <select
              aria-label="Course"
              value={course?.id ?? ""}
              onChange={(event) => {
                if (event.target.value) openCourse(event.target.value);
              }}
            >
              {course ? null : <option value="">Choose a course</option>}
              {courses.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
        )}
        {course ? (
          <ul className="kc-component-list" aria-label="Components">
            {rows.length === 0 ? <li className="ds-quiet">No components yet</li> : null}
            {course.components.map((item) => (
              <li key={item.id}>
                <a
                  className={`ds-row${component?.id === item.id ? " is-on" : ""}`}
                  href={`/kc-creator?course=${course.id}&kc=${item.id}&model=${encodeURIComponent(model)}`}
                >
                  <strong>{item.title}</strong>
                  <small>{TYPE_LABELS[item.kc_type ?? "unset"]}</small>
                </a>
              </li>
            ))}
            {course.patches.map((item) => (
              <li key={item.id}>
                <a
                  className={`ds-row${component?.id === item.id ? " is-on" : ""}`}
                  href={`/kc-creator?course=${course.id}&kc=${item.id}&model=${encodeURIComponent(model)}`}
                >
                  <strong>{item.title}</strong>
                  <small>Not a target</small>
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="ds-quiet">Choose a course, then a component.</p>
        )}
      </aside>
      <section className="studio-stage kc-creator-stage">
        {notice ? (
          <div className="banner" role="alert">
            <p>{notice}</p>
          </div>
        ) : null}
        <div className="studio-columns">
          <div className="studio-tree">
            {!course || !component ? <p className="ds-quiet">Choose a component to edit it.</p> : null}
            {course && component ? (
              <ComponentEditor
                key={component.id}
                course={course}
                component={component}
                model={model}
                completeRef={completeRef}
              />
            ) : null}
          </div>
          <div className="studio-chat">
            <CreatorChat
              course={course}
              component={component}
              thread={thread}
              model={model}
              draftFormRef={draftFormRef}
              pushFormRef={pushFormRef}
            />
          </div>
        </div>
      </section>
    </main>
  );
}

function CreatorChat({
  course,
  component,
  thread,
  model,
  draftFormRef,
  pushFormRef,
}: {
  course: KcCourse | null;
  component: KcComponent | null;
  thread: KcCreatorThread | null;
  model: string;
  draftFormRef: RefObject<HTMLFormElement | null>;
  pushFormRef: RefObject<HTMLFormElement | null>;
}) {
  if (!course || !component || !thread) {
    return <p className="ds-quiet">Open a component before asking for a draft.</p>;
  }
  const draft = thread.draft;
  return (
    <>
      <div className="ds-scroll">
        <div className="ds-column">
          {component.description ? (
            <div className="bubble assistant">
              <p className="kc-reply">{component.description}</p>
            </div>
          ) : null}
          <div className="bubble assistant">
            <p className="kc-reply">{thread.mirror}</p>
          </div>
          {thread.messages.map((message) => (
            <div key={message.id} className={`bubble ${message.role === "user" ? "user" : "assistant"}`}>
              <p className="kc-reply">{message.content}</p>
            </div>
          ))}
        </div>
      </div>
      {draft ? (
        <form action={pushKcComponent} ref={pushFormRef}>
          <input type="hidden" name="course_id" value={course.id} />
          <input type="hidden" name="node_id" value={component.id} />
          <input type="hidden" name="model" value={model} />
          <input
            type="hidden"
            name="payload"
            value={JSON.stringify({
              description: draft.description ?? component.description,
              outline: draft.outline ?? component.outline,
              topics: draft.topics ?? component.topics,
              title: draft.title,
              kc_type: draft.kc_type,
              core_truth: draft.core_truth,
              rubric: draft.rubric,
              misconceptions: draft.misconceptions,
              prerequisite_codes: draft.prerequisite_codes,
              encompasses_codes: draft.encompasses_codes,
              type_fields: draft.type_fields,
            })}
          />
          <button className="button studio-push" type="submit">
            Push draft
          </button>
        </form>
      ) : null}
      <KcCreatorComposer courseId={course.id} nodeId={component.id} model={model} formRef={draftFormRef} />
    </>
  );
}

const TIPS = {
  description: "A short summary of this component. The walk does not read it.",
  outline: "The outline Orient elaborates. It is not a topic.",
  topic: "One topic the walk discusses, with the goal that belongs to it.",
  goal: "The goal that belongs to this topic. The topic turn looks for it.",
  title: "The name the kid sees on the card and during the lesson.",
  type: "The recipe the tutor runs: recall a fact, work an example, compare two cases, judge a decision, or correct a rookie plan.",
  fact: "The fact the tutor accepts, and the line it says when the kid passes.",
  retrieval_question: "The question the tutor asks first on a factual component.",
  steps: "The worked example the tutor reads, one step per line. It then hides one step.",
  blanked_step: "Which step the tutor hides and asks the kid to fill. The first step is 0.",
  solo_problem: "The problem the tutor asks the kid to solve alone.",
  solo_check: "The answer the tutor accepts for that solo problem.",
  case_a: "The first case the tutor shows. The kid picks between the two cases.",
  case_b: "The second case the tutor shows, set against the first.",
  prediction: "The question the tutor asks when the kid picks a case.",
  rule: "The rule the tutor asks the kid to state, and the answer it accepts.",
  transfer_case:
    "A third case the child uses after stating the rule. Conceptual components only. Leave it empty to skip that move. The model does not invent one.",
  counterfactual:
    "The what-if the child answers after defending the chain. Causal components only, and only when self-explanation is on. Leave it empty to skip that move.",
  decision_point: "The situation the tutor opens with, then asks what is at stake.",
  flawed_claim: "The claim the tutor asks the kid to mark as flawed or as holding.",
  causal_chain: "The explanation the tutor accepts when the kid defends the chain.",
  mix_a: "The first earlier component the rookie mixes.",
  mix_b: "The second earlier component the rookie mixes.",
  faulty_plan: "What the rookie says. The tutor asks the kid to correct that plan.",
  core_truth: "The idea the tutor says back after a miss, and the line several steps accept.",
  rubric: "A check the tutor is told a good answer has to meet.",
  wrong_move: "If the kid's answer matches this, the tutor names the mistake once and opens the broken component.",
  broken_kc: "The component the tutor opens after that wrong move.",
  prerequisite: "A component the kid should already know. The tutor offers this one once those are known.",
  encompasses: "When the kid passes this component, the tutor gives that component a stability bump.",
} as const;

function ComponentEditor({
  course,
  component,
  model,
  completeRef,
}: {
  course: KcCourse;
  component: KcComponent;
  model: string;
  completeRef: RefObject<HTMLButtonElement | null>;
}) {
  const codes = [...course.components, ...course.patches]
    .map((item) => item.code)
    .filter((code) => code !== component.code);
  // Push updates this same component. Follow the saved type unless the author
  // picked a different type after that save.
  const savedType = (component.kc_type ?? "factual") as KcType;
  const [choice, setChoice] = useState<{ id: string; saved: KcType; type: KcType } | null>(null);
  const kcType = choice && choice.id === component.id && choice.saved === savedType ? choice.type : savedType;
  const rubric = [...component.rubric, "", "", ""].slice(0, 3);
  const initialMixes = Array.isArray(component.type_fields.mixes) ? (component.type_fields.mixes as string[]) : [];
  const fields: Record<string, unknown> = {
    ...component.type_fields,
    steps: Array.isArray(component.type_fields.steps)
      ? (component.type_fields.steps as string[]).join("\n")
      : (component.type_fields.steps ?? ""),
    mix_a: initialMixes[0] ?? "",
    mix_b: initialMixes[1] ?? "",
  };
  const misconceptions: KcMisconception[] =
    component.misconceptions.length > 0 ? component.misconceptions : [{ wrong_move: "", broken_kc: "" }];
  const canComplete = component.missing.length === 0 && !component.marked_complete;

  return (
    <>
      <form className="kc-editor" action={saveKcComponent}>
      <input type="hidden" name="course_id" value={course.id} />
      <input type="hidden" name="node_id" value={component.id} />
      <input type="hidden" name="model" value={model} />
      <h2>Component</h2>
      <label title={TIPS.description}>
        Description
        <textarea
          aria-label="Component description"
          name="description"
          title={TIPS.description}
          defaultValue={component.description}
          placeholder="A short summary"
          rows={3}
        />
      </label>
      <label title={TIPS.title}>
        Title
        <input aria-label="Component title" name="title" title={TIPS.title} defaultValue={component.title} required />
      </label>
      <label title={TIPS.outline}>
        Outline
        <textarea
          aria-label="Outline"
          name="outline"
          title={TIPS.outline}
          defaultValue={component.outline ?? ""}
          placeholder="The outline Orient elaborates"
          rows={3}
        />
      </label>
      <TopicRows initial={component.topics ?? []} />
      <label title={TIPS.type}>
        Type
        <select
          aria-label="Component type"
          name="kc_type"
          title={TIPS.type}
          value={kcType}
          onChange={(event) =>
            setChoice({ id: component.id, saved: savedType, type: event.target.value as KcType })
          }
        >
          {(Object.keys(TYPE_LABELS).filter((key) => key !== "unset") as KcType[]).map((type) => (
            <option key={type} value={type}>
              {TYPE_LABELS[type]}
            </option>
          ))}
        </select>
      </label>
      <TypeFields key={kcType} kcType={kcType} fields={fields} codes={codes} />
      <label title={TIPS.core_truth}>
        Core truth
        <textarea
          aria-label="Core truth"
          name="core_truth"
          title={TIPS.core_truth}
          defaultValue={component.core_truth}
          rows={2}
        />
      </label>
      <fieldset>
        <legend>Rubric checks, one to three</legend>
        {rubric.map((check, index) => (
          <input
            key={index}
            aria-label={`Rubric check ${index + 1}`}
            name="rubric"
            title={TIPS.rubric}
            defaultValue={check}
          />
        ))}
      </fieldset>
      <fieldset>
        <legend>Misconceptions</legend>
        {misconceptions.map((item, index) => (
          <div className="kc-pair" key={index}>
            <input
              aria-label={`Wrong move ${index + 1}`}
              name="wrong_move"
              title={TIPS.wrong_move}
              defaultValue={item.wrong_move}
              placeholder="Wrong move"
            />
            <input
              aria-label={`Broken component ${index + 1}`}
              name="broken_kc"
              title={TIPS.broken_kc}
              defaultValue={item.broken_kc}
              placeholder="Component code"
              list="kc-codes"
            />
          </div>
        ))}
      </fieldset>
      <fieldset>
        <legend>Prerequisite of this component</legend>
        {codes.map((code) => (
          <label key={`pre-${code}`} className="kc-check" title={TIPS.prerequisite}>
            <input
              type="checkbox"
              name="prerequisite_codes"
              value={code}
              title={TIPS.prerequisite}
              defaultChecked={component.prerequisite_codes.includes(code)}
            />
            {code}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Encompasses, stability bump</legend>
        {codes.map((code) => (
          <label key={`enc-${code}`} className="kc-check" title={TIPS.encompasses}>
            <input
              type="checkbox"
              name="encompasses_codes"
              value={code}
              title={TIPS.encompasses}
              defaultChecked={component.encompasses_codes.includes(code)}
            />
            {code}
          </label>
        ))}
      </fieldset>
      <datalist id="kc-codes">
        {codes.map((code) => (
          <option key={code} value={code} />
        ))}
      </datalist>
      <div className="kc-editor-actions">
        <button className="button" type="submit">
          Save this component
        </button>
        <button
          className="button"
          type="submit"
          formAction={markKcComplete}
          formNoValidate
          ref={completeRef}
          disabled={!canComplete}
        >
          {component.marked_complete ? "Marked complete" : "Mark complete"}
        </button>
      </div>
      </form>
      <HistoryLog label="Component history" text={component.history ?? ""} />
      <HistoryLog label="Course history" text={course.history ?? ""} />
    </>
  );
}

function TopicRows({ initial }: { initial: { topic: string; goal: string }[] }) {
  const [rows, setRows] = useState(initial.length ? initial : [{ topic: "", goal: "" }]);
  return (
    <fieldset>
      <legend>Topics</legend>
      {rows.map((row, index) => (
        <div className="kc-topic-row" key={index}>
          <input
            aria-label={`Topic ${index + 1}`}
            name="topic"
            title={TIPS.topic}
            value={row.topic}
            placeholder="Topic"
            onChange={(event) => {
              const next = rows.slice();
              next[index] = { ...row, topic: event.target.value };
              setRows(next);
            }}
          />
          <input
            aria-label={`Goal ${index + 1}`}
            name="goal"
            title={TIPS.goal}
            value={row.goal}
            placeholder="Goal"
            onChange={(event) => {
              const next = rows.slice();
              next[index] = { ...row, goal: event.target.value };
              setRows(next);
            }}
          />
          <button
            className="ghost"
            type="button"
            aria-label={`Remove topic ${index + 1}`}
            onClick={() => setRows(rows.filter((_, item) => item !== index))}
          >
            Remove
          </button>
        </div>
      ))}
      <button className="ghost kc-topic-add" type="button" onClick={() => setRows([...rows, { topic: "", goal: "" }])}>
        Add topic
      </button>
    </fieldset>
  );
}

function HistoryLog({ label, text }: { label: string; text: string }) {
  return (
    <section className="kc-history">
      <h3>{label}</h3>
      <pre aria-label={label}>{text.trim() ? text : "No history yet."}</pre>
    </section>
  );
}

function textOf(fields: Record<string, unknown>, key: string) {
  return typeof fields[key] === "string" ? String(fields[key]) : "";
}

function TypeFields({
  kcType,
  fields,
  codes,
}: {
  kcType: KcType;
  fields: Record<string, unknown>;
  codes: string[];
}) {
  const mixes = Array.isArray(fields.mixes) ? (fields.mixes as string[]) : [];
  if (kcType === "factual") {
    return (
      <>
        <label title={TIPS.fact}>
          Fact
          <textarea aria-label="Fact" name="fact" title={TIPS.fact} defaultValue={textOf(fields, "fact")} rows={2} />
        </label>
        <label title={TIPS.retrieval_question}>
          Retrieval question
          <textarea
            aria-label="Retrieval question"
            name="retrieval_question"
            title={TIPS.retrieval_question}
            defaultValue={textOf(fields, "retrieval_question")}
            rows={2}
          />
        </label>
      </>
    );
  }
  if (kcType === "procedural") {
    return (
      <>
        <label title={TIPS.steps}>
          Worked steps, one per line
          <textarea aria-label="Worked steps" name="steps" title={TIPS.steps} defaultValue={textOf(fields, "steps")} rows={4} />
        </label>
        <label title={TIPS.blanked_step}>
          Blanked step, starting at 0
          <input
            aria-label="Blanked step"
            name="blanked_step"
            title={TIPS.blanked_step}
            inputMode="numeric"
            defaultValue={String(fields.blanked_step ?? 0)}
          />
        </label>
        <label title={TIPS.solo_problem}>
          Solo problem
          <textarea
            aria-label="Solo problem"
            name="solo_problem"
            title={TIPS.solo_problem}
            defaultValue={textOf(fields, "solo_problem")}
            rows={2}
          />
        </label>
        <label title={TIPS.solo_check}>
          Solo check
          <input aria-label="Solo check" name="solo_check" title={TIPS.solo_check} defaultValue={textOf(fields, "solo_check")} />
        </label>
      </>
    );
  }
  if (kcType === "conceptual") {
    return (
      <>
        <label title={TIPS.case_a}>
          Case one
          <textarea aria-label="Case one" name="case_a" title={TIPS.case_a} defaultValue={textOf(fields, "case_a")} rows={2} />
        </label>
        <label title={TIPS.case_b}>
          Case two
          <textarea aria-label="Case two" name="case_b" title={TIPS.case_b} defaultValue={textOf(fields, "case_b")} rows={2} />
        </label>
        <label title={TIPS.prediction}>
          Prediction
          <textarea
            aria-label="Prediction"
            name="prediction"
            title={TIPS.prediction}
            defaultValue={textOf(fields, "prediction")}
            rows={2}
          />
        </label>
        <label title={TIPS.rule}>
          Rule
          <textarea aria-label="Rule" name="rule" title={TIPS.rule} defaultValue={textOf(fields, "rule")} rows={2} />
        </label>
        <label title={TIPS.transfer_case}>
          Transfer case
          <textarea
            aria-label="Transfer case"
            name="transfer_case"
            title={TIPS.transfer_case}
            defaultValue={textOf(fields, "transfer_case")}
            rows={2}
          />
        </label>
      </>
    );
  }
  if (kcType === "causal") {
    return (
      <>
        <label title={TIPS.decision_point}>
          Decision point
          <textarea
            aria-label="Decision point"
            name="decision_point"
            title={TIPS.decision_point}
            defaultValue={textOf(fields, "decision_point")}
            rows={2}
          />
        </label>
        <label title={TIPS.flawed_claim}>
          Flawed claim
          <textarea
            aria-label="Flawed claim"
            name="flawed_claim"
            title={TIPS.flawed_claim}
            defaultValue={textOf(fields, "flawed_claim")}
            rows={2}
          />
        </label>
        <label title={TIPS.causal_chain}>
          Causal chain
          <textarea
            aria-label="Causal chain"
            name="causal_chain"
            title={TIPS.causal_chain}
            defaultValue={textOf(fields, "causal_chain")}
            rows={2}
          />
        </label>
        <label title={TIPS.counterfactual}>
          Counterfactual
          <textarea
            aria-label="Counterfactual"
            name="counterfactual"
            title={TIPS.counterfactual}
            defaultValue={textOf(fields, "counterfactual")}
            rows={2}
          />
        </label>
      </>
    );
  }
  return (
    <>
      <label title={TIPS.mix_a}>
        First component it mixes
        <select aria-label="First mix" name="mix_a" title={TIPS.mix_a} defaultValue={textOf(fields, "mix_a") || mixes[0] || ""}>
          <option value="">Choose</option>
          {codes.map((code) => (
            <option key={code}>{code}</option>
          ))}
        </select>
      </label>
      <label title={TIPS.mix_b}>
        Second component it mixes
        <select aria-label="Second mix" name="mix_b" title={TIPS.mix_b} defaultValue={textOf(fields, "mix_b") || mixes[1] || ""}>
          <option value="">Choose</option>
          {codes.map((code) => (
            <option key={code}>{code}</option>
          ))}
        </select>
      </label>
      <label title={TIPS.faulty_plan}>
        Rookie’s faulty plan
        <textarea
          aria-label="Faulty plan"
          name="faulty_plan"
          title={TIPS.faulty_plan}
          defaultValue={textOf(fields, "faulty_plan")}
          rows={3}
        />
      </label>
    </>
  );
}
