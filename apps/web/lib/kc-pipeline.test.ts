import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import type { KcPipeline } from "./kc.ts";
import { PipelineStageError, runPipeline, type RunStage } from "./kc-pipeline.ts";
import { combineBlueprint, combineReview, partialItems, progressLine, runStage, stageLabel, STAGE_TOKEN_LIMITS, type StageEvent, type StageRequest } from "./kc-stage.ts";

function pipeline(next: KcPipeline["next"], extra: Partial<KcPipeline> = {}): KcPipeline {
  return {
    stage: next?.stage === "unit" ? "units" : next?.stage === "review" ? "review" : "brief",
    next,
    brief: "",
    questions: [],
    answers: [],
    standards: [],
    standards_source: "",
    coverage: null,
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

test("streaming progress counts components, not outcomes or units", () => {
  assert.equal(partialItems(null), 0);
  assert.equal(partialItems({ outcomes: ["Name it.", "Use it.", "Apply it.", "Check it."] }), 0);
  assert.equal(partialItems({ outcomes: ["Name it.", "Use it.", "Apply it.", "Check it."], units: [] }), 0);
  assert.equal(partialItems({ outcomes: ["Name it."], units: [{ title: "Next" }] }), 0);
  assert.equal(partialItems({ outcomes: ["Name it.", "Use it."], units: [{ components: [{}, {}] }, { components: [{}] }] }), 3);
  assert.equal(partialItems({ outcomes: ["Name it."], unit: { components: [{}] } }), 1);
  assert.equal(partialItems({ components: [{}, {}, {}] }), 3);
  assert.equal(progressLine("Blueprint", 3), "Blueprint: 3 components so far");
  assert.equal(progressLine("Blueprint (retry)", 1), "Blueprint (retry): 1 component so far");
  assert.equal(progressLine("Unit 2 of 2", 2), "Unit 2 of 2: 2 so far");
});

test("a blueprint retry labels the counter instead of resetting it", async () => {
  const events: StageEvent[] = [];
  let calls = 0;
  await runStage(
    { stage: "blueprint", unit: null },
    {
      bundle: async () => ({ model: "gpt-4.1", system_prompt: "Plan.", user_prompt: "Go.", schema: {} }),
      generate: async (input) => {
        calls += 1;
        input.onPartial({
          outcomes: ["Name it.", "Use it.", "Apply it."],
          units: [{ components: [{}, {}] }, { components: [{}] }],
        });
        if (calls === 1) throw new Error("You returned 13. Return between 8 and 12 components.");
        return { outcomes: ["Name it.", "Use it."], units: [] };
      },
      store: async () => pipeline(null),
    },
    (event) => events.push(event),
  );
  const progress = events.filter((event) => event.type === "progress");
  assert.equal(progress[0]?.label, "Blueprint");
  assert.equal(progress[0]?.items, 3);
  assert.equal(progressLine(progress[0]?.label ?? "", progress[0]?.items ?? 0), "Blueprint: 3 components so far");
  assert.equal(progress[1]?.label, "Blueprint (retry)");
  assert.equal(progress[1]?.items, 3);
  assert.equal(progressLine("Blueprint (retry)", 3), "Blueprint (retry): 3 components so far");
});

function progressCounts(events: StageEvent[]): number[] {
  return events.filter((event) => event.type === "progress").map((event) => (event.type === "progress" ? event.items : 0));
}

test("blueprint progress does not fall back when outcomes or the next unit start", async () => {
  const single: StageEvent[] = [];
  await runStage(
    { stage: "blueprint", unit: null },
    {
      bundle: async () => ({ model: "gpt-4.1", system_prompt: "Plan.", user_prompt: "Go.", schema: {} }),
      generate: async (input) => {
        input.onPartial({ outcomes: ["a", "b", "c", "d"] });
        input.onPartial({ outcomes: ["a", "b", "c", "d"], units: [] });
        input.onPartial({ outcomes: ["a", "b", "c", "d"], units: [{ components: [{}, {}] }] });
        return { outcomes: ["a", "b"], units: [{ components: [{}, {}] }] };
      },
      store: async () => pipeline(null),
    },
    (event) => single.push(event),
  );
  assert.deepEqual(progressCounts(single), [2]);

  const split: StageEvent[] = [];
  let calls = 0;
  await runStage(
    { stage: "blueprint", unit: null },
    {
      bundle: async () => ({
        model: "gpt-4.1",
        system_prompt: "Plan.",
        user_prompt: "Go.",
        schema: {},
        combine: "blueprint",
        calls: [1, 2].map((number) => ({
          label: `Blueprint unit ${number} of 2`,
          system_prompt: "Plan.",
          user_prompt: `Plan unit ${number}.`,
          schema: {},
        })),
      }),
      generate: async (input) => {
        calls += 1;
        if (calls === 1) {
          input.onPartial({ outcomes: ["a", "b", "c", "d"] });
          input.onPartial({ outcomes: ["a", "b", "c", "d"], unit: { title: "One" } });
          input.onPartial({
            outcomes: ["a", "b", "c", "d"],
            unit: { title: "One", components: [{}, {}, {}, {}, {}, {}] },
          });
          return { outcomes: ["a", "b"], unit: { title: "One", components: [{}, {}, {}, {}, {}, {}] } };
        }
        input.onPartial({ unit: { title: "Two" } });
        input.onPartial({ unit: { title: "Two", components: [{}] } });
        return { unit: { title: "Two", components: [{}] } };
      },
      store: async () => pipeline(null),
    },
    (event) => split.push(event),
  );
  assert.deepEqual(progressCounts(split), [6, 6, 7]);
});

test("a blueprint retry fetches the corrected bounds", async () => {
  const generated: string[] = [];
  let fetches = 0;
  await runStage(
    { stage: "blueprint", unit: null },
    {
      bundle: async () => {
        fetches += 1;
        return {
          model: "gpt-4.1",
          system_prompt: "Return exactly 42 components.",
          user_prompt: "Plan the course blueprint.",
          schema: {},
        };
      },
      generate: async (input) => {
        generated.push(input.instructions);
        assert.equal(input.maxOutputTokens, STAGE_TOKEN_LIMITS.blueprint);
        if (generated.length === 1) throw new Error("You returned 13. Return exactly 42 components.");
        return { outcomes: ["Name it.", "Use it."], units: [] };
      },
      store: async () => pipeline(null),
    },
    () => {},
  );
  assert.equal(fetches, 2);
  assert.match(generated[1] ?? "", /exactly 42/);
  assert.doesNotMatch(generated[1] ?? "", /8 and 12/);
});

test("a long matched blueprint is one call per unit inside the unit token ceiling", async () => {
  const tokens: number[] = [];
  let stored: { outcomes?: string[]; units?: { title?: string }[] } | null = null;
  await runStage(
    { stage: "blueprint", unit: null },
    {
      bundle: async () => ({
        model: "gpt-4.1",
        system_prompt: "Return exactly 42 components.",
        user_prompt: "Plan the course blueprint.",
        schema: {},
        combine: "blueprint",
        calls: [1, 2].map((number) => ({
          label: `Blueprint unit ${number} of 2`,
          system_prompt: `Plan unit ${number}. Return exactly 1 component.`,
          user_prompt: `Plan unit ${number}.`,
          schema: {},
        })),
      }),
      generate: async (input) => {
        tokens.push(input.maxOutputTokens);
        const number = input.prompt.includes("1") ? "One" : "Two";
        return {
          outcomes: ["Name it.", "Use it."],
          unit: { title: number, summary: "A unit.", components: [{ ref: "c1", title: number, summary: "Teaches it.", prerequisites: [] }] },
        };
      },
      store: async (result) => {
        stored = result as { outcomes: string[]; units: { title: string }[] };
        return pipeline(null, { stage: "edit_blueprint" });
      },
    },
    () => {},
  );
  assert.deepEqual(tokens, [STAGE_TOKEN_LIMITS.unit, STAGE_TOKEN_LIMITS.unit]);
  assert.deepEqual(stored?.units?.map((unit) => unit.title), ["One", "Two"]);
  assert.deepEqual(stored?.outcomes, ["Name it.", "Use it."]);
});

test("unit reviews combine into one check", () => {
  const combined = combineReview([
    {
      checks: [
        { name: "gaps", result: "ok", note: "" },
        { name: "overlap", result: "fixed", note: "Merged a repeat." },
        { name: "jumps", result: "ok", note: "" },
        { name: "capstone", result: "ok", note: "" },
        { name: "outcomes", result: "ok", note: "" },
        { name: "reading_level", result: "ok", note: "" },
      ],
      outcomes: ["Name it.", "Use it."],
      revisions: [{ code: "a" }],
      additions: [],
    },
    {
      checks: [
        { name: "gaps", result: "issue", note: "A step is missing." },
        { name: "overlap", result: "ok", note: "" },
        { name: "jumps", result: "ok", note: "" },
        { name: "capstone", result: "fixed", note: "Added a close." },
        { name: "outcomes", result: "ok", note: "" },
        { name: "reading_level", result: "issue", note: "Too hard." },
      ],
      outcomes: null,
      revisions: [],
      additions: [{ title: "Close" }],
    },
  ]);
  const byName = Object.fromEntries(combined.checks.map((check) => [check.name, check]));
  assert.equal(byName.gaps?.result, "issue");
  assert.equal(byName.overlap?.result, "fixed");
  assert.match(byName.overlap?.note ?? "", /Merged a repeat/);
  assert.equal(byName.capstone?.result, "fixed");
  assert.equal(combined.revisions.length, 1);
  assert.equal(combined.additions.length, 1);
  assert.deepEqual(combined.outcomes, ["Name it.", "Use it."]);
  const blueprint = combineBlueprint([
    { outcomes: ["Name it.", "Use it."], unit: { title: "One" } },
    { unit: { title: "Two" } },
  ]);
  assert.deepEqual(blueprint.units, [{ title: "One" }, { title: "Two" }]);
});

test("the course draft route streams with a token limit and a long duration", () => {
  const route = readFileSync(new URL("../app/api/kc/course-draft/route.ts", import.meta.url), "utf8");
  const model = readFileSync(new URL("./kc-stage-model.ts", import.meta.url), "utf8");
  assert.match(route, /maxDuration = 300/);
  assert.match(route, /application\/x-ndjson/);
  assert.match(route, /STAGE_TOKEN_LIMITS\.unit/);
  assert.match(model, /maxOutputTokens: input.maxOutputTokens/);
  assert.match(model, /partialOutputStream/);
});
