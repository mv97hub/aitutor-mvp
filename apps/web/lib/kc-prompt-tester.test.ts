import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { LAYER_FIELDS, LAYER_HEADINGS } from "./kc-layer-fields.ts";
import type { KcComponent, KcCourse } from "./kc.ts";
import type { Student } from "./types.ts";
import {
  DEFAULT_TUTOR_PROFILE,
  READ_ONLY_DERIVED,
  applyChild,
  applyResult,
  applyUnit,
  blocksForUnit,
  choiceForMove,
  coursePosition,
  emptyTesterValues,
  fieldsForLayer,
  formFields,
  isReadOnly,
  prerequisiteStatus,
  testerPayload,
} from "./kc-prompt-tester.ts";

function component(overrides: Partial<KcComponent> = {}): KcComponent {
  return {
    id: "unit-1",
    code: "angles",
    title: "Angle sum",
    description: "Why a triangle's angles add up.",
    outline: "",
    topics: [],
    kc_type: "conceptual",
    target: true,
    core_truth: "The angles add to 180.",
    rubric: ["States 180."],
    misconceptions: [{ wrong_move: "They add to 90.", broken_kc: "right-angle" }],
    prerequisite_codes: ["lines"],
    encompasses_codes: ["polygons"],
    type_fields: { transfer_case: "a quadrilateral", case_a: "thin", case_b: "wide" },
    marked_complete: false,
    missing: [],
    history: "",
    ...overrides,
  };
}

function course(overrides: Partial<KcCourse> = {}): KcCourse {
  const first = component();
  const second = component({
    id: "unit-2",
    code: "exterior",
    title: "Exterior angle",
    kc_type: "factual",
    prerequisite_codes: [],
    type_fields: { fact: "An exterior angle equals the far interior angles." },
  });
  return {
    id: "course-1",
    code: "geometry",
    title: "Triangles",
    description: "See why the angles add up.",
    audience: "12-14",
    kind: "mastery",
    minutes: null,
    ready: false,
    history: "",
    components: [first, second],
    patches: [component({ id: "patch-1", code: "patch", title: "Lines", target: false })],
    ...overrides,
  };
}

test("layer headings keep their numbers", () => {
  assert.deepEqual([...LAYER_HEADINGS], [
    "Layer 1, Component",
    "Layer 2, Child",
    "Layer 3, Voice",
    "Layer 4, Guidance",
    "Layer 5, Encouragement",
    "Layer 6, Metacognition",
    "Layer 7, Feedback loop",
  ]);
  assert.deepEqual(
    LAYER_HEADINGS.flatMap((heading) => fieldsForLayer(heading).map((field) => field.layer)),
    formFields().map((field) => field.layer),
  );
});

test("the form skips the model and keeps computed fields read-only", () => {
  assert.equal(formFields().some((field) => field.name === "Model"), false);
  assert.deepEqual([...READ_ONLY_DERIVED], [
    "Move name",
    "Evidence",
    "Effective struggle window",
    "Effective enrichment",
    "Asks why",
  ]);
  for (const name of READ_ONLY_DERIVED) {
    assert.equal(isReadOnly(name), true);
    assert.equal(LAYER_FIELDS.find((field) => field.name === name)?.kind, "Derived");
  }
  const payload = testerPayload(emptyTesterValues(DEFAULT_TUTOR_PROFILE), { fact: "kept" });
  assert.equal("effective_struggle_window" in payload, false);
  assert.equal("move_name" in payload, false);
  assert.equal("asks_why" in payload, false);
  assert.equal(payload.instructive, 3);
  assert.equal(payload.unit_close, "no");
  assert.equal(payload.persona, "curious-co-explorer");
  assert.deepEqual(payload.type_fields, { fact: "kept" });
  assert.deepEqual(payload.blocks, []);
});

