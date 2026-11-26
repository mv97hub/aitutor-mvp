import assert from "node:assert/strict";
import test from "node:test";

import { committedButtons } from "./committed-actions.ts";

test("a committed action list is the screen, including an empty list", () => {
  assert.deepEqual(committedButtons(["No final questions — let's continue!"]), [
    "No final questions — let's continue!",
  ]);
  assert.deepEqual(committedButtons([]), []);
  assert.equal(committedButtons(undefined), null);
  assert.equal(committedButtons(null), null);
});
