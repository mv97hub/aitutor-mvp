import assert from "node:assert/strict";
import test from "node:test";

import type { KcBlueprint } from "./kc.ts";
import { addComponent, addUnit, earlierCodes, moveComponent, pruneLinks, removeComponent, removeUnit } from "./kc-blueprint-edit.ts";

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

test("removing a unit drops its components and an emptied unit disappears", () => {
  const dropped = removeUnit(blueprint(), 1);
  assert.equal(dropped.units.length, 1);
  assert.deepEqual(
    dropped.units[0]?.components.map((item) => item.code),
    ["idea-1", "idea-2"],
  );
  const only = removeComponent(removeComponent(blueprint(), { unit: 1, index: 0 }), { unit: 0, index: 1 });
  assert.equal(only.units.length, 1);
  assert.equal(only.units[0]?.components.length, 1);
  const added = addUnit(dropped);
  assert.equal(added.units.length, 2);
  assert.equal(added.units[1]?.title, "New unit");
  assert.equal(removeUnit(added, 0).units.length, 1);
});

test("adding a unit appends a unit and one new component", () => {
  const added = addUnit(blueprint());
  assert.equal(added.units.length, 3);
  assert.equal(added.units[2]?.title, "New unit");
  assert.equal(added.units[2]?.components.length, 1);
  assert.equal(added.units[2]?.components[0]?.title, "New component");
  assert.equal(added.units[2]?.components[0]?.code, "");
});

test("prune keeps only prerequisites that already appeared", () => {
  const row = blueprint();
  row.units[0]!.components[0]!.prerequisites = ["idea-3"];
  const pruned = pruneLinks(row);
  assert.deepEqual(pruned.units[0]?.components[0]?.prerequisites, []);
  assert.deepEqual(pruned.units[1]?.components[0]?.prerequisites, ["idea-2"]);
});
