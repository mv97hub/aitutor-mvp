import assert from "node:assert/strict";
import test from "node:test";

import { BLOCK_TYPES } from "./kc-blocks.ts";
import { BLOCK_CONFIG_FIELDS, DEFAULT_KC_TUTOR_CONFIG, kcTutorConfigFrom, OVERARCHING_FIELDS } from "./kc-tutor-config.ts";

test("defaults cover overarching settings and all nine block types", () => {
  assert.equal(OVERARCHING_FIELDS.length, 5);
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.overarching.orient_framing, "elaborate_outline");
  assert.deepEqual(Object.keys(DEFAULT_KC_TUTOR_CONFIG.blocks), [...BLOCK_TYPES]);
  for (const type of BLOCK_TYPES) {
    for (const field of BLOCK_CONFIG_FIELDS[type]) {
      assert.ok(field.key in DEFAULT_KC_TUTOR_CONFIG.blocks[type], `${type}.${field.key}`);
    }
  }
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.curiosity.counts_toward_mastery_score, false);
});

test("a saved override is kept and an invalid value falls back", () => {
  const config = kcTutorConfigFrom({
    overarching: { stay_on_course: "strict", orient_framing: "nope" },
    blocks: { mcq: { max_retry_attempts: 4, confirm_why_on_correct: "always" } },
  });
  assert.equal(config.overarching.stay_on_course, "strict");
  assert.equal(config.overarching.orient_framing, "elaborate_outline");
  assert.equal(config.blocks.mcq.max_retry_attempts, 4);
  assert.equal(config.blocks.mcq.confirm_why_on_correct, "always");
  assert.equal(config.blocks.teach_back.follow_up_questions_count, 1);
});
