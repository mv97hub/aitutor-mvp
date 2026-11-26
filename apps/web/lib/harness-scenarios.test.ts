import assert from "node:assert/strict";
import test from "node:test";
import { findHarnessScenario, SCENARIO_GROUPS, scenarioMove, type ScenarioInput } from "./harness-scenarios.ts";

const formulaPrompt = "What is the formula for the inflation rate using CPI?";
const base: ScenarioInput = {
  personaNumber: 5, blockType: "retrieval_check", substep: "recall", tutor: formulaPrompt,
  canType: true, buttons: [], choices: [], history: [], blockIndex: 2,
};
const move = (id: string, changes: Partial<ScenarioInput> = {}) => scenarioMove(id, { ...base, ...changes });

test("the menu covers eight paired families and each variant has its own stable identity", () => {
  assert.equal(SCENARIO_GROUPS.length, 8);
  const ids = SCENARIO_GROUPS.flatMap(group => group.variants.map(variant => variant.id));
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(SCENARIO_GROUPS.every(group => group.variants.length > 1 && group.personas.length && group.blockTypes.length));
  assert.ok(ids.every(id => findHarnessScenario(id)?.variant.id === id));
});

test("formula variants hold the question constant, never send on an unrelated topic, and run once per block", () => {
  assert.match(move("cpi-formula-hesitant")!, /^Is it .*divided by the old CPI/);
  assert.match(move("cpi-formula-statement")!, /divided by the old CPI/);
  assert.doesNotMatch(move("cpi-formula-incomplete")!, /divided/);
  const line = move("cpi-formula-statement")!;
  for (const changes of [
    { personaNumber: 14 }, { canType: false }, { tutor: "What is Shakespeare's best-known play?" },
    { tutor: "CPI is a price index. What does CPI stand for?" }, { blockType: "explanation" },
    { substep: "summary_check" }, { history: [{ role: "child", content: line, step: 2 }] },
  ]) assert.equal(move("cpi-formula-statement", changes), undefined);
  assert.equal(move("cpi-formula-statement", {history: [{role: "child", content: line, step: 1}]}), line);
});

test("attachment expression variants and reader support require their own visible task", () => {
  const inference = {personaNumber: 9, blockType: "case_study", substep: "contrast_and_rule",
    tutor: "What can you infer about a child who shows avoidant attachment? Does that mean they don't care?"};
  for (const personaNumber of [9, 10]) {
    for (const id of ["attachment-short", "attachment-fluent", "attachment-wrong"]) assert.ok(move(id, {...inference, personaNumber}));
  }
  assert.equal(move("attachment-short", {...inference, tutor: "Give an example of avoidant behavior."}), undefined);
  const passage = {personaNumber: 2, blockType: "passage_ela", substep: "central_idea",
    tutor: "What is the central idea of the passage?"};
  for (const personaNumber of [2, 8]) {
    const request = move("reread-short", {...passage, personaNumber});
    assert.match(request!, /read the whole passage again/i);
    assert.equal(move("reread-detail", {...passage, personaNumber}), request);
  }
  assert.equal(move("reread-stress", passage), undefined);
  assert.ok(move("reread-stress", {...passage, history: [{role: "assistant", content: "To be, or not to be, that is the question", step: 2}]}));
});

const numeric = "CPI rose from 120 to 132. What was the percentage inflation rate?";
const disclosure = "The inflation rate is the change in CPI divided by the old CPI, times 100.";
const seen = (role: string, content: string, step = 2) => ({role, content, step});

test("an echo requires a full tutor disclosure on this block; a fresh unaided transfer is a separate opportunity", () => {
  const ctx = {personaNumber: 11};
  assert.equal(move("disclosure-verbatim", {...ctx, history: [seen("assistant", "Think about where you started.")]}), undefined);
  assert.equal(move("disclosure-verbatim", {...ctx, history: [seen("assistant", disclosure, 1)]}), undefined);
  for (const id of ["disclosure-verbatim", "disclosure-paraphrase", "disclosure-struggle"]) {
    const reply = move(id, {...ctx, history: [seen("assistant", disclosure)]})!;
    assert.ok(reply);
    assert.equal(reply === disclosure, id === "disclosure-verbatim");
    const solo = {...ctx, blockType: "worked_example", substep: "solo_solve", tutor: numeric, blockIndex: 3};
    assert.equal(move(id, solo), undefined);
    const history = [seen("assistant", disclosure), seen("user", reply)];
    assert.match(move(id, {...solo, history})!, id === "disclosure-struggle" ? /hint/ : /10%/);
    assert.equal(move(id, {...solo, history, tutor: "The answer is 10%. " + numeric}), undefined);
    assert.equal(move(id, {...solo, history: [...history, seen("assistant", "For this change the answer is 10%.", 3)]}), undefined);
  }
});

