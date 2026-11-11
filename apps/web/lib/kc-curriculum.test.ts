import assert from "node:assert/strict";
import test from "node:test";

import { PASTE_LIMIT, PASTE_OVERRIDE_NOTE, intakeCutNotes, pasteOverridesDepth, pastedCurriculumCount } from "./kc-curriculum.ts";

test("a longer paste overrides Standard depth and a cut is noted", () => {
  const lines = [];
  for (let index = 1; index <= 42; index += 1) {
    lines.push(`Unit ${index}: Topic ${index}`);
    lines.push(`${index}. Topic ${index} about scarcity and choice.`);
  }
  const count = pastedCurriculumCount("", lines.join("\n"));
  assert.equal(count, 42);
  assert.equal(pasteOverridesDepth("standard", count), true);
  assert.equal(pasteOverridesDepth("standard", 12), false);
  assert.equal(pasteOverridesDepth("intro", 7), true);
  assert.equal(pasteOverridesDepth("curriculum", 42), false);
  assert.match(PASTE_OVERRIDE_NOTE, /overrides Standard depth/);
  assert.deepEqual(intakeCutNotes({ source_text_cut: true, standard_text_cut: true }).length, 2);
  assert.match(intakeCutNotes({ source_text_cut: true })[0] ?? "", /100,000/);
  assert.equal(PASTE_LIMIT, 100_000);
  assert.equal(pastedCurriculumCount("", "A prose source with no unit headers."), 0);
});
