import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_CHAT_CAP_CENTS,
  DEFAULT_CHILD_MODEL,
  DEFAULT_JUDGE_MODEL,
  chatCount,
  costUsd,
  ensureSimplification,
  estimateChatUsd,
  keptRunIds,
  lunaNote,
  sameModelWarning,
} from "./harness.ts";
import { GPT6_LUNA_MODEL } from "./kc-models.ts";

test("gpt-6-luna has no dollar price", () => {
  assert.equal(costUsd(GPT6_LUNA_MODEL, 1_000_000, 0, 1_000_000), null);
  assert.equal(costUsd("gpt-4.1-mini", 1_000_000, 0, 0), "0.4");
  const estimate = estimateChatUsd(GPT6_LUNA_MODEL, "gpt-4.1-mini", "gpt-6.1-sol");
  assert.equal(estimate.unpriced.includes(GPT6_LUNA_MODEL), true);
  assert.ok(estimate.usd);
  assert.match(lunaNote(GPT6_LUNA_MODEL) || "", /blank cost/);
  assert.equal(lunaNote("gpt-4.1"), null);
});

test("defaults and the chat matrix", () => {
  assert.equal(DEFAULT_CHILD_MODEL, "gpt-4.1-mini");
  assert.equal(DEFAULT_JUDGE_MODEL, "gpt-6.1-sol");
  assert.equal(DEFAULT_CHAT_CAP_CENTS, 40);
  assert.equal(chatCount({ children: 8, components: 3, models: 2, profiles: 1, iterations: 3 }), 144);
  assert.equal(sameModelWarning("gpt-4.1", ["gpt-4.1", "gpt-4.1-mini"]), true);
  assert.equal(sameModelWarning("gpt-4.1-mini", ["gpt-4.1"]), false);
});

test("a recommendation batch that only adds is given a shorter option", () => {
  const cards = ensureSimplification([
    { title: "Add a boredom line", kind: "add", prompt_direction: "longer" },
  ]);
  assert.equal(cards.some((card) => card.kind === "remove" && card.prompt_direction === "shorter"), true);
  const kept = ensureSimplification([
    { title: "Cut the extra rule", kind: "remove", prompt_direction: "shorter" },
  ]);
  assert.equal(kept.length, 1);
});

test("stored prompts stay for the baseline and the newest suite run", () => {
  assert.deepEqual(
    keptRunIds([
      { baseline_run_id: "base", run_ids: ["old", "base", "newest"] },
      { baseline_run_id: null, run_ids: ["only"] },
    ]).sort(),
    ["base", "newest", "only"].sort(),
  );
});
