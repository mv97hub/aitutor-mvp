import assert from "node:assert/strict";
import test from "node:test";

import { finishSavedTurn, newTutorMessageId } from "./tutor-turn.ts";

test("a logging failure after the decision still returns the saved session", async () => {
  const session = { id: "saved", reply: "Say that again?" };
  const returned = await finishSavedTurn(session, async () => {
    throw new Error("could not store the prompt");
  });
  assert.equal(returned, session);
});

test("the call owns only a single newly committed assistant message, even for repeated text", () => {
  const prior = [{ id: "a1", role: "assistant", content: "Yes." }];
  const submitted = [...prior, { id: "c1", role: "user", content: "yes" }];
  const committed = [...submitted, { id: "a2", role: "assistant", content: "Yes." }];
  assert.equal(newTutorMessageId(prior, submitted), null);
  assert.equal(newTutorMessageId(submitted, committed), "a2");
  assert.equal(newTutorMessageId(committed, committed), null);
  assert.equal(newTutorMessageId(prior, [...committed, { id: "a3", role: "assistant" }]), null);
  assert.equal(newTutorMessageId([{ id: "other", role: "assistant" }], committed), null);
});
