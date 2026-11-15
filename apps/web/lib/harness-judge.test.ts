import assert from "node:assert/strict";
import test from "node:test";

import { acceptJudgeOutput, agreementLabel, judgePrompt, RUBRIC_VERSION } from "./harness-judge.ts";

const turns = [
  {
    seq: 1,
    intent: "on_topic_question",
    child_text: "What does govern mean?",
    tutor_reply: "Govern means to rule.",
  },
  {
    seq: 2,
    intent: "answer_wrong",
    child_text: "The river is green.",
    tutor_reply: "Not quite. Look at the map again.",
  },
];

test("rubric v2 names 1, 3, and 5 and passes the intent", () => {
  assert.equal(RUBRIC_VERSION, "2");
  const prompt = judgePrompt({ child: "Curious", turns });
  assert.match(prompt, /intent: on_topic_question/);
  assert.match(prompt, /teaching_quality: 1 = does not teach this step/);
  assert.match(prompt, /3 = teaches, with a gap/);
  assert.match(prompt, /5 = teaches the step clearly/);
  assert.match(prompt, /child_realism: 1 =/);
});

test("a score whose quote is not in that turn is dropped", () => {
  const result = acceptJudgeOutput(
    {
      scores: [
        { dimension: "teaching_quality", score: 4, quote: "Govern means to rule.", turn: 1 },
        { dimension: "correctness", score: 2, quote: "soccer fans", turn: 1 },
        { dimension: "engagement", score: 3, quote: "Govern means to rule.", turn: 2 },
      ],
      tags: [],
      child_realism: 4,
    },
    { turns },
  );
  assert.deepEqual(
    result.scores.map((score) => score.dimension),
    ["teaching_quality"],
  );
  assert.equal(result.child_realism, 4);
});

test("an answered side question is not ignored_question", () => {
  const dropped = acceptJudgeOutput(
    {
      scores: [],
      tags: [
        { tag: "ignored_question", turn: 1, quote: "What does govern mean?" },
        { tag: "too_long", turn: 1, quote: "Govern means to rule." },
      ],
      child_realism: 3,
    },
    { turns, checks: { side: [{ turn: 0, answered: true }] } },
  );
  assert.deepEqual(
    dropped.tags.map((tag) => tag.tag),
    ["too_long"],
  );

  const kept = acceptJudgeOutput(
    {
      scores: [],
      tags: [{ tag: "ignored_question", turn: 1, quote: "What does govern mean?" }],
    },
    { turns, checks: { side: [{ turn: 0, answered: false }] } },
  );
  assert.equal(kept.tags.length, 1);
  assert.equal(kept.child_realism, null);
});

test("agreement is empty until a hand score exists, then names the gap", () => {
  assert.equal(agreementLabel(4, 4), "agree");
  assert.equal(agreementLabel(5, 2), "off by 3");
});
