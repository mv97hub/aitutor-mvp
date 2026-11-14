import assert from "node:assert/strict";
import test from "node:test";

import { EMPTY_INNER, pickMove, previewLines, quitLine, updateInner } from "./harness-policy.ts";

const middle = {
  maturity: 3,
  attention: 3,
  curiosity: 3,
  boredom: 3,
  prior_knowledge: 5,
  learning_rate: 3,
  reading: 3,
  writing: 3,
  compliance: 3,
  tangent: 1,
  when_unsure: 3,
  wrong_pattern: 3,
  frustration: 3,
  buttons: 1,
  echoing: 1,
  boundary: 1,
  quit: 3,
};

test("the same seed repeats the child's intents", () => {
  const input = {
    traits: middle,
    inner: EMPTY_INNER,
    seed: 42,
    actions: { canType: true, buttons: [], choices: [] },
    mode: "rule" as const,
    answerKey: { expected: "The river is blue." },
    lastTutor: "What color is the river?",
  };
  const first = [0, 1, 2, 3, 4].map((turn) => pickMove({ ...input, turn }).intent);
  const second = [0, 1, 2, 3, 4].map((turn) => pickMove({ ...input, turn }).intent);
  assert.deepEqual(first, second);
  assert.equal(first.length, 5);
});

test("a choice card is picked by the harness, and a known child picks the right one", () => {
  const move = pickMove({
    traits: middle,
    inner: EMPTY_INNER,
    seed: 1,
    turn: 0,
    actions: {
      canType: false,
      buttons: [],
      choices: [
        { id: "a", text: "Up", correct: true },
        { id: "b", text: "Down", correct: false },
      ],
    },
    mode: "rule",
  });
  assert.equal(move.intent, "answer_right");
  assert.equal(move.text, "Up");
  assert.equal(move.needsModel, false);
});

test("a scripted line needs no model, and a bored child can quit", () => {
  const scripted = pickMove({
    traits: middle,
    inner: EMPTY_INNER,
    seed: 1,
    turn: 1,
    actions: { canType: true, buttons: [], choices: [] },
    mode: "script",
    script: ["who is pompey", "tell me"],
  });
  assert.equal(scripted.text, "tell me");
  assert.equal(scripted.needsModel, false);
  const quit = pickMove({
    traits: { ...middle, quit: 1 },
    inner: { boredom: 100, frustration: 0, confusion: 0, hints: 0 },
    seed: 1,
    turn: 0,
    actions: { canType: true, buttons: [], choices: [] },
    mode: "rule",
  });
  assert.equal(quit.intent, "quit");
  assert.ok(quitLine({ quit: 1 }) < 100);
});

test("a long tutor message raises boredom for a short attention span", () => {
  const next = updateInner(EMPTY_INNER, {
    traits: { attention: 1, boredom: 5, frustration: 3 },
    tutorMessage: "word ".repeat(200),
    samePlace: true,
    wrong: true,
    usedInterest: false,
  });
  assert.ok(next.boredom > 10);
  assert.ok(next.frustration > 0);
});

test("preview shows five lines", () => {
  const lines = previewLines({ writing: 1, boundary: 5, curiosity: 5 }, "Boundary tester");
  assert.equal(lines.length, 5);
  assert.equal(lines.some((line) => line.includes("tutor")), true);
});
