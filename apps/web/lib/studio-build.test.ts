import assert from "node:assert/strict";
import test from "node:test";

import { bulkPrompt } from "./studio-build.ts";

test("bulk prompts name the open codes", () => {
  const goals = bulkPrompt("goals", ["PREM2-U1-Q1", "PREM2-U1-Q2"]);
  assert.match(goals, /learning goal/);
  assert.match(goals, /PREM2-U1-Q1, PREM2-U1-Q2/);
  assert.match(goals, /Do not fill close style/);

  const close = bulkPrompt("close", ["PREM2-U1-Q1"]);
  assert.match(close, /quest-close choices/);
  assert.match(close, /PREM2-U1-Q1/);
});
