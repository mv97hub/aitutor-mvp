import assert from "node:assert/strict";
import test from "node:test";

import { CONTINUE_LABEL, EMPTY_INNER, MOVE_ON_LABEL, childPrompt, childPromptText, heldBelief, holdQuit, nudgeAllowed, nudgeTurn, pickMove, previewLines, quitLine, tutorAsksForWork, updateInner } from "./harness-policy.ts";

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

test("wrong multiple-choice picks are not always the first wrong option", () => {
  const texts = new Set<string>();
  for (let seed = 0; seed < 40; seed += 1) {
    const move = pickMove({
      traits: { ...middle, prior_knowledge: 1 },
      inner: EMPTY_INNER,
      seed,
      turn: 0,
      actions: {
        canType: false,
        buttons: [],
        choices: [
          { id: "a", text: "Right", correct: true },
          { id: "b", text: "First wrong", correct: false },
          { id: "c", text: "Second wrong", correct: false },
        ],
      },
      mode: "rule",
    });
    if (move.intent === "wrong_choice") texts.add(move.text);
  }
  assert.ok(texts.has("First wrong"));
  assert.ok(texts.has("Second wrong"));
});

test("a quiet child answers in a plain statement", () => {
  const description = "Quiet, capable 11-year-old who answers in plain statements and does not ask questions, stall, or play dumb.";
  const prompt = childPrompt({
    description,
    traits: middle,
    intent: "answer_right",
    expected: "The river is blue.",
    lastTutor: "What color is the river?",
  });
  assert.match(prompt, /plain statement/i);
  assert.match(prompt, /Do not ask a question/);
  assert.match(prompt, /stall, or play dumb/);
  const intents = new Set<string>();
  for (let seed = 0; seed < 20; seed += 1) {
    const move = pickMove({
      traits: middle,
      inner: EMPTY_INNER,
      seed,
      turn: seed % 5,
      actions: { canType: true, buttons: [], choices: [] },
      mode: "rule",
      description,
      answerKey: { expected: "The river is blue." },
      lastTutor: "What color is the river?",
    });
    intents.add(move.intent);
    assert.equal(move.intent, "answer_right");
    assert.equal(move.needsModel, true);
  }
  assert.equal(intents.has("on_topic_question"), false);
  assert.equal(intents.has("idk"), false);
  assert.equal(intents.has("say_yes"), false);
  assert.equal(intents.has("answer_part"), false);
  const choice = pickMove({
    traits: { ...middle, prior_knowledge: 1 },
    inner: EMPTY_INNER,
    seed: 3,
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
    description,
  });
  assert.equal(choice.intent, "answer_right");
  assert.equal(choice.text, "Up");
  assert.equal(choice.needsModel, false);
});

