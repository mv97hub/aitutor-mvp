import assert from "node:assert/strict";
import test from "node:test";

import type { KcComponent, KcComponentDraft } from "./kc.ts";
import { creatorPushPayload } from "./kc-creator-push.ts";

function component(topics: { topic: string; goal: string }[]): KcComponent {
  return {
    id: "unit-1",
    code: "river",
    title: "River fact",
    description: "A short summary.",
    outline: "How the river looks.",
    topics,
    kc_type: "factual",
    target: true,
    core_truth: "The river is blue.",
    rubric: ["States the color"],
    misconceptions: [],
    prerequisite_codes: [],
    encompasses_codes: [],
    type_fields: { fact: "The river is blue.", retrieval_question: "What color?" },
    marked_complete: false,
    missing: [],
    history: "",
  };
}

test("the push payload keeps every topic-goal pair from the model draft", () => {
  const pairs = [
    { topic: "color", goal: "Recall the color" },
    { topic: "banks", goal: "Name a bank" },
    { topic: "current", goal: "Say which way it flows" },
    { topic: "source", goal: "Name where it starts" },
  ];
  const saved = component(pairs.slice(0, 3));
  const draft: KcComponentDraft = {
    kind: "component",
    code: saved.code,
    title: saved.title,
    description: saved.description,
    outline: saved.outline,
    topics: pairs,
    kc_type: "factual",
    core_truth: saved.core_truth,
    rubric: saved.rubric,
    misconceptions: saved.misconceptions,
    prerequisite_codes: saved.prerequisite_codes,
    encompasses_codes: saved.encompasses_codes,
    type_fields: saved.type_fields,
  };
  const payload = creatorPushPayload(draft, saved);
  assert.deepEqual(payload.topics, pairs);
  assert.equal(payload.topics.length, 4);
});
