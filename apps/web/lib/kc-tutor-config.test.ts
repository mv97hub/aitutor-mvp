import assert from "node:assert/strict";
import test from "node:test";

import { BLOCK_TYPES } from "./kc-blocks.ts";
import { BLOCK_CONFIG_FIELDS, DEFAULT_KC_TUTOR_CONFIG, kcTutorConfigFrom, OVERARCHING_FIELDS } from "./kc-tutor-config.ts";

test("defaults cover overarching settings and all ten block types", () => {
  assert.equal(OVERARCHING_FIELDS.length, 8);
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.overarching.orient_framing, "elaborate_outline");
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.overarching.instructional_stance, "guided_discovery");
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.overarching.scaffolding_escalation, "progressive_nudge_then_scaffold");
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.overarching.prerequisite_support_policy, "inline_micro_recap");
  assert.deepEqual(Object.keys(DEFAULT_KC_TUTOR_CONFIG.blocks), [...BLOCK_TYPES]);
  for (const type of BLOCK_TYPES) {
    for (const field of BLOCK_CONFIG_FIELDS[type]) {
      assert.ok(field.key in DEFAULT_KC_TUTOR_CONFIG.blocks[type], `${type}.${field.key}`);
    }
  }
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.curiosity.counts_toward_mastery_score, false);
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.explanation.explanation_depth, 4);
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.explanation.allow_depth_override_student_length, true);
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.explanation.elaboration_style_on_question, "fresh_analogy_and_example");
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.explanation.check_in_prompt_style, "questions_or_elaborate");
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.explanation.end_of_block_summary_style, "bulleted_recap_with_takeaway");
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.explanation.counts_toward_mastery_score, false);
});

test("a saved override is kept and an invalid value falls back", () => {
  const config = kcTutorConfigFrom({
    overarching: {
      stay_on_course: "strict",
      orient_framing: "nope",
      encouragement_style: "brief_confirm",
      close_summary_depth: "elaborate_strengths_and_weaknesses",
    },
    blocks: { mcq: { max_retry_attempts: 4, confirm_why_on_correct: "always" } },
  });
  assert.equal(config.overarching.stay_on_course, "strict");
  assert.equal(config.overarching.orient_framing, "elaborate_outline");
  assert.equal(config.overarching.encouragement_style, "matter_of_fact_confirm");
  assert.equal(config.overarching.close_summary_depth, "diagnostic_strengths_and_gaps");
  assert.equal(config.blocks.mcq.max_retry_attempts, 4);
  assert.equal(config.blocks.mcq.confirm_why_on_correct, "always");
  assert.equal(config.blocks.teach_back.follow_up_questions_count, 1);
});
