import assert from "node:assert/strict";
import test from "node:test";

import { finishSavedTurn } from "./tutor-turn.ts";

test("a logging failure after the decision still returns the saved session", async () => {
  const session = { id: "saved", reply: "Say that again?" };
  const returned = await finishSavedTurn(session, async () => {
    throw new Error("could not store the prompt");
  });
  assert.equal(returned, session);
});
