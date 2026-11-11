"use client";

import { useEffect, useRef, useState } from "react";

import { useCreatorDebug } from "@/components/CreatorDebug";
import { KcBlueprintEditor } from "@/components/KcBlueprintEditor";
import { pushKcDraft } from "@/lib/kc-actions";
import type { KcBlueprint, KcPipeline } from "@/lib/kc";
import { KC_MODELS, kcModel } from "@/lib/kc-models";
import { pipelineAction, requestOf, runPipeline, stageRunner, workingText } from "@/lib/kc-pipeline";
import { promptTurnId } from "@/lib/kc-prompt-log";
import type { StageEvent } from "@/lib/kc-stage";

const CHECK_LABELS: Record<string, string> = {
  gaps: "Gaps",
  overlap: "Overlap",
  jumps: "Steps that jump too far",
  capstone: "Capstone",
  outcomes: "Outcomes",
  reading_level: "Reading level",
};

function actionLabel(state: KcPipeline): string | null {
  const next = requestOf(state.next);
  if (!next) return null;
  if (next.stage === "brief") return "Write the brief";
  if (next.stage === "blueprint") return "Plan the blueprint";
  if (next.stage === "review") return "Review the course";
  if (state.units_done === 0) return "Write the descriptions";
  return `Write unit ${state.units_done + 1} of ${state.units_total}`;
}

