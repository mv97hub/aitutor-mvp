import assert from "node:assert/strict";
import test from "node:test";

import {
  defaultSelectedRunIds,
  draftPromptCards,
  recommendationMarkdown,
  recommendationPageSummary,
  skippedRunMessage,
  type DraftMaterials,
} from "./harness-draft.ts";

const GOAL =
  "Goal start: The learner is still on the explanation. Explain this same topic in two or three sentences, from a fresh angle. Ask no question.";

function explanatoryPrompt(): string {
  return ["This turn", "Active step: Block 2 of 6: Explanatory Walkthrough. The child will type.", GOAL].join("\n");
}

function topicPrompt(): string {
  return ["This turn", "Active step: Block 1 of 6: Topic / Goal. The child will type.", GOAL].join("\n");
}

const builder = [
  { symbol: "_GOAL_START_DEEPEN", section: "This turn", function: "_this_turn", source: GOAL, literals: [GOAL] },
];

function sample(): DraftMaterials {
  return {
    run_id: "run-1",
    findings: [
      {
        title: "ignored question on Explanatory Walkthrough",
        tag: "ignored_question",
        block_label: "Explanatory Walkthrough",
        examples: [{ chat_id: "chat-1", turn: 4, block: "Explanatory Walkthrough" }],
      },
      {
        title: "ignored question again",
        tag: "ignored_question",
        block_label: "Explanatory Walkthrough",
        examples: [{ chat_id: "chat-1", turn: 4, block: "Explanatory Walkthrough" }],
      },
      {
        title: "ignored question a third time",
        tag: "ignored_question",
        block_label: "Explanatory Walkthrough",
        examples: [{ chat_id: "chat-1", turn: 4, block: "Explanatory Walkthrough" }],
      },
      {
        title: "too long on the same turn",
        tag: "too_long",
        block_label: "Explanatory Walkthrough",
        examples: [{ chat_id: "chat-1", turn: 4, block: "Explanatory Walkthrough" }],
      },
      {
        title: "AI_Child1 got stuck",
        tag: "stuck",
        block_label: "Topic / Goal",
        nudges: [
          { turn: 9, asked: "What's next?", answered: "Let's keep going.", block_type: "Topic / Goal", block_id: "b1", substep: "explain" },
          { turn: 9, asked: "What's next?", answered: "Let's keep going.", block_type: "Topic / Goal", block_id: "b1", substep: "explain" },
          { turn: 10, asked: "What should we do next?", answered: "We are still here.", block_type: "Topic / Goal", block_id: "b1", substep: "explain" },
        ],
      },
    ],
    examples: [
      {
        chat_id: "chat-1",
        turn: 4,
        run_id: "run-1",
        block_label: "Explanatory Walkthrough",
        block_title: "How a river cuts rock",
        substep: "explain_topic",
        child_text: "What does govern mean?",
        tutor_reply: "The river kept its old name and moved on.",
        tutor_prompt: explanatoryPrompt(),
      },
      {
        chat_id: "chat-1",
        turn: 2,
        run_id: "run-1",
        block_label: "Topic / Goal",
        block_title: "Why Cuba",
        substep: "explain",
        child_text: "Tell me more about Cuba.",
        tutor_reply: "Cuba sat between two powers.",
        tutor_prompt: topicPrompt(),
      },
    ],
    builder,
  };
}

test("the newest few runs start selected", () => {
  assert.deepEqual(defaultSelectedRunIds(["a", "b", "c", "d"]), ["a", "b", "c"]);
  assert.deepEqual(defaultSelectedRunIds(["a"]), ["a"]);
});

test("a failed run is named and the other runs are still drafted", () => {
  const named = skippedRunMessage([{ runId: "11111111-1111-1111-1111-111111111111", message: "Load failed" }]);
  assert.match(named, /11111111-1111-1111-1111-111111111111/);
  assert.match(named, /Load failed/);
  assert.match(named, /other selected runs were still drafted/);
});

