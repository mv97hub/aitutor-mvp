import assert from "node:assert/strict";
import test from "node:test";

import type { KcBlueprint } from "./kc.ts";
import { addComponent, earlierCodes, moveComponent, pruneLinks, removeComponent } from "./kc-blueprint-edit.ts";

function blueprint(): KcBlueprint {
  return {
    outcomes: ["Name the sum."],
    units: [
      {
        title: "Angles",
        summary: "Angle facts.",
        components: [
          { code: "idea-1", title: "Idea 1", summary: "First.", prerequisites: [] },
          { code: "idea-2", title: "Idea 2", summary: "Second.", prerequisites: ["idea-1"] },
        ],
      },
      {
        title: "Proofs",
        summary: "Proofs.",
        components: [{ code: "idea-3", title: "Idea 3", summary: "Third.", prerequisites: ["idea-2"] }],
      },
    ],
  };
}

test("moving a component across a unit drops a prerequisite that would point forward", () => {
  const moved = moveComponent(blueprint(), { unit: 1, index: 0 }, -1);
  const first = moved.units[0]?.components ?? [];
  assert.deepEqual(
    first.map((item) => item.code),
    ["idea-1", "idea-3", "idea-2"],
  );
  assert.deepEqual(first[1]?.prerequisites, []);
  assert.deepEqual(first[2]?.prerequisites, ["idea-1"]);
});

test("removing a component drops links to it and a new row has no code", () => {
  const removed = removeComponent(blueprint(), { unit: 0, index: 0 });
  assert.deepEqual(removed.units[0]?.components[0]?.prerequisites, []);
  const added = addComponent(removed, 1, "Capstone");
  const last = added.units[1]?.components.at(-1);
  assert.equal(last?.code, "");
  assert.equal(last?.title, "Capstone");
  assert.deepEqual(earlierCodes(added, { unit: 1, index: 1 }), ["idea-2", "idea-3"]);
});

test("prune keeps only prerequisites that already appeared", () => {
  const row = blueprint();
  row.units[0]!.components[0]!.prerequisites = ["idea-3"];
  const pruned = pruneLinks(row);
  assert.deepEqual(pruned.units[0]?.components[0]?.prerequisites, []);
  assert.deepEqual(pruned.units[1]?.components[0]?.prerequisites, ["idea-2"]);
});