/** Brief, blueprint, unit descriptions, and the review. A retry starts at the stage that failed. */
export function KcPipelinePanel({
  courseId,
  model,
  pipeline,
}: {
  courseId: string;
  model: string;
  pipeline: KcPipeline;
}) {
  const [state, setState] = useState(pipeline);
  const [modelId, setModelId] = useState(kcModel(model));
  const [working, setWorking] = useState<string | null>(null);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const debug = useCreatorDebug();
  const unitsTotal = useRef(pipeline.units_total);
  const abort = useRef<AbortController | null>(null);
  unitsTotal.current = state.units_total;

  useEffect(() => () => abort.current?.abort(), []);

  function remember(event: StageEvent) {
    if (event.type === "prompt") {
      debug?.record({
        id: promptTurnId([courseId, event.label, event.instructions, event.prompt]),
        prompts: [{ label: event.label, instructions: event.instructions, prompt: event.prompt }],
      });
    }
    if (event.type === "progress") setProgress(`${event.label}: ${event.items} so far`);
    if (event.type === "retry") setProgress(`Retrying ${event.label}. ${event.message}`);
  }

  async function go(from: KcPipeline) {
    if (working) return;
    const controller = new AbortController();
    abort.current?.abort();
    abort.current = controller;
    setError(null);
    setProgress("");
    setWorking(workingText(from) ?? "Working…");
    try {
      const done = await runPipeline(
        from,
        stageRunner(courseId, modelId, () => unitsTotal.current, controller.signal),
        (next) => {
          unitsTotal.current = next.units_total;
          setState(next);
          setWorking(workingText(next) ?? "Working…");
          setProgress("");
        },
        remember,
        () => controller.signal.aborted,
      );
      if (!controller.signal.aborted) setState(done);
    } catch (err) {
      if (controller.signal.aborted) return;
      setError(err instanceof Error ? err.message : "The stage failed.");
    } finally {
      if (abort.current === controller) setWorking(null);
    }
  }

  async function answer(formData: FormData, skip: boolean) {
    setError(null);
    try {
      const answers = state.questions.map((question) => ({
        question,
        answer: String(formData.get(question) || "").trim(),
      }));
      const next = await pipelineAction(courseId, "answers", { answers, skip });
      setState(next);
      if (next.next) await go(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Those answers did not save.");
    }
  }

  async function saveBlueprint(blueprint: KcBlueprint, approve: boolean) {
    setError(null);
    try {
      const next = await pipelineAction(courseId, "blueprint", { blueprint, approve });
      setState(next);
      if (approve && next.next) await go(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The blueprint did not save.");
    }
  }

  async function reset() {
    setError(null);
    abort.current?.abort();
    try {
      setState(await pipelineAction(courseId, "reset"));
      setProgress("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The draft did not reset.");
    }
  }

  const label = actionLabel(state);
  const failedStage = error && state.next ? requestOf(state.next) : null;

  return (
    <div className="kc-pipeline">
      {state.missing.length && state.stage === "brief" ? (
        <p className="ds-quiet">Fill in {state.missing.join(", ")} before drafting.</p>
      ) : null}
      {state.brief ? (
        <p className="kc-brief">
          <strong>Brief. </strong>
          {state.brief}
        </p>
      ) : null}
      {error ? (
        <div className="banner" role="alert">
          <p>{error}</p>
          {failedStage ? <p>Retry runs {failedStage.stage === "unit" ? "that unit" : `the ${failedStage.stage}`} again.</p> : null}
        </div>
      ) : null}
      {working ? (
        <p className="ds-typing" role="status">
          {working}
          {progress ? ` ${progress}` : ""}
        </p>
      ) : null}

      {state.stage === "questions" ? (
        <form
          className="kc-questions"
          onSubmit={(event) => {
            event.preventDefault();
            void answer(new FormData(event.currentTarget), false);
          }}
        >
          <h2>Two follow-ups</h2>
          {state.questions.map((question) => (
            <label key={question}>
              {question}
              <textarea aria-label={question} name={question} rows={2} required={state.questions.length === 1} />
            </label>
          ))}
          <div className="kc-pipeline-actions">
            <button className="button" type="submit" disabled={Boolean(working)}>
              Answer
            </button>
            <button
              className="ghost"
              type="button"
              disabled={Boolean(working)}
              onClick={() => void answer(new FormData(), true)}
            >
              Skip
            </button>
          </div>
        </form>
      ) : null}

      {state.blueprint && state.stage === "edit_blueprint" ? (
        <KcBlueprintEditor
          blueprint={state.blueprint}
          busy={Boolean(working)}
          onSave={(blueprint) => void saveBlueprint(blueprint, false)}
          onApprove={(blueprint) => void saveBlueprint(blueprint, true)}
        />
      ) : null}

      {state.stage === "units" || state.stage === "review" ? (
        <p className="ds-quiet">
          {state.units_done} of {state.units_total} units written.
        </p>
      ) : null}

      {state.review ? (
        <ul className="kc-review" aria-label="Review">
          {state.review.checks.map((check) => (
            <li key={check.name}>
              <strong>{CHECK_LABELS[check.name] ?? check.name}.</strong> {check.result}
              {check.note ? ` ${check.note}` : ""}
            </li>
          ))}
        </ul>
      ) : null}

      {state.draft ? (
        <>
          <ol className="kc-draft-list" aria-label="Draft component list">
            {state.draft.components.map((item) => (
              <li key={item.code}>
                <strong>{item.title}</strong> <span className="studio-code">{item.code}</span>
                <p className="kc-brief">{item.description}</p>
                <p className="ds-quiet">
                  {item.position ? `Component ${item.position}` : "Component"}
                  {item.unit ? `, ${item.unit}` : ""}. Prerequisites: {item.prerequisite_codes.join(", ") || "none"}
                </p>
              </li>
            ))}
          </ol>
          <form action={pushKcDraft}>
            <input type="hidden" name="course_id" value={courseId} />
            <input type="hidden" name="components" value={JSON.stringify(state.draft.components)} />
            <button className="button studio-push" type="submit">
              Push draft
            </button>
          </form>
          {state.pushed ? <p className="ds-quiet">Pushed. The structure on the left has the components.</p> : null}
        </>
      ) : null}

      <div className="kc-pipeline-actions">
        {label ? (
          <button className="button" type="button" disabled={Boolean(working)} onClick={() => void go(state)}>
            {error ? "Retry this stage" : label}
          </button>
        ) : null}
        {state.stage !== "brief" || state.brief ? (
          <button className="ghost" type="button" disabled={Boolean(working)} onClick={() => void reset()}>
            Start over
          </button>
        ) : null}
        <label className="kc-model">
          Model
          <select aria-label="Model" value={modelId} disabled={Boolean(working)} onChange={(event) => setModelId(kcModel(event.target.value))}>
            {KC_MODELS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && failedStage ? <p className="ds-quiet">This retry starts at the stage that failed.</p> : null}
    </div>
  );
}
