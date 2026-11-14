import assert from "node:assert/strict";
import test from "node:test";

import {
  applyModelReplacements,
  defaultSelectedRunIds,
  draftPromptCards,
  drafterPrompt,
  recommendationMarkdown,
  recommendationPageSummary,
  skippedRunMessage,
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
    {
      title: "AI_Child1 got stuck",
      tag: "stuck",
      block_label: "Topic / Goal",
      cause_class: "prompt",
      count: 1,
      nudges: [
        { turn: 9, asked: "What's next?", answered: "Let's keep going.", block_type: "Topic / Goal", block_id: "b1", substep: "explain" },
        { turn: 10, asked: "What should we do next?", answered: "We are still here.", block_type: "Topic / Goal", block_id: "b1", substep: "explain" },
      ],
    },
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
  assert.equal(stuck?.evidence.block_type, "Topic / Goal");
  assert.match(stuck?.evidence.summary || "", /What's next\?/);
  assert.match(stuck?.evidence.summary || "", /What should we do next\?/);
  assert.match(stuck?.evidence.summary || "", /Let's keep going/);
  assert.match(stuck?.evidence.summary || "", /We are still here/);
  assert.match(stuck?.evidence.summary || "", /did not move/);
  assert.equal(stuck?.evidence.nudges?.length, 2);
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

test("the newest few runs start selected", () => {
  assert.deepEqual(defaultSelectedRunIds(["a", "b", "c", "d"]), ["a", "b", "c"]);
  assert.deepEqual(defaultSelectedRunIds(["a"]), ["a"]);
});

test("a failed run is named and the other runs still draft one card per theme", () => {
  const named = skippedRunMessage([
    { runId: "11111111-1111-1111-1111-111111111111", message: "Load failed" },
  ]);
  assert.match(named, /11111111-1111-1111-1111-111111111111/);
  assert.match(named, /Load failed/);
  assert.match(named, /other selected runs were still drafted/);
  const quiet: DraftMaterials = {
    run_id: "run-quiet",
    findings: [
      {
        title: "quiet finding",
        tag: "quiet_only",
        block_label: "Topic / Goal",
        examples: [{ chat_id: "quiet", turn: 3, block: "Topic / Goal" }],
      },
    ],
    examples: [{ chat_id: "quiet", turn: 3, run_id: "run-quiet", tutor_prompt: "No builder sentence is in this prompt.", block_label: "Topic / Goal" }],
    builder: materials.builder,
  };
  const second: DraftMaterials = {
    run_id: "run-b",
    findings: [
      {
        title: "AI_Child2 got stuck",
        tag: "stuck",
        block_label: "Topic / Goal",
        cause_class: "prompt",
        examples: [{ chat_id: "chat-2", turn: 11, block: "Topic / Goal" }],
        nudges: [
          { turn: 11, asked: "And then?", answered: "Same step.", block_type: "Topic / Goal", block_id: "b1", substep: "explain" },
          { turn: 12, asked: "Now what?", answered: "Still explain.", block_type: "Topic / Goal", block_id: "b1", substep: "explain" },
        ],
      },
    ],
    examples: (materials.examples || []).map((example) => ({ ...example, chat_id: "chat-2", run_id: "run-b" })),
    builder: materials.builder,
  };
  const cards = draftPromptCards({ runs: [{ ...materials, run_id: "run-a" }, second, quiet] });
  const stuckCards = cards.filter((card) => card.evidence.summary?.includes("got stuck"));
  assert.equal(stuckCards.length, 1);
  const stuck = stuckCards[0];
  assert.equal(stuck.evidence.block_type, "Topic / Goal");
  assert.equal(stuck.evidence.section, "This turn");
  assert.equal(stuck.evidence.function, "_this_turn");
  assert.match(stuck.evidence.current || "", /more deeply/);
  assert.ok(stuck.evidence.replacement);
  assert.ok((stuck.evidence.replacement || "").length < (stuck.evidence.current || "").length);
  const sources = stuck.evidence.sources || [];
  assert.ok(sources.some((source) => source.run_id === "run-a"));
  assert.ok(sources.some((source) => source.run_id === "run-b" && source.turn === 11 && source.block_type === "Topic / Goal"));
  assert.match(stuck.evidence.summary || "", /What's next\?/);
  assert.match(stuck.evidence.summary || "", /Let's keep going/);
  assert.match(stuck.evidence.summary || "", /And then\?/);
  assert.match(stuck.evidence.summary || "", /Same step/);
  assert.match(stuck.evidence.summary || "", /did not move/);
  assert.equal(stuck.evidence.nudges?.length, 4);
  assert.equal(cards.some((card) => card.evidence.summary?.includes("quiet finding")), false);
  const markdown = recommendationMarkdown("run-a,run-b", cards);
  assert.match(markdown, /run-a/);
  assert.match(markdown, /run-b/);
  assert.match(markdown, /turn 11/);
});

test("the page summary is plain text for a later run and keeps stuck nudges", () => {
  const text = recommendationPageSummary([
    {
      title: "Topic / Goal: Shorten This turn for stuck",
      evidence: {
        section: "This turn",
        function: "_this_turn",
        current: "Explain this same topic more deeply.",
        shorter: "Explain this topic in two sentences, then stop.",
        block_type: "Topic / Goal",
        sources: [{ run_id: "run-a", turn: 9, block_type: "Topic / Goal" }],
        nudges: [
          {
            turn: 9,
            asked: "What's next?",
            answered: "Let's keep going.",
            block_type: "Topic / Goal",
            block_id: "b1",
            substep: "explain",
          },
        ],
      },
    },
    {
      title: "one question",
      evidence: {
        section: "How to teach",
        function: "_how_to_teach",
        current: "Do not ask any question.",
        shorter: "Ask no question.",
        block_type: "Topic / Goal",
        sources: [{ run_id: "run-b", turn: 2, block_type: "Topic / Goal" }],
      },
    },
  ]);
  assert.match(text, /later Cursor run/);
  assert.match(text, /does not change the live tutor prompt/);
  assert.match(text, /kc_prompt\.py/);
  assert.match(text, /Theme 1: Topic \/ Goal: Shorten This turn for stuck/);
  assert.match(text, /Section: This turn/);
  assert.match(text, /Function: _this_turn/);
  assert.match(text, /Quoted stored line: Explain this same topic more deeply\./);
  assert.match(text, /Shorter replacement: Explain this topic in two sentences, then stop\./);
  assert.match(text, /block type Topic \/ Goal/);
  assert.match(text, /Run run-a/);
  assert.match(text, /Turn 9/);
  assert.match(text, /the child asked "What's next\?"/);
  assert.match(text, /The tutor answered "Let's keep going\."/);
  assert.match(text, /did not move/);
  assert.match(text, /Theme 2: one question/);
  assert.match(text, /Run run-b/);
  assert.match(text, /Turn 2/);
  const second = text.split("Theme 2:")[1] || "";
  assert.equal(second.includes("did not move"), false);
});