test("the prompt tester previews the unit's catalog block fields", () => {
  const unit = component({
    blocks: [
      {
        id: "blk-1",
        type: "retrieval_check",
        data: {
          recall_prompt: "What do the angles add to?",
          expected_fact: "180 degrees",
          elaborative_why_prompt: "Why a straight line?",
          expected_why_rationale: "The exterior walk turns halfway.",
        },
      },
    ],
  });
  const blocks = blocksForUnit(unit);
  assert.equal(blocks[0]?.type, "retrieval_check");
  assert.equal(blocks[0]?.data.recall_prompt, "What do the angles add to?");
  const payload = testerPayload(applyUnit(emptyTesterValues(), course({ components: [unit] }), unit), {}, blocks);
  assert.equal(payload.blocks[0]?.data.expected_fact, "180 degrees");
  assert.equal(payload.kc_type, "retrieval_check");
});

test("choosing a unit fills layer 1 from that course and component", () => {
  const picked = course();
  const unit = picked.components[0];
  assert.ok(unit);
  const values = applyUnit(emptyTesterValues(), picked, unit);
  assert.equal(values["Course title"], "Triangles");
  assert.equal(values["Course description"], "See why the angles add up.");
  assert.equal(values.Audience, "12-14");
  assert.equal(values.Kind, "mastery");
  assert.equal(values["Component title"], "Angle sum");
  assert.equal(values["Component code"], "angles");
  assert.equal(values["Component description"], "Why a triangle's angles add up.");
  assert.equal(values.Type, "case_study");
  assert.equal(values["Core truth"], "The angles add to 180.");
  assert.equal(values["Rubric lines"], "States 180.");
  assert.equal(values.Misconceptions, "They add to 90. -> right-angle");
  assert.equal(values["Prerequisite codes"], "lines");
  assert.equal(values["Encompass codes"], "polygons");
  assert.equal(values["Transfer case"], "a quadrilateral");
  assert.equal(values.Counterfactual, "");
  assert.equal(values["Prerequisite status"], "lines: unknown");
  assert.equal(coursePosition(picked, "unit-1"), "1 of 2; previous: none; next: Exterior angle");
  assert.equal(values["Course position"], "1 of 2; previous: none; next: Exterior angle");
  assert.equal(values["Choice widget"], "yes");
  assert.equal(values.Persona, DEFAULT_TUTOR_PROFILE.persona);
  assert.equal(values["Unit close"], "no");
  const second = picked.components[1];
  assert.ok(second);
  assert.equal(choiceForMove("retrieval_check", 1), "no");
  assert.equal(choiceForMove("mcq", 1), "yes");
  assert.equal(choiceForMove("case_study", 1), "yes");
  assert.equal(coursePosition(picked, "patch-1"), "Patch");
  assert.equal(prerequisiteStatus(["lines", ""]), "lines: unknown");
});

function child(overrides: Partial<Student> = {}): Student {
  return {
    id: "child-1",
    slug: "ada",
    display_name: "Ada",
    age: 11,
    age_band: "9-11",
    reading_level: "middle-grade",
    modality: "visual",
    interests: ["kites", "maps"],
    tutor_persona: "curious-co-explorer",
    tutor_lexicon: "middle-grade-vivid",
    tutor_metaphors: "playground-sports",
    tutor_sidekick: "bumbling-partner",
    tutor_socratic_strictness: "balanced",
    tutor_struggle_window: "minimum",
    tutor_anti_spoiler: true,
    tutor_pacing: "short-turns-one-question",
    ...overrides,
  };
}

