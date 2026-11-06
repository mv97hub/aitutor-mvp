"use client";

import { useState } from "react";

import { EnterSubmitTextarea } from "@/components/EnterSubmitTextarea";
import { KcBanner } from "@/components/KcBanner";
import { KcCourseList } from "@/components/KcCourseList";
import { markKcComplete, postKcCreatorMessage, pushKcComponent, saveKcComponent } from "@/lib/kc-actions";
import {
  TYPE_LABELS,
  type KcComponent,
  type KcComponentDraft,
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
  error,
}: {
  courses: KcCourse[];
  course: KcCourse | null;
  component: KcComponent | null;
  thread: KcCreatorThread | null;
  error: string | null;
}) {
  const rows = course ? [...course.components, ...course.patches] : [];
  return (
    <main className="ds-shell studio-shell kc-screen">
      <KcBanner name="KC Creator" />
      <aside className="ds-side">
        <KcCourseList
          courses={courses}
          activeId={course?.id ?? null}
          hrefBase="/kc-creator?course="
        />
        {course ? (
          <ul className="kc-component-list" aria-label="Components">
            {rows.length === 0 ? <li className="ds-quiet">No components yet</li> : null}
            {course.components.map((item) => (
              <li key={item.id}>
                <a
                  className={`ds-row${component?.id === item.id ? " is-on" : ""}`}
                  href={`/kc-creator?course=${course.id}&kc=${item.id}`}
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
                  href={`/kc-creator?course=${course.id}&kc=${item.id}`}
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
            <CreatorChat course={course} component={component} thread={thread} />
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
}: {
  course: KcCourse | null;
  component: KcComponent | null;
  thread: KcCreatorThread | null;
}) {
  if (!course || !component || !thread) {
    return <p className="ds-quiet">Open a component before asking for a draft.</p>;
  }
  const draft = thread.draft;
  return (
    <>
      <div className="ds-scroll">
        <div className="ds-column">
          <div className="bubble assistant">
            <p>{thread.mirror}</p>
          </div>
          {thread.messages.map((message) => (
            <div key={message.id} className={`bubble ${message.role === "user" ? "user" : "assistant"}`}>
              <p>{message.content}</p>
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
      <form className="ds-composer-seat" action={postKcCreatorMessage}>
        <input type="hidden" name="course_id" value={course.id} />
        <input type="hidden" name="node_id" value={component.id} />
        <div className="ds-card">
          <EnterSubmitTextarea
            className="ds-draft"
            name="message"
            rows={1}
            required
            placeholder="Ask about this component"
            aria-label="Component chat"
            maxLength={8000}
          />
          <div className="ds-card-row">
            <button className="ds-send" type="submit" aria-label="Send">
              ↑
            </button>
          </div>
        </div>
      </form>
    </>
  );
}

function ComponentEditor({ course, component }: { course: KcCourse; component: KcComponent }) {
  const codes = [...course.components, ...course.patches]
    .map((item) => item.code)
    .filter((code) => code !== component.code);
  const [kcType, setKcType] = useState<KcType>(component.kc_type ?? "factual");
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
      <label>
        Title
        <input aria-label="Component title" name="title" defaultValue={component.title} required />
      </label>
      <label>
        Type
        <select
          aria-label="Component type"
          name="kc_type"
          defaultValue={kcType}
          onChange={(event) => setKcType(event.target.value as KcType)}
        >
          {(Object.keys(TYPE_LABELS).filter((key) => key !== "unset") as KcType[]).map((type) => (
            <option key={type} value={type}>
              {TYPE_LABELS[type]}
            </option>
          ))}
        </select>
      </label>
      <TypeFields key={kcType} kcType={kcType} fields={fields} codes={codes} />
      <label>
        Core truth
        <textarea aria-label="Core truth" name="core_truth" defaultValue={component.core_truth} rows={2} />
      </label>
      <fieldset>
        <legend>Rubric checks, one to three</legend>
        {rubric.map((check, index) => (
          <input key={index} aria-label={`Rubric check ${index + 1}`} name="rubric" defaultValue={check} />
        ))}
      </fieldset>
      <fieldset>
        <legend>Misconceptions</legend>
        {misconceptions.map((item, index) => (
          <div className="kc-pair" key={index}>
            <input
              aria-label={`Wrong move ${index + 1}`}
              name="wrong_move"
              defaultValue={item.wrong_move}
              placeholder="Wrong move"
            />
            <input
              aria-label={`Broken component ${index + 1}`}
              name="broken_kc"
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
          <label key={`pre-${code}`} className="kc-check">
            <input
              type="checkbox"
              name="prerequisite_codes"
              value={code}
              defaultChecked={component.prerequisite_codes.includes(code)}
            />
            {code}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Encompasses, stability bump</legend>
        {codes.map((code) => (
          <label key={`enc-${code}`} className="kc-check">
            <input
              type="checkbox"
              name="encompasses_codes"
              value={code}
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
        <label>
          Fact
          <textarea aria-label="Fact" name="fact" defaultValue={textOf(fields, "fact")} rows={2} />
        </label>
        <label>
          Retrieval question
          <textarea
            aria-label="Retrieval question"
            name="retrieval_question"
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
        <label>
          Worked steps, one per line
          <textarea aria-label="Worked steps" name="steps" defaultValue={textOf(fields, "steps")} rows={4} />
        </label>
        <label>
          Blanked step, starting at 0
          <input
            aria-label="Blanked step"
            name="blanked_step"
            inputMode="numeric"
            defaultValue={String(fields.blanked_step ?? 0)}
          />
        </label>
        <label>
          Solo problem
          <textarea aria-label="Solo problem" name="solo_problem" defaultValue={textOf(fields, "solo_problem")} rows={2} />
        </label>
        <label>
          Solo check
          <input aria-label="Solo check" name="solo_check" defaultValue={textOf(fields, "solo_check")} />
        </label>
      </>
    );
  }
  if (kcType === "conceptual") {
    return (
      <>
        <label>
          Case one
          <textarea aria-label="Case one" name="case_a" defaultValue={textOf(fields, "case_a")} rows={2} />
        </label>
        <label>
          Case two
          <textarea aria-label="Case two" name="case_b" defaultValue={textOf(fields, "case_b")} rows={2} />
        </label>
        <label>
          Prediction
          <textarea aria-label="Prediction" name="prediction" defaultValue={textOf(fields, "prediction")} rows={2} />
        </label>
        <label>
          Rule
          <textarea aria-label="Rule" name="rule" defaultValue={textOf(fields, "rule")} rows={2} />
        </label>
      </>
    );
  }
  if (kcType === "causal") {
    return (
      <>
        <label>
          Decision point
          <textarea
            aria-label="Decision point"
            name="decision_point"
            defaultValue={textOf(fields, "decision_point")}
            rows={2}
          />
        </label>
        <label>
          Flawed claim
          <textarea aria-label="Flawed claim" name="flawed_claim" defaultValue={textOf(fields, "flawed_claim")} rows={2} />
        </label>
        <label>
          Causal chain
          <textarea aria-label="Causal chain" name="causal_chain" defaultValue={textOf(fields, "causal_chain")} rows={2} />
        </label>
      </>
    );
  }
  return (
    <>
      <label>
        First component it mixes
        <select aria-label="First mix" name="mix_a" defaultValue={textOf(fields, "mix_a") || mixes[0] || ""}>
          <option value="">Choose</option>
          {codes.map((code) => (
            <option key={code}>{code}</option>
          ))}
        </select>
      </label>
      <label>
        Second component it mixes
        <select aria-label="Second mix" name="mix_b" defaultValue={textOf(fields, "mix_b") || mixes[1] || ""}>
          <option value="">Choose</option>
          {codes.map((code) => (
            <option key={code}>{code}</option>
          ))}
        </select>
      </label>
      <label>
        Rookie’s faulty plan
        <textarea aria-label="Faulty plan" name="faulty_plan" defaultValue={textOf(fields, "faulty_plan")} rows={3} />
      </label>
    </>
  );
}
