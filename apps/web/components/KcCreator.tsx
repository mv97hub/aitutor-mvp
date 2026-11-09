"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { useRouter } from "next/navigation";

import { KcBanner } from "@/components/KcBanner";
import { KcBlockCanvas, KcBlockScope } from "@/components/KcBlockCanvas";
import { KcCreatorComposer } from "@/components/KcComposer";
import { markKcComplete, markKcCourseReady, pushKcComponent, saveKcComponent } from "@/lib/kc-actions";
import { BLOCK_LABELS, blockSummary, scopeFromCourse } from "@/lib/kc-blocks";
import {
  type KcComponent,
  type KcCourse,
  type KcCreatorThread,
  type KcMisconception,
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
import { creatorBubbleText } from "@/lib/kc-draft-text";
import { creatorPushPayload } from "@/lib/kc-creator-push";
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
    <main className="ds-shell studio-shell kc-screen kc-creator">
      <KcBanner name="KC Creator">
        <div className="kc-fast">
          {course ? (
            course.ready ? (
              <button className="button" type="button" disabled>
                Course ready
              </button>
            ) : (
              <form className="kc-course-ready-form" action={markKcCourseReady}>
                <input type="hidden" name="course_id" value={course.id} />
                <input type="hidden" name="node_id" value={component?.id ?? ""} />
                <input type="hidden" name="model" value={model} />
                <button className="button" type="submit">
                  Mark whole course ready
                </button>
              </form>
            )
          ) : null}
          {record ? (
            <span className="kc-fast-count" aria-live="polite">
              {record.done} / {record.ids.length}
            </span>
          ) : null}
          {course ? (
            <KcBlockScope
              courseId={course.id}
              nodeId={component?.id ?? ""}
              model={model}
              allowed={course.allowed_block_types}
            />
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
                  <small>{item.blocks?.length ? blockSummary(item.blocks) : "No blocks yet"}</small>
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
              <p className="kc-reply">
                {message.role === "assistant" && message.draft
                  ? creatorBubbleText(message.content, message.draft)
                  : message.content}
              </p>
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
            value={JSON.stringify(creatorPushPayload(draft, component))}
          />
          <button className="button studio-push" type="submit">
            Push draft
          </button>
        </form>
      ) : null}
      <KcCreatorComposer
        courseId={course.id}
        nodeId={component.id}
        model={model}
        formRef={draftFormRef}
        allowedBlockTypes={scopeFromCourse(course.allowed_block_types)}
      />
    </>
  );
}

const TIPS = {
  description: "A short summary of this component. The walk does not read it.",
  outline: "The outline Orient elaborates. It is not a topic.",
  title: "The name the kid sees on the card and during the lesson.",
  core_truth: "The idea the tutor says back after a miss, and the line several steps accept.",
  rubric: "Derived from the blocks, in block order. It is not typed here.",
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
      {component.recommended_blocks?.length ? (
        <p className="ds-quiet">
          Recommended blocks: {component.recommended_blocks.map((item) => BLOCK_LABELS[item.type] ?? item.type).join(", ")}
        </p>
      ) : null}
      {/* Remount when Push draft replaces the saved blocks. Edits stay until that list changes. */}
      <KcBlockCanvas
        key={`${component.id}:${JSON.stringify(component.blocks ?? [])}`}
        initial={component.blocks ?? []}
      />
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
      {component.rubric.length ? (
        <fieldset>
          <legend title={TIPS.rubric}>Rubric checks, from the blocks</legend>
          <ul aria-label="Rubric checks">
            {component.rubric.map((check, index) => (
              <li key={`${index}-${check}`}>{check}</li>
            ))}
          </ul>
        </fieldset>
      ) : null}
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

function HistoryLog({ label, text }: { label: string; text: string }) {
  return (
    <section className="kc-history">
      <h3>{label}</h3>
      <pre aria-label={label}>{text.trim() ? text : "No history yet."}</pre>
    </section>
  );
}
