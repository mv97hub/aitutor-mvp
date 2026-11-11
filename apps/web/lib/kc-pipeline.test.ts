import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import type { KcPipeline } from "./kc.ts";
import { PipelineStageError, runPipeline, type RunStage } from "./kc-pipeline.ts";
import { partialItems, runStage, stageLabel, STAGE_TOKEN_LIMITS, type StageRequest } from "./kc-stage.ts";

function pipeline(next: KcPipeline["next"], extra: Partial<KcPipeline> = {}): KcPipeline {
  return {
    stage: next?.stage === "unit" ? "units" : next?.stage === "review" ? "review" : "brief",
    next,
    brief: "",
    questions: [],
    answers: [],
    blueprint: null,
    approved: false,
    units_total: 2,
    units_done: next?.unit ?? 0,
    descriptions: {},
    review: null,
    pushed: false,
    missing: [],
    draft: null,
    ...extra,
  };
}

test("a failed stage is the only one retried", async () => {
  const seen: string[] = [];
  let fail = true;
  const run: RunStage = async (request) => {
    seen.push(`${request.stage}:${request.unit ?? ""}`);
    if (request.stage === "unit" && request.unit === 1 && fail) {
      fail = false;
      throw new PipelineStageError("The description was too short.", request);
    }
    if (request.stage === "unit") {
      const done = (request.unit ?? 0) + 1;
      const last = done >= 2;
      return pipeline(last ? { stage: "review", unit: null } : { stage: "unit", unit: done }, {
        stage: last ? "review" : "units",
        units_done: done,
      });
    }
    return pipeline(null, { stage: "draft", draft: { kind: "course", components: [] } });
  };

  await assert.rejects(runPipeline(pipeline({ stage: "unit", unit: 0 }), run, () => {}), /too short/);
  assert.deepEqual(seen, ["unit:0", "unit:1"]);

  const finished = await runPipeline(pipeline({ stage: "unit", unit: 1 }, { units_done: 1, stage: "units" }), run, () => {});
  assert.equal(finished.stage, "draft");
  assert.deepEqual(seen, ["unit:0", "unit:1", "unit:1", "review:"]);
});

test("the run stops when the next step needs the author", async () => {
  const seen: string[] = [];
  const run: RunStage = async (request) => {
    seen.push(request.stage);
    return pipeline(null, { stage: "edit_blueprint" });
  };
  const stopped = await runPipeline(pipeline({ stage: "blueprint", unit: null }), run, () => {});
  assert.equal(stopped.stage, "edit_blueprint");
  assert.deepEqual(seen, ["blueprint"]);
});

test("one stage retries its own model call and stores once", async () => {
  const request: StageRequest = { stage: "unit", unit: 1 };
  const generated: string[] = [];
  const stored: unknown[] = [];
  let reject = true;
  const pipelineState = pipeline(null, { stage: "units", units_done: 2 });
  const done = await runStage(
    request,
    {
      bundle: async () => ({ model: "gpt-4.1", system_prompt: "Write unit 2.", user_prompt: "Go.", schema: {} }),
      generate: async (input) => {
        generated.push(input.instructions);
        assert.equal(input.maxOutputTokens, STAGE_TOKEN_LIMITS.unit);
        input.onPartial({ components: [{ code: "a" }, { code: "b" }] });
        if (reject) {
          reject = false;
          throw new Error("3 to 4 sentences");
        }
        return { components: [] };
      },
      store: async (result) => {
        stored.push(result);
        return pipelineState;
      },
    },
    () => {},
    2,
  );
  assert.equal(done, pipelineState);
  assert.equal(stored.length, 1);
  assert.equal(generated.length, 2);
  assert.match(generated[1] ?? "", /3 to 4 sentences/);
  assert.equal(stageLabel("unit", 1, 2), "Unit 2 of 2");
});

test("a stage that keeps failing does not store a result", async () => {
  await assert.rejects(
    runStage(
      { stage: "brief", unit: null },
      {
        bundle: async () => ({ model: "gpt-4.1", system_prompt: "Brief.", user_prompt: "Go.", schema: {} }),
        generate: async () => {
          throw new Error("no key");
        },
        store: async () => {
          throw new Error("store should not run");
        },
      },
      () => {},
    ),
    /no key/,
  );
});

test("streaming progress counts the rows written so far", () => {
  assert.equal(partialItems(null), 0);
  assert.equal(partialItems({ units: [{ components: [{}, {}] }, { components: [{}] }] }), 5);
});

test("the course draft route streams with a token limit and a long duration", () => {
  const route = readFileSync(new URL("../app/api/kc/course-draft/route.ts", import.meta.url), "utf8");
  const model = readFileSync(new URL("./kc-stage-model.ts", import.meta.url), "utf8");
  assert.match(route, /maxDuration = 300/);
  assert.match(route, /application\/x-ndjson/);
  assert.match(model, /maxOutputTokens: input.maxOutputTokens/);
  assert.match(model, /partialOutputStream/);
});
