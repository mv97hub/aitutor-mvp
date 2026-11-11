import assert from "node:assert/strict";
import test from "node:test";

import { BLOCK_TYPES, blankData } from "./kc-blocks.ts";
import {
  PASSAGE_ELA_DISPLAY_OPTIONS,
  PASSAGE_ELA_EVIDENCE_OPTIONS,
  PASSAGE_ELA_REREAD_OPTIONS,
  PASSAGE_ELA_SCAFFOLD_OPTIONS,
} from "./kc-layer-fields.ts";
import { FIELD_OPTIONS } from "./kc-prompt-tester.ts";
import { BLOCK_CONFIG_FIELDS, DEFAULT_KC_TUTOR_CONFIG } from "./kc-tutor-config.ts";

test("passage_ela is selectable with its fields and guidance settings", () => {
  assert.equal(BLOCK_TYPES.at(-1), "passage_ela");
  assert.equal(BLOCK_TYPES.length, 11);
  const data = blankData("passage_ela");
  assert.equal(data.passage_genre, "informational");
  assert.equal(data.analysis_focus, "inference");
  assert.deepEqual(data.verbatim_evidence_quotes, ["", ""]);
  assert.equal("passage_text" in data, true);
  assert.equal("problem_statement" in data, false);

  const keys = BLOCK_CONFIG_FIELDS.passage_ela.map((field) => field.key);
  assert.deepEqual(keys, [
    "passage_ela_display_mode",
    "passage_ela_evidence_mode",
    "passage_ela_scaffold_style",
    "passage_ela_max_attempts_per_step",
    "passage_ela_reread_policy",
  ]);
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.passage_ela.passage_ela_display_mode, "full_on_open");
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.passage_ela.passage_ela_evidence_mode, "quote_or_close_paraphrase");
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.passage_ela.passage_ela_scaffold_style, "point_to_paragraph");
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.passage_ela.passage_ela_max_attempts_per_step, 2);
  assert.equal(DEFAULT_KC_TUTOR_CONFIG.blocks.passage_ela.passage_ela_reread_policy, "free_reprint");
  assert.deepEqual(
    PASSAGE_ELA_DISPLAY_OPTIONS.map(([id]) => id),
    ["full_on_open", "chunked_by_paragraph"],
  );
  assert.equal(PASSAGE_ELA_EVIDENCE_OPTIONS.length, 3);
  assert.equal(PASSAGE_ELA_SCAFFOLD_OPTIONS.length, 3);
  assert.deepEqual(PASSAGE_ELA_REREAD_OPTIONS.map(([id]) => id), ["free_reprint"]);

  const substeps = FIELD_OPTIONS.Substep.map(([id]) => id);
  assert.ok(substeps.includes("central_idea"));
  assert.ok(substeps.includes("cite_evidence"));
  assert.ok(substeps.includes("craft_or_inference"));
  assert.equal(Object.keys(DEFAULT_KC_TUTOR_CONFIG.blocks).length, 11);
});
