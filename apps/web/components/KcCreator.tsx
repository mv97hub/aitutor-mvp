"use client";

import { useState } from "react";
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
      <KcBanner name="KC Creator" />
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
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <div className="studio-columns">
          <div className="studio-tree">
            {!course || !component ? <p className="ds-quiet">Choose a component to edit it.</p> : null}
            {course && component ? <ComponentEditor key={component.id} course={course} component={component} /> : null}
          </div>
          <div className="studio-chat">
            <CreatorChat course={course} component={component} thread={thread} model={model} />
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
}: {
  course: KcCourse | null;
  component: KcComponent | null;
  thread: KcCreatorThread | null;
  model: string;
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
        <form action={pushKcComponent}>
          <input type="hidden" name="course_id" value={course.id} />
          <input type="hidden" name="node_id" value={component.id} />
          <input
            type="hidden"
            name="payload"
            value={JSON.stringify({
              description: draft.description ?? component.description,
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
      <KcCreatorComposer courseId={course.id} nodeId={component.id} model={model} />
    </>
  );
}

const TIPS = {
  description:
    "The outline, key topics, and key goals. The chat starts from this brief, and the tutor steps are written from it.",
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

function ComponentEditor({ course, component }: { course: KcCourse; component: KcComponent }) {
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
    <form className="kc-editor" action={saveKcComponent}>
      <input type="hidden" name="course_id" value={course.id} />
      <input type="hidden" name="node_id" value={component.id} />
      <h2>Component</h2>
      <label title={TIPS.description}>
        Description
        <textarea
          aria-label="Component description"
          name="description"
          title={TIPS.description}
          defaultValue={component.description}
          placeholder="Outline, key topics, and key goals"
          rows={4}
        />
      </label>
      <label title={TIPS.title}>
        Title
        <input aria-label="Component title" name="title" title={TIPS.title} defaultValue={component.title} required />
      </label>
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
        <button className="button" type="submit" formAction={markKcComplete} disabled={!canComplete}>
          {component.marked_complete ? "Marked complete" : "Mark complete"}
        </button>
      </div>
    </form>
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