test("choosing a child fills the layer 2 settings and leaves session fields", () => {
  const values = emptyTesterValues();
  values["Course title"] = "Triangles";
  values.Persona = "tactical-coach";
  values["Attempts on this move"] = "2";
  values["Hint tier already given"] = "scaffold";
  values["Component status"] = "fragile";
  values.Stability = "0.4";
  values["Last answer"] = "90 degrees";
  values["Last misconception"] = "right angle";
  values["Minutes used"] = "6";
  values["Support band"] = "stretch";
  const filled = applyChild(values, child());
  assert.equal(filled["Display name"], "Ada");
  assert.equal(filled.Age, "11");
  assert.equal(filled["Grade band"], "middle_school");
  assert.equal(filled["Reading level"], "middle-grade");
  assert.equal(filled["Response length"], "balanced");
  assert.equal(filled["Expression style"], "short_phrases");
  assert.equal(filled["Explanation style"], "visual_spatial");
  assert.equal(filled.Modality, "visual");
  assert.equal(filled["Challenge appetite"], "steady");
  assert.equal(filled["Communication tone"], "warm_and_encouraging");
  assert.equal(filled["Learning support"], "none");
  assert.equal(filled["Interest tags"], "");
  assert.equal(filled.Interests, "kites, maps");
  assert.equal(filled["Course title"], "Triangles");
  assert.equal(filled.Persona, "tactical-coach");
  assert.equal(filled["Attempts on this move"], "2");
  assert.equal(filled["Hint tier already given"], "scaffold");
  assert.equal(filled["Component status"], "fragile");
  assert.equal(filled.Stability, "0.4");
  assert.equal(filled["Last answer"], "90 degrees");
  assert.equal(filled["Last misconception"], "right angle");
  assert.equal(filled["Minutes used"], "6");
  assert.equal(filled["Support band"], "stretch");
  const blank = applyChild(values, child({ age: null, reading_level: "", modality: "", interests: [] }));
  assert.equal(blank.Age, "");
  assert.equal(blank["Reading level"], "");
  assert.equal(blank.Modality, "");
  assert.equal(blank.Interests, "");
  assert.equal(blank["Attempts on this move"], "2");
  filled.Age = "15";
  filled["Display name"] = "Edited";
  const body = testerPayload(filled);
  assert.equal(body.age, 15);
  assert.equal(body.display_name, "Edited");
  assert.equal(body.reading_level, "middle-grade");
  assert.deepEqual(body.interests, ["kites", "maps"]);
  assert.equal(body.attempts, 2);
  assert.equal(body.support_band, "stretch");
});

test("the payload keeps an edited instructive level and unit close", () => {
  const values = emptyTesterValues();
  values.Instructive = "5";
  values["Unit close"] = "yes";
  values["Rubric lines"] = "States 180.\nNames the triangle.";
  values.Misconceptions = "They add to 90. -> right-angle";
  values.Interests = "kites, maps";
  const body = testerPayload(values);
  assert.equal(body.instructive, 5);
  assert.equal(body.unit_close, "yes");
  assert.deepEqual(body.rubric, ["States 180.", "Names the triangle."]);
  assert.deepEqual(body.misconceptions, [{ wrong_move: "They add to 90.", broken_kc: "right-angle" }]);
  assert.deepEqual(body.interests, ["kites", "maps"]);
  const shown = applyResult(values, {
    system_prompt: "prompt",
    move_name: "Retrieve",
    evidence: "fact",
    effective_struggle_window: "minimum (1 tries)",
    effective_enrichment: "direct",
    asks_why: "no",
  });
  assert.equal(shown["Move name"], "Retrieve");
  assert.equal(shown["Effective struggle window"], "minimum (1 tries)");
  assert.equal(shown["Effective enrichment"], "direct");
  assert.equal(shown["Asks why"], "no");
  assert.equal(isReadOnly("Effective struggle window"), true);
});

test("the page posts to the read-only route and the menu link is the tester", () => {
  const page = readFileSync(new URL("../app/kc-prompt-tester/page.tsx", import.meta.url), "utf8");
  const component = readFileSync(new URL("../components/KcPromptTester.tsx", import.meta.url), "utf8");
  assert.match(page, /\/kc\/courses/);
  assert.match(page, /\/students/);
  assert.doesNotMatch(page, /\/kc\/tutor\/courses/);
  assert.match(component, /LAYER_HEADINGS\.map/);
  assert.match(component, /aria-label="Child"/);
  assert.match(component, /applyChild/);
  assert.match(component, /<output/);
  assert.match(component, /\/kc\/prompt-tester/);
  assert.match(component, /field\.kind === "Derived"/);
});
