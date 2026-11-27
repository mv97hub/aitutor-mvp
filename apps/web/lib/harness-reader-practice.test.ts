import assert from "node:assert/strict";
import test from "node:test";

import { CARGO_ANSWER, EXAMPLE_REQUEST, READER_PRACTICE, readerPracticeChecks, readerPracticePlan, type PracticeTurn } from "./harness-reader-practice.ts";
import { scenarioMove } from "./harness-scenarios.ts";

test("the operator preset resolves only the ready River roads fixture and the actual six-year-old", () => {
  const river = {id: "river", code: "harness-scenario-river"};
  const fixture = {id: "fixture", code: "harness-profile-scenarios", ready: true, components: [river]};
  const children = [{number: 8, id: "avid"}, {number: 2, id: "reader"}];
  const imitation = {...fixture, id: "other-course", code: "lookalike"};
  const selected = readerPracticePlan([imitation, fixture], children);
  assert.deepEqual(selected, {
    scenario: READER_PRACTICE, behavior: "script", persona_ids: ["reader"], course_ids: ["fixture"],
    component_ids: ["river"], iterations: 1, turn_limit: 2, tutor_models: ["gpt-4.1-mini"], tutor_profile_ids: [],
  });
  assert.equal(readerPracticePlan([{...fixture, ready: false}], children), undefined);
  assert.equal(readerPracticePlan([imitation], children), undefined);
  assert.equal(readerPracticePlan([{...fixture, components: []}], children), undefined);
  assert.equal(readerPracticePlan([fixture], [children[0]]), undefined);
});

test("the practice report distinguishes delivered, replayed, counted, changed, missing and unavailable outcomes", () => {
  const turn: PracticeTurn = {
    child_text: EXAMPLE_REQUEST,
    session_before: { scenario_exercised: true, substep: "central_idea", block_id: "river" },
    session_after: { delivery_status: "delivered", substep: "central_idea", block_id: "river",
      loop_result: { stayed: true, attempt_counted: false } },
  };
  const ok = "Central-idea question open · zero attempts used";
  const answer = {...turn, child_text: CARGO_ANSWER};
  assert.deepEqual(readerPracticeChecks([turn, answer]), [ok, ok]);
  assert.deepEqual(readerPracticeChecks([turn, {...answer, session_after: {...answer.session_after, delivery_status: "recovered"}}]), [ok, ok]);
  assert.deepEqual(readerPracticeChecks([turn]), [ok, "Not exercised"]);
  assert.deepEqual(readerPracticeChecks([{...turn, session_before: {scenario_exercised: false}}]), ["Not exercised", "Not exercised"]);
  assert.deepEqual(readerPracticeChecks([{...turn, session_after: {...turn.session_after, loop_result: {stayed: true, attempt_counted: true}}}, answer]), ["An assessment attempt was counted", ok]);
  assert.deepEqual(readerPracticeChecks([turn, {...answer, session_after: {...answer.session_after, substep: "cite_evidence"}}]), [ok, "Reading question changed"]);
  assert.deepEqual(readerPracticeChecks([turn, {...answer, session_after: {...answer.session_after, delivery_status: "unknown"}}]), [ok, "Outcome unavailable"]);
});

test("the script needs visible River roads and never treats an unrelated question as a cargo prompt", () => {
  const river = {personaNumber: 2, blockType: "passage_ela", substep: "central_idea", tutor: "What is the central idea of the passage?",
    passage: "Rivers carry fresh water from the hills to the sea.", canType: true, buttons: [], choices: [], history: []};
  assert.equal(scenarioMove(READER_PRACTICE, river), EXAMPLE_REQUEST);
  for (const changes of [{personaNumber: 8}, {passage: "To be, or not to be."}, {canType: false}, {substep: "cite_evidence"}]) {
    assert.equal(scenarioMove(READER_PRACTICE, {...river, ...changes}), undefined);
  }
  for (const tutor of ["Apples go to town. What did the boat carry?", "It carried pears. What else could a boat carry?",
    "What could the boat carry? Now, why do people live by rivers?"]) {
    assert.equal(scenarioMove(READER_PRACTICE, {...river, tutor, lastScenarioLine: EXAMPLE_REQUEST}), undefined);
  }
  assert.match(scenarioMove("reread-short", river)!, /read the whole passage again/);
});
