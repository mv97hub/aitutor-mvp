import assert from "node:assert/strict";
import test from "node:test";

import type { KcComponentDraft } from "./kc.ts";
import { creatorBubbleText, draftReplyText } from "./kc-draft-text.ts";

const draft: KcComponentDraft = {
  kind: "component",
  code: "river",
  title: "River fact",
  description: "The river is blue.",
  outline: "How the river looks.",
  topics: [{ topic: "color", goal: "Recall the color" }],
  kc_type: "factual",
  core_truth: "The river is blue.",
  rubric: ["Recall the color"],
  type_fields: { fact: "The river is blue.", retrieval_question: "What color?" },
  misconceptions: [{ wrong_move: "It is red", broken_kc: "zz-other" }],
  prerequisite_codes: ["zz-other"],
  encompasses_codes: [],
  blocks: [
    {
      id: "blk_1",
      type: "topic_goal",
      data: {
        topic: "color",
        goal: "Recall the color",
        acceptance_criteria: "",
        teaching_notes: "Use the banks.",
      },
    },
    {
      id: "blk_2",
      type: "mcq",
      data: {
        mode: "static",
        question_stem: "What color is the river?",
        choices: [
          { id: "a", text: "blue", is_correct: true, distractor_rationale: "", misconception_code: "" },
          {
            id: "b",
            text: "red",
            is_correct: false,
            distractor_rationale: "the banks look red",
            misconception_code: "zz-other",
          },
        ],
        correct_explanation: "It is blue.",
        target_skill: null,
      },
    },
    {
      id: "blk_3",
      type: "socratic",
      data: {
        central_dilemma: "Why is it blue?",
        initial_probe: "What do you think?",
        counterexamples: ["A muddy river", ""],
        target_synthesis: "Depth and sky.",
      },
    },
    {
      id: "blk_4",
      type: "worked_example",
      data: {
        problem_statement: "Name the color",
        steps: [
          { step_text: "Look", rationale: "the water" },
          { step_text: "Name it", rationale: null },
        ],
        faded_step_index: 1,
        solo_problem: "A new river",
        solo_expected_answer: "blue",
      },
    },
  ],
};

const body = [
  "Draft for River fact only. Other components stay as they are.",
  "Description: The river is blue.",
  "Outline: How the river looks.",
  "1. Topic / Goal",
  "Topic: color",
  "Goal: Recall the color",
  "Teaching notes: Use the banks.",
  "2. Multiple Choice Question",
  "Mode: static",
  "Question stem: What color is the river?",
  "Choices:",
  "- a. blue (correct)",
  "- b. red (trap: the banks look red; misconception: zz-other)",
  "Correct explanation: It is blue.",
  "3. Socratic Discussion",
  "Central dilemma: Why is it blue?",
  "Opening probe: What do you think?",
  "Counterexamples: A muddy river",
  "Target synthesis: Depth and sky.",
  "4. Worked Example + Faded Step",
  "Problem statement: Name the color",
  "Steps:",
  "- Look (the water)",
  "- Name it",
  "Faded step: 1",
  "Solo problem: A new river",
  "Solo expected answer: blue",
  "Core truth: The river is blue.",
  "Misconceptions: It is red (zz-other)",
  "Prerequisites: zz-other",
  "Encompasses: none",
  "Nothing is saved until you push it.",
].join("\n");

test("the bubble text lists filled catalog fields and keeps the links", () => {
  assert.equal(draftReplyText(draft), body);
  assert.equal(body.includes("\nTopics:"), false);
  assert.equal(body.includes("\nType:"), false);
  assert.equal(body.includes("Fact:"), false);
  assert.equal(body.includes("Retrieval question:"), false);
});

test("an assistant bubble shows the prose, then the blocks from the draft", () => {
  const stored = [
    "The river looks blue because of the sky.",
    "",
    "Draft for River fact only. Other components stay as they are.",
    "Topics: color (Recall the color)",
    "Type: Factual",
    "Fact: The river is blue.",
  ].join("\n");
  const shown = creatorBubbleText(stored, draft);
  assert.equal(shown, `The river looks blue because of the sky.\n\n${body}`);
  assert.equal(shown.includes("Topics:"), false);
  assert.equal(shown.includes("Fact:"), false);
  assert.equal(shown.indexOf("The river looks blue"), 0);
  assert.ok(shown.indexOf("1. Topic / Goal") > shown.indexOf("The river looks blue"));
});
