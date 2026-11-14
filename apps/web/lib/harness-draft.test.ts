import assert from "node:assert/strict";
import test from "node:test";

import {
  applyModelReplacements,
  draftPromptCards,
  drafterPrompt,
  type DraftMaterials,
} from "./harness-draft.ts";

const ASIDE =
  "Goal start: The learner typed a side remark. It is not an attempt and it is not a request to learn more. Answer it inside the safety rules, in one or two sentences, then one line back to the active lesson. Do not start a new explanation of this block. Answer that question first, in a sentence or two, then one line back to the active lesson. Do not ask the goal question. It does not mean ignore the question they typed.";
const DEEPEN =
  "Goal start: The learner wants to keep learning. Explain this same topic more deeply, from a fresh angle. Write it as teaching, not a question. Do not ask the goal question. Do not ask any question.";
const HINT =
  "When the learner is stuck, start with a nudge, then an analogy, then a scaffold, and reveal the goal only after those hints.";
const TEACH_DUP =
  "Do not start a new explanation of this block. Answer the side remark in one or two sentences, then one line back to the active lesson.";

function prompt(turn: string): string {
  return [
    "This turn",
    "Active step: Block 1 of 6: Topic / Goal. The child will type.",
    turn,
    "",
    "How to teach",
    HINT,
    TEACH_DUP,
  ].join("\n");
}

const materials: DraftMaterials = {
  run_id: "run-1",
  findings: [
    { title: "AI_Child1 got stuck", tag: "stuck", block_label: "Topic / Goal", cause_class: "prompt", count: 1 },
    { title: "one question was not in the prompt", tag: "one_question", block_label: "an unknown block", cause_class: "prompt", count: 0 },
    { title: "stay on course was not in the prompt", tag: "stay_on_course", block_label: "an unknown block", cause_class: "prompt", count: 0 },
    {
      title: "repeated itself",
      tag: "repeated_itself",
      block_label: "Topic / Goal",
      cause_class: "setting",
      count: 3,
      examples: [{ chat_id: "chat-1", turn: 4, block: "Topic / Goal" }],
    },
    {
      title: "ignored question",
      tag: "ignored_question",
      block_label: "Topic / Goal",
      cause_class: "loop",
      count: 2,
      examples: [{ chat_id: "chat-1", turn: 2, block: "Topic / Goal" }],
    },
  ],
  examples: [
    { chat_id: "chat-1", turn: 1, tutor_prompt: prompt(DEEPEN), block_label: "Topic / Goal", sections: { "This turn": DEEPEN, "How to teach": `${HINT}\n${TEACH_DUP}` } },
    { chat_id: "chat-1", turn: 2, child_text: "What does govern mean?", tutor_prompt: prompt(ASIDE), block_label: "Topic / Goal", sections: { "This turn": ASIDE, "How to teach": `${HINT}\n${TEACH_DUP}` } },
    { chat_id: "chat-1", turn: 4, tutor_prompt: prompt(ASIDE), block_label: "Topic / Goal", sections: { "This turn": ASIDE, "How to teach": `${HINT}\n${TEACH_DUP}` } },
  ],
  builder: [
    { symbol: "_GOAL_START_DEEPEN", section: "This turn", function: "_this_turn", source: DEEPEN, literals: [DEEPEN] },
    { symbol: "_GOAL_START_ASIDE", section: "This turn", function: "_this_turn", source: ASIDE, literals: [ASIDE] },
    { symbol: "_block_config_rules", section: "How to teach", function: "_block_config_rules", source: HINT, literals: [HINT] },
    { symbol: "_how_to_teach", section: "How to teach", function: "_how_to_teach", source: TEACH_DUP, literals: [TEACH_DUP] },
  ],
};

test("drafted cards quote the stored prompt and name the function", () => {
  const cards = draftPromptCards(materials);
  const stored = (materials.examples || []).map((item) => item.tutor_prompt).join("\n");
  assert.ok(cards.length >= 5);
  for (const card of cards) {
    assert.ok(card.evidence.section);
    assert.ok(card.evidence.function);
    assert.ok(card.evidence.current);
    assert.ok(stored.includes(card.evidence.current || ""));
    assert.ok(card.evidence.replacement);
    assert.ok(card.evidence.shorter);
    assert.ok(card.proposed.shorter);
    assert.equal(card.prompt_direction, "shorter");
  }
  const stuck = cards.find((card) => card.evidence.summary?.includes("got stuck"));
  assert.match(stuck?.evidence.current || "", /more deeply/);
  assert.equal(stuck?.evidence.function, "_this_turn");
  assert.equal(stuck?.evidence.section, "This turn");
  const question = cards.find((card) => card.evidence.summary?.includes("one question"));
  assert.match(question?.evidence.current || "", /Do not ask any question/);
  assert.match(question?.evidence.replacement || "", /One question/);
  assert.equal(question?.evidence.block_type, "Topic / Goal");
  const repeated = cards.find((card) => card.evidence.summary?.includes("repeated"));
  assert.match(repeated?.evidence.current || "", /nudge/);
  assert.equal(repeated?.kind, "remove");
  assert.ok(cards.some((card) => card.kind === "remove"));
  const prompt = drafterPrompt(materials, cards);
  assert.match(prompt, /_this_turn/);
  assert.match(prompt, /more deeply/);
  assert.match(prompt, /What does govern mean/);
});

test("a model replacement is kept only when it quotes the stored sentence and is shorter", () => {
  const cards = draftPromptCards(materials);
  const current = cards[0].evidence.current || "";
  const kept = applyModelReplacements(cards, [
    { current_quote: "a sentence the tutor never saw", replacement: "Ignore the child.", shorter: "Remove this sentence." },
    { current_quote: current, replacement: current + " Add another paragraph of rules.", shorter: "Remove this sentence." },
    { current_quote: current, replacement: "Two sentences, then stop.", shorter: "Remove this sentence." },
  ]);
  assert.equal(kept[0].evidence.replacement, "Two sentences, then stop.");
  assert.equal(kept[0].evidence.current, current);
  const other = cards.find((card) => card.evidence.current !== current);
  assert.ok(other);
  const keptOther = kept.find((card) => card.title === other?.title);
  assert.equal(keptOther?.evidence.replacement, other?.evidence.replacement);
});