test("a demonstrated CPI correction precedes either response, and the CPI belief does not contaminate a later literature task", () => {
  const num = {personaNumber: 14, blockType: "worked_example", substep: "solo_solve", tutor: numeric};
  const wrong = move("cpi-belief-revises", num)!;
  assert.equal(wrong, move("cpi-belief-persists", {...num, personaNumber: 13}));
  const history = [seen("assistant", numeric), seen("user", wrong)];
  assert.equal(move("cpi-belief-revises", {...num, history, tutor: "Almost, can you try again?"}), undefined);
  const worked = {...num, history, tutor: "Use 12 divided by 120, which is 10%. What is the rate now?"};
  assert.match(move("cpi-belief-revises", worked)!, /^It rose by 10%/);
  assert.match(move("cpi-belief-persists", worked)!, /still think 12/);
  const literature = {personaNumber: 14, tutor: "Who wrote Romeo and Juliet?", blockIndex: 3};
  assert.equal(move("cpi-belief-persists", literature), undefined);
  assert.equal(move("cpi-belief-persists", {...literature, history}), "William Shakespeare.");
});

test("closing can use only an offered button; repeated short turns can reach a wish to stop", () => {
  const c = {personaNumber: 7, blockType: "explanation", substep: "summary_check", tutor: "Any last questions?"};
  const button = "No final questions — let's continue!";
  assert.equal(move("closing-continue", {...c, buttons: ["Other"]}), undefined);
  assert.equal(move("closing-continue", {...c, buttons: [button], canType: false}), button);
  assert.equal(move("closing-more", c), "Ask me one more question.");
  assert.equal(move("closing-acknowledges", {...c, personaNumber: 3}), "ok");
  assert.equal(move("closing-stops", c), "k");
  assert.equal(move("closing-stops", {...c, history: [seen("assistant", c.tutor), seen("user", "k")]}), "k");
  assert.equal(move("closing-stops", {...c, history: [seen("assistant", c.tutor), seen("user", "k"), seen("user", "k")]}), "Can we stop now?");
});

test("a typed aside returns to ordinary play on re-ask; both cards permit only a displayed option", () => {
  for (const id of ["aside-identity", "aside-interest"]) {
    for (const [blockType, substep] of [["curiosity", "hook_and_predict"], ["spot_the_flaw", "critique"]]) {
      const ctx = {personaNumber: 4, blockType, substep, tutor: "What do you predict?"};
      const line = move(id, ctx)!;
      assert.ok(line);
      assert.equal(move(id, {...ctx, history: [seen("user", line)]}), undefined);
      assert.equal(move(id, {...ctx, canType: false}), undefined);
    }
    const card = {personaNumber: 12, blockType: "mcq", substep: "choice", canType: false};
    assert.equal(move(id, card), undefined);
    assert.equal(move(id, {...card, choices: [{id: "b", text: "The river"}]}), "The river");
  }
});

test("clarification and guess controls use the same numeric item and tie reasoning to the submitted choice", () => {
  const ctx = {personaNumber: 1, blockType: "case_study", substep: "transfer", tutor: numeric};
  assert.equal(move("reason-clarify", ctx), "What does CPI mean?");
  assert.match(move("reason-partial", ctx)!, /12 points/);
  assert.equal(move("reason-partial", {...ctx, tutor: "CPI fell from 132 to 120. What was the inflation rate?"}), undefined);
  const card = {...ctx, canType: false, blockType: "mcq", substep: "choice", choices: [{id: "b", text: "10%"}]};
  assert.equal(move("reason-guess", card), "10%");
  assert.equal(move("reason-sound", {...card, personaNumber: 6}), "10%");
  assert.equal(move("reason-guess", {...card, choices: [{id: "b", text: "12%"}]}), undefined);
  const why = {...ctx, blockType: "mcq", substep: "awaiting_why", tutor: "Why that choice?"};
  assert.equal(move("reason-guess", why), undefined);
  const history = [seen("assistant", numeric), seen("user", "10%\na. 12%\nb. 10%")];
  const guess = move("reason-guess", {...why, history})!;
  const sound = move("reason-sound", {...why, history})!;
  assert.match(guess, /guessed/);
  assert.match(sound, /Dividing by the starting 120/);
  assert.equal(move("reason-guess", {...why, history: [...history, seen("user", guess)]}), sound);
  assert.equal(move("reason-sound", {...why, history: [seen("assistant", numeric), seen("user", "12%")]}), undefined);
  // The real MCQ shows its stem on a card. It need never appear in an assistant message.
  const cardOnly = [seen("assistant", "Choose an option below."), seen("user", "10%\na. 10%\nb. 12%")];
  assert.equal(move("reason-guess", {...why, history: cardOnly}), undefined);
  assert.equal(move("reason-guess", {...why, history: cardOnly, lastScenarioLine: "10%"}), guess);
  assert.equal(move("reason-guess", {...why, history: [...cardOnly, seen("user", guess)], lastScenarioLine: guess}), sound);
});
