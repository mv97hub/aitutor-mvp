"use client";

import Link from "next/link";
import { useState } from "react";

import {
  addKcComponent,
  createKcCourse,
  markKcReady,
  moveKcComponent,
  pushKcDraft,
  removeKcComponent,
  saveKcComponent,
  saveKcCourse,
} from "@/lib/kc-actions";
import {
  AUDIENCES,
  KINDS,
  TYPE_LABELS,
  type KcComponent,
  type KcCourse,
  type KcDraft,
  type KcMisconception,
  type KcNetwork,
  type KcStructure,
  type KcType,
} from "@/lib/kc";

export function KcStudio({
  initialCourses,
  initialCourse,
  initialStructure,
  initialComponentId,
  initialNetwork,
  initialDraft,
  initialReply,
  initialMessage,
  initialError,
}: {
  initialCourses: KcCourse[];
  initialCourse: KcCourse | null;
  initialStructure: KcStructure | null;
  initialComponentId: string | null;
  initialNetwork: KcNetwork | null;
  initialDraft: KcDraft | null;
  initialReply: string;
  initialMessage: string;
  initialError: string | null;
}) {
  const course = initialCourse;
  const component =
    course == null || initialComponentId == null
      ? null
      : (course.components.find((item) => item.id === initialComponentId) ??
        course.patches.find((item) => item.id === initialComponentId) ??
        null);
  const order = course?.components.map((item) => item.id) ?? [];

  return (
    <main className="kc-app">
      <header className="kc-bar">
        <Link href="/">Home</Link>
        <strong>KC Studio</strong>
        <span>Course first, then one component. The chat only drafts.</span>
      </header>
      <div className="kc-studio">
        <aside className="kc-rail">
          <ul className="kc-course-list" aria-label="Courses">
            {initialCourses.map((item) => (
              <li key={item.id}>
                <a className={course?.id === item.id ? "is-on" : ""} href={`/kc-studio?course=${item.id}`}>
                  <span>{item.title}</span>
                  <small>{item.ready ? "Ready" : "Draft"}</small>
                </a>
              </li>
            ))}
          </ul>
          <form className="kc-create" action={createKcCourse}>
            <h2>New course</h2>
            <label>
              Name
              <input aria-label="New course name" name="title" required />
            </label>
            <label>
              What the kid should come away able to do
              <textarea aria-label="New course description" name="description" rows={3} />
            </label>
            <label>
              Audience
              <select aria-label="New course audience" name="audience" defaultValue="12-14">
                {AUDIENCES.map((band) => (
                  <option key={band}>{band}</option>
                ))}
              </select>
            </label>
            <label>
              Kind
              <select aria-label="New course kind" name="kind" defaultValue="mastery">
                {KINDS.map((kind) => (
                  <option key={kind.id} value={kind.id}>
                    {kind.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Minutes, optional
              <input aria-label="New course minutes" name="minutes" inputMode="numeric" />
            </label>
            <button className="kc-primary" type="submit">
              Create course
            </button>
          </form>
        </aside>
        <section className="kc-main">
          {initialError ? (
            <p className="kc-error" role="alert">
              {initialError}
            </p>
          ) : null}
          {!course ? <p className="kc-quiet">Choose a course, or create one.</p> : null}
          {course ? (
            <>
              <form className="kc-course" action={saveKcCourse} key={course.id}>
                <input type="hidden" name="course_id" value={course.id} />
                <label>
                  Name
                  <input aria-label="Course name" name="title" defaultValue={course.title} required />
                </label>
                <label className="kc-wide">
                  What the kid should come away able to do
                  <textarea
                    aria-label="Course description"
                    name="description"
                    defaultValue={course.description}
                    rows={3}
                  />
                </label>
                <label>
                  Audience
                  <select aria-label="Audience" name="audience" defaultValue={course.audience}>
                    {AUDIENCES.map((band) => (
                      <option key={band}>{band}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Kind
                  <select aria-label="Kind" name="kind" defaultValue={course.kind}>
                    {KINDS.map((kind) => (
                      <option key={kind.id} value={kind.id}>
                        {kind.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Minutes, optional
                  <input
                    aria-label="Minutes"
                    name="minutes"
                    inputMode="numeric"
                    defaultValue={course.minutes ?? ""}
                  />
                </label>
                <div className="kc-actions">
                  <button className="kc-primary" type="submit">
                    Save course
                  </button>
                  <a href={`/kc-studio?course=${course.id}&network=1`}>Network</a>
                  <button type="submit" formAction={markKcReady}>
                    {course.ready ? "Ready" : "Mark ready"}
                  </button>
                </div>
              </form>
              {component ? (
                <ComponentEditor key={component.id} course={course} component={component} />
              ) : (
                <StructureView courseId={course.id} structure={initialStructure} patches={course.patches} order={order} />
              )}
            </>
          ) : null}
        </section>
        <aside className="kc-chat">
          <h2>{component ? "This component" : "Component list"}</h2>
          <p className="kc-quiet">
            {component
              ? "The draft replaces this component only. Push draft is the write."
              : "The draft is a list of components. Nothing is stored until you push it."}
          </p>
          {initialMessage ? (
            <ol className="kc-transcript" aria-live="polite">
              <li className="user">{initialMessage}</li>
              {initialReply ? <li className="assistant">{initialReply}</li> : null}
            </ol>
          ) : null}
          {initialDraft?.kind === "course" ? (
            <ul className="kc-draft-list" aria-label="Draft component list">
              {initialDraft.components.map((item) => (
                <li key={item.code}>{item.title}</li>
              ))}
            </ul>
          ) : null}
          {initialDraft?.kind === "component" ? (
            <p className="kc-draft-note">
              Draft type: {TYPE_LABELS[initialDraft.kc_type] ?? initialDraft.kc_type}. {initialDraft.core_truth}
            </p>
          ) : null}
          {course ? (
            <form method="get" action="/kc-studio">
              <input type="hidden" name="course" value={course.id} />
              {component ? <input type="hidden" name="component" value={component.id} /> : null}
              <label>
                Ask for a draft
                <textarea aria-label="Studio chat" name="message" rows={3} required />
              </label>
              <div className="kc-actions">
                <button className="kc-primary" type="submit">
                  Draft
                </button>
              </div>
            </form>
          ) : (
            <p className="kc-quiet">Open a course before asking for a draft.</p>
          )}
          {course && initialDraft?.kind === "course" ? (
            <form action={pushKcDraft}>
              <input type="hidden" name="course_id" value={course.id} />
              <input type="hidden" name="kind" value="course" />
              <input type="hidden" name="components" value={JSON.stringify(initialDraft.components)} />
              <button className="kc-primary" type="submit">
                Push draft
              </button>
            </form>
          ) : null}
          {course && initialDraft?.kind === "component" && component ? (
            <form action={pushKcDraft}>
              <input type="hidden" name="course_id" value={course.id} />
              <input type="hidden" name="kind" value="component" />
              <input type="hidden" name="node_id" value={component.id} />
              <input
                type="hidden"
                name="payload"
                value={JSON.stringify({
                  title: initialDraft.title,
                  kc_type: initialDraft.kc_type,
                  core_truth: initialDraft.core_truth,
                  rubric: initialDraft.rubric,
                  misconceptions: initialDraft.misconceptions,
                  prerequisite_codes: initialDraft.prerequisite_codes,
                  encompasses_codes: initialDraft.encompasses_codes,
                  type_fields: initialDraft.type_fields,
                })}
              />
              <button className="kc-primary" type="submit">
                Push draft
              </button>
            </form>
          ) : null}
        </aside>
      </div>
      {initialNetwork && course ? (
        <NetworkModal title={course.title} network={initialNetwork} closeHref={`/kc-studio?course=${course.id}`} />
      ) : null}
    </main>
  );
}

function StructureView({
  courseId,
  structure,
  patches,
  order,
}: {
  courseId: string;
  structure: KcStructure | null;
  patches: KcComponent[];
  order: string[];
}) {
  return (
    <div className="kc-structure">
      <h2>Course structure</h2>
      {structure?.groups.map((group) => (
        <section key={group.kc_type}>
          <h3>{TYPE_LABELS[group.kc_type] ?? group.kc_type}</h3>
          <ul>
            {group.components.map((row) => (
              <li key={row.id}>
                <a href={`/kc-studio?course=${courseId}&component=${row.id}`}>
                  <strong>{row.title}</strong>
                  <span>{TYPE_LABELS[row.kc_type ?? "unset"]}</span>
                  {row.missing.length ? <em>{row.missing.join(", ")}</em> : <em>Complete</em>}
                </a>
                <span className="kc-row-actions">
                  <form action={moveKcComponent}>
                    <input type="hidden" name="course_id" value={courseId} />
                    <input type="hidden" name="id" value={row.id} />
                    <input type="hidden" name="direction" value="-1" />
                    {order.map((id) => (
                      <input key={id} type="hidden" name="order" value={id} />
                    ))}
                    <button type="submit" aria-label={`Move ${row.title} up`}>
                      Up
                    </button>
                  </form>
                  <form action={moveKcComponent}>
                    <input type="hidden" name="course_id" value={courseId} />
                    <input type="hidden" name="id" value={row.id} />
                    <input type="hidden" name="direction" value="1" />
                    {order.map((id) => (
                      <input key={id} type="hidden" name="order" value={id} />
                    ))}
                    <button type="submit" aria-label={`Move ${row.title} down`}>
                      Down
                    </button>
                  </form>
                  <form action={removeKcComponent}>
                    <input type="hidden" name="course_id" value={courseId} />
                    <input type="hidden" name="id" value={row.id} />
                    <button type="submit" aria-label={`Remove ${row.title}`}>
                      Remove
                    </button>
                  </form>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {patches.length ? (
        <section>
          <h3>Patches</h3>
          <ul>
            {patches.map((patch) => (
              <li key={patch.id}>
                <a href={`/kc-studio?course=${courseId}&component=${patch.id}`}>
                  <strong>{patch.title}</strong>
                  <span>{TYPE_LABELS[patch.kc_type ?? "unset"]}</span>
                  <em>Not a target</em>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <form className="kc-add" action={addKcComponent}>
        <input type="hidden" name="course_id" value={courseId} />
        <label>
          Add a component by hand
          <input aria-label="New component title" name="title" required />
        </label>
        <button type="submit">Add</button>
      </form>
    </div>
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

  return (
    <form className="kc-detail" action={saveKcComponent}>
      <input type="hidden" name="course_id" value={course.id} />
      <input type="hidden" name="node_id" value={component.id} />
      <div className="kc-actions">
        <a href={`/kc-studio?course=${course.id}`}>Back to the course</a>
        <h2>Component</h2>
      </div>
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
      <button className="kc-primary" type="submit">
        Save this component
      </button>
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

function NetworkModal({ title, network, closeHref }: { title: string; network: KcNetwork; closeHref: string }) {
  const targets = network.nodes.filter((node) => !node.patch);
  const patches = network.nodes.filter((node) => node.patch);
  const pos = new Map<string, { x: number; y: number }>();
  targets.forEach((node, index) => {
    pos.set(node.code, { x: 130 + (index % 3) * 190, y: 78 + Math.floor(index / 3) * 120 });
  });
  patches.forEach((node, index) => {
    pos.set(node.code, { x: 720, y: 78 + index * 120 });
  });
  const height = Math.max(360, 100 + Math.max(Math.ceil(targets.length / 3), patches.length, 1) * 120);
  return (
    <div className="kc-modal" role="presentation">
      <div className="kc-modal-card" role="dialog" aria-modal="true" aria-label={`${title} network`}>
        <div className="kc-actions">
          <h2>Network</h2>
          <a href={closeHref}>Close</a>
        </div>
        <p className="kc-quiet">View only. A node is a component. Patches sit at the edge.</p>
        <svg className="kc-net" viewBox={`0 0 840 ${height}`} role="img" aria-label="Component network">
          {network.edges.map((edge, index) => {
            const from = pos.get(edge.from_code);
            const to = pos.get(edge.to_code);
            if (!from || !to) return null;
            return (
              <line
                key={index}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                className={edge.kind === "encompasses" ? "is-encompass" : "is-prereq"}
              />
            );
          })}
          {network.nodes.map((node) => {
            const point = pos.get(node.code);
            if (!point) return null;
            return (
              <g key={node.code}>
                <circle cx={point.x} cy={point.y} r={28} className={node.patch ? "is-patch" : ""} />
                <text x={point.x} y={point.y + 46} textAnchor="middle">
                  {node.title.length > 22 ? `${node.title.slice(0, 20)}…` : node.title}
                </text>
              </g>
            );
          })}
        </svg>
        <ul className="kc-edge-list">
          {network.edges.map((edge, index) => (
            <li key={index}>
              {edge.from_code} {edge.kind === "prerequisite_of" ? "is a prerequisite of" : "encompasses"} {edge.to_code}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