test("one wrong belief has to fit the question", () => {
  const description =
    "Age 12. Holds one wrong belief: a price rise means everyone has more money. Wrong answers are a real attempt at the question, not gibberish or a topic change.";
  assert.equal(heldBelief(description), "a price rise means everyone has more money");
  const prompt = childPrompt({
    description,
    traits: middle,
    intent: "answer_wrong",
    wrongMove: "a stored misconception that does not fit",
    lastTutor: "Why did the price of bread go up?",
  });
  assert.match(prompt, /Answer the question the tutor just asked/);
  assert.match(prompt, /real try at that question/);
  assert.match(prompt, /Do not change the subject or send gibberish/);
  assert.match(prompt, /price rise means everyone has more money/);
  assert.doesNotMatch(prompt, /stored misconception/);
  const texts = new Set<string>();
  for (let seed = 0; seed < 20; seed += 1) {
    const typed = pickMove({
      traits: { ...middle, prior_knowledge: 5, curiosity: 5, tangent: 5 },
      inner: EMPTY_INNER,
      seed,
      turn: seed % 5,
      actions: { canType: true, buttons: [], choices: [] },
      mode: "rule",
      description,
      lastTutor: "Why did the price of bread go up?",
    });
    assert.equal(typed.intent, "answer_wrong");
    assert.equal(typed.needsModel, true);
    const choice = pickMove({
      traits: { ...middle, prior_knowledge: 5 },
      inner: EMPTY_INNER,
      seed,
      turn: 0,
      actions: {
        canType: false,
        buttons: [],
        choices: [
          { id: "a", text: "Right", correct: true },
          { id: "b", text: "First wrong", correct: false },
          { id: "c", text: "Second wrong", correct: false },
        ],
      },
      mode: "rule",
      description,
    });
    assert.equal(choice.intent, "wrong_choice");
    assert.equal(choice.needsModel, false);
    texts.add(choice.text);
  }
  assert.ok(texts.has("First wrong"));
  assert.ok(texts.has("Second wrong"));
  assert.equal(texts.has("Right"), false);
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
  const once = pickMove({
    traits: { ...middle, quit: 1 },
    inner: { boredom: 100, frustration: 0, confusion: 0, hints: 0, strain: 0 },
    seed: 1,
    turn: 0,
    actions: { canType: true, buttons: [], choices: [] },
    mode: "rule",
    lastTutor: "What color is the river?",
  });
  assert.notEqual(once.intent, "quit");
  const early = pickMove({
    traits: { ...middle, quit: 1 },
    inner: { boredom: 100, frustration: 0, confusion: 0, hints: 0, strain: 2 },
    seed: 1,
    turn: 1,
    actions: { canType: true, buttons: [], choices: [] },
    mode: "rule",
    lastTutor: "What color is the river?",
  });
  assert.notEqual(early.intent, "quit");
  const quit = pickMove({
    traits: { ...middle, quit: 1 },
    inner: { boredom: 100, frustration: 0, confusion: 0, hints: 0, strain: 3 },
    seed: 1,
    turn: 2,
    actions: { canType: true, buttons: [], choices: [] },
    mode: "rule",
    lastTutor: "What color is the river?",
  });
  assert.equal(quit.intent, "quit");
  assert.ok(quitLine({ quit: 1 }) >= 80);
  assert.ok(quitLine({ quit: 1 }) <= 100);
  const offered = pickMove({
    traits: { ...middle, quit: 1 },
    inner: { boredom: 100, frustration: 100, confusion: 0, hints: 0, strain: 4 },
    seed: 1,
    turn: 2,
    actions: { canType: true, buttons: [MOVE_ON_LABEL, "Tell me more"], choices: [] },
    mode: "rule",
    lastTutor: "Do you want to move on?",
  });
  assert.equal(offered.intent, "move_on");
  assert.equal(offered.text, MOVE_ON_LABEL);
  const asked = pickMove({
    traits: { ...middle, quit: 1 },
    inner: { boredom: 100, frustration: 100, confusion: 0, hints: 0, strain: 4 },
    seed: 1,
    turn: 3,
    actions: { canType: true, buttons: [CONTINUE_LABEL], choices: [] },
    mode: "rule",
    lastTutor: "Do you want to move on?",
  });
  assert.notEqual(asked.intent, "quit");
  assert.equal(asked.text, CONTINUE_LABEL);
});

test("a normal lesson does not bore a child into quitting", () => {
  let inner = { ...EMPTY_INNER };
  const traits = { ...middle, attention: 3, boredom: 3, quit: 3 };
  const lengths = [274, 382, 309, 195, 426, 348, 233];
  const places = ["explain", "explain", "explain", "main", "main", "main", "main"];
  let previous = "";
  for (let turn = 0; turn < lengths.length; turn += 1) {
    const place = places[turn];
    inner = updateInner(inner, {
      traits,
      tutorMessage: "x".repeat(lengths[turn]),
      samePlace: previous !== "" && previous === place,
      wrong: false,
      usedInterest: false,
    });
    const move = pickMove({
      traits,
      inner,
      seed: 1,
      turn,
      actions: { canType: true, buttons: turn === 3 ? [MOVE_ON_LABEL, "Tell me more"] : [], choices: [] },
      mode: "rule",
      lastTutor: "What happened next?",
    });
    assert.notEqual(move.intent, "quit");
    inner = { ...inner, strain: move.inner.strain };
    previous = place;
  }
  assert.ok(inner.boredom < 30, `boredom climbed to ${inner.boredom}`);
});

