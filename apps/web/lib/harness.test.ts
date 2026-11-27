import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_CHAT_CAP_CENTS,
  DEFAULT_CHILD_MODEL,
  chatCount,
  costUsd,
  listedTestChildren,
  lunaNote,
  sameModelWarning,
} from "./harness.ts";
import { GPT6_LUNA_MODEL } from "./kc-models.ts";

test("gpt-6-luna has no dollar price", () => {
  assert.equal(costUsd(GPT6_LUNA_MODEL, 1_000_000, 0, 1_000_000), null);
  assert.equal(costUsd("gpt-4.1-mini", 1_000_000, 0, 0), "0.4");
  assert.match(lunaNote(GPT6_LUNA_MODEL) || "", /blank cost/);
  assert.equal(lunaNote("gpt-4.1"), null);
});

test("the new run child list keeps AI_Child13 and AI_Child14", () => {
  const names = listedTestChildren([
    { name: "AI_Child12", archived: false },
    { name: "AI_Child13", archived: false },
    { name: "AI_Child14" },
    { name: "AI_Child9", archived: true },
  ]).map((persona) => persona.name);
  assert.deepEqual(names, ["AI_Child12", "AI_Child13", "AI_Child14"]);
});

test("defaults and the chat matrix", () => {
  assert.equal(DEFAULT_CHILD_MODEL, "gpt-4.1-mini");
  assert.equal(DEFAULT_CHAT_CAP_CENTS, 40);
  assert.equal(chatCount({ children: 8, components: 3, models: 2, profiles: 1, iterations: 3 }), 144);
  assert.equal(sameModelWarning("gpt-4.1", ["gpt-4.1", "gpt-4.1-mini"]), true);
  assert.equal(sameModelWarning("gpt-4.1-mini", ["gpt-4.1"]), false);
});
