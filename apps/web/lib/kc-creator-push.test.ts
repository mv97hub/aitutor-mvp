import assert from "node:assert/strict";
import test from "node:test";

import type { KcBlock, KcComponent, KcComponentDraft } from "./kc.ts";
import { creatorPushPayload } from "./kc-creator-push.ts";

function component(): KcComponent {
  return {
    id: "unit-1",
    code: "river",
    title: "River fact",
    description: "A short summary.",
    outline: "How the river looks.",
    topics: [{ topic: "saved", goal: "Do not require this pair" }],
    kc_type: "factual",
    target: true,
    core_truth: "The river is blue.",
    rubric: ["States the color"],
    misconceptions: [],
    prerequisite_codes: [],
    encompasses_codes: [],
    type_fields: { fact: "The river is blue.", retrieval_question: "What color?" },
    blocks: [],
    marked_complete: false,
    missing: [],
    history: "",
  };
}

test("the push payload sends draft blocks and does not require topic pairs", () => {
  const blocks: KcBlock[] = [
    { id: "blk_1", type: "topic_goal", data: { topic: "color", goal: "Recall the color" } },
    { id: "blk_2", type: "retrieval_check", data: { expected_fact: "The river is blue." } },
  ];
  const saved = component();
  const draft: KcComponentDraft = {
    kind: "component",
    code: saved.code,
    title: saved.title,
    description: saved.description,
    outline: saved.outline,
    core_truth: saved.core_truth,
    misconceptions: saved.misconceptions,
    prerequisite_codes: saved.prerequisite_codes,
    encompasses_codes: saved.encompasses_codes,
    blocks,
  };
  const payload = creatorPushPayload(draft, saved);
  assert.deepEqual(payload.blocks, blocks);
  assert.equal(payload.blocks.length, 2);
  assert.equal("topics" in payload, false);
  assert.equal("kc_type" in payload, false);
  assert.equal("type_fields" in payload, false);
});