test("one observation per turn and fault, with quotes and no replacement wording", () => {
  const materials = sample();
  materials.findings = [
    ...(materials.findings || []),
    {
      title: "stay on the goal step",
      tag: "stuck",
      examples: [{ chat_id: "chat-1", turn: 2, block: "Topic / Goal" }],
    },
  ];
  const cards = draftPromptCards(materials);
  const summary = recommendationPageSummary(cards);
  assert.equal(recommendationMarkdown("run-1", cards), summary);
  assert.equal(/Remove this sentence|Shorter replacement|shorter replacement/i.test(summary), false);
  for (const card of cards) {
    assert.equal(card.evidence.replacement, undefined);
    assert.equal(card.evidence.shorter, undefined);
    assert.equal(card.proposed.text, "");
    assert.equal(card.proposed.shorter, "");
    assert.match(summary, new RegExp(card.evidence.child_text || "missing child"));
    assert.match(summary, new RegExp(card.evidence.tutor_reply || "missing tutor"));
  }
  const keys = cards.map((card) => `${card.evidence.run_id}|${card.evidence.sources?.[0]?.chat_id || ""}|${card.evidence.turn}|${card.evidence.findings?.[0]?.tag}`);
  assert.equal(new Set(keys).size, keys.length);
  const ignored = cards.filter((card) => card.evidence.findings?.[0]?.tag === "ignored_question");
  assert.equal(ignored.length, 1);
  assert.equal(ignored[0].evidence.turn, 4);
  assert.equal(ignored[0].evidence.child_text, "What does govern mean?");
  assert.equal(ignored[0].evidence.tutor_reply, "The river kept its old name and moved on.");
  assert.match(ignored[0].evidence.fault || "", /ignored the child's question/);
  const sameTurn = cards.filter((card) => card.evidence.turn === 4);
  assert.equal(sameTurn.length, 2);
  assert.equal(sameTurn.filter((card) => card.evidence.findings?.[0]?.tag === "too_long").length, 1);
  const goalQuotes = cards.filter((card) => (card.evidence.current || "") === GOAL);
  assert.ok(goalQuotes.length >= 1);
  assert.equal(goalQuotes.every((card) => card.evidence.replacement === undefined), true);
  const mismatch = cards.find((card) => card.evidence.block_type === "Explanatory Walkthrough" && card.evidence.current === GOAL);
  assert.ok(mismatch);
  assert.match(mismatch?.evidence.mismatch || "", /Topic \/ Goal/);
  assert.match(mismatch?.evidence.mismatch || "", /Explanatory Walkthrough/);
  assert.match(mismatch?.evidence.mismatch || "", /do not match/);
  assert.match(summary, /This line is for Topic \/ Goal/);
  assert.match(summary, /not a line to change/);
  const goalTurn = cards.find((card) => card.evidence.turn === 2);
  assert.equal(goalTurn?.evidence.block_type, "Topic / Goal");
  assert.equal(goalTurn?.evidence.current, GOAL);
  assert.equal(goalTurn?.evidence.mismatch || "", "");
  const nudges = cards.filter((card) => (card.evidence.nudges || []).length > 0);
  assert.equal(nudges.length, 2);
  assert.match(summary, /What's next\?/);
  assert.match(summary, /Let's keep going/);
  assert.match(summary, /What should we do next\?/);
  assert.match(summary, /did not move/);
  assert.match(summary, /Runs: 1/);
  assert.match(summary, /run-1/);
  assert.match(summary, /Block types: .*Explanatory Walkthrough/);
  assert.match(summary, /Topic \/ Goal/);
  assert.match(summary, /does not change the live tutor prompt/);
  assert.match(summary, /kc_prompt\.py/);
  assert.match(summary, /How a river cuts rock/);
  assert.match(summary, /explain_topic/);
});