test("a very long reply adds a little boredom, and a normal one does not", () => {
  const traits = { attention: 1, boredom: 5, frustration: 3 };
  const normal = updateInner(EMPTY_INNER, {
    traits,
    tutorMessage: "word ".repeat(40),
    samePlace: true,
    wrong: false,
    usedInterest: false,
  });
  const huge = updateInner(EMPTY_INNER, {
    traits,
    tutorMessage: "word ".repeat(400),
    samePlace: true,
    wrong: false,
    usedInterest: false,
  });
  assert.ok(normal.boredom < 10);
  assert.ok(huge.boredom > normal.boredom);
  assert.ok(huge.boredom < 15);
});

test("the child prompt label follows whether the model was called", () => {
  assert.equal(childPromptText({ child_prompt: "You are the child." }), "You are the child.");
  assert.equal(
    childPromptText({ child_prompt: "", child_tokens: { input_tokens: 0, output_tokens: 0 } }),
    "This turn did not call the child model.",
  );
  assert.equal(
    childPromptText({ child_prompt: "", child_tokens: { input_tokens: 241, output_tokens: 18 } }),
    "The child model was called for this turn, but its prompt was not stored.",
  );
});

test("preview shows five lines", () => {
  const lines = previewLines({ writing: 1, boundary: 5, curiosity: 5 }, "Boundary tester");
  assert.equal(lines.length, 5);
  assert.equal(lines.some((line) => line.includes("tutor")), true);
});

test("a stuck nudge is a short line and never a quit", () => {
  assert.equal(nudgeTurn(2).text, "What's next?");
  assert.equal(nudgeTurn(1).text, "What should we do next?");
  assert.equal(nudgeTurn(2).intent, "nudge");
  assert.equal(nudgeTurn(2).needsModel, false);
  const held = holdQuit({
    intent: "nudge",
    text: "What's next?",
    traits: { ...middle, quit: 5 },
    inner: { ...EMPTY_INNER, boredom: 99, frustration: 99, strain: 9 },
    buttons: [],
    lastTutor: "Let's keep going.",
  });
  assert.equal(held.intent, "nudge");
  assert.equal(held.text, "What's next?");
});

test("a Cuba recall question and a next-move explanation are answered before a nudge", () => {
  const cuba = "What do you remember about why Cuba ended up in the middle?";
  const origins = "The next move is your own short explanation of the origins.";
  assert.equal(tutorAsksForWork(cuba), true);
  assert.equal(tutorAsksForWork(origins), true);
  assert.equal(tutorAsksForWork("Choose the reason Cuba ended up in the middle."), true);
  assert.equal(tutorAsksForWork("Still on explain after the river is blue"), false);
  assert.equal(tutorAsksForWork("Let's keep going."), false);
  assert.equal(nudgeAllowed({ pending: 2, answersGiven: 0, tutor: cuba }), false);
  assert.equal(nudgeAllowed({ pending: 2, answersGiven: 1, tutor: origins }), false);
  assert.equal(nudgeAllowed({ pending: 2, answersGiven: 2, tutor: origins }), true);
  assert.equal(nudgeAllowed({ pending: 2, answersGiven: 0, tutor: "Let's keep going." }), true);
  assert.equal(nudgeAllowed({ pending: 0, answersGiven: 0, tutor: cuba }), false);
  assert.equal(nudgeAllowed({ pending: 2, answersGiven: 0, tutor: "Tell me more.", choices: 2 }), false);
});
