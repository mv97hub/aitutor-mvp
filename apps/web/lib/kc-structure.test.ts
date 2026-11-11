import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { structureControls, unitsAfterStartOver } from "./kc-structure.ts";

test("the structure panel shows Start over with one unit left", () => {
  const one = structureControls(1);
  assert.equal(one.startOver, true);
  assert.equal(one.deleteUnit, false);
  const several = structureControls(2);
  assert.equal(several.startOver, true);
  assert.equal(several.deleteUnit, true);
  const source = readFileSync(new URL("../components/KcStructureList.tsx", import.meta.url), "utf8");
  assert.match(source, /Start over/);
  assert.match(source, /Reset draft only/);
  assert.match(source, /Start over and delete components/);
  assert.match(source, /structureControls/);
  assert.match(source, /unitsAfterStartOver/);
  assert.doesNotMatch(source, /mode === "chat" \? null : [\s\S]*Start over/);
});

test("confirming delete-components removes the last unit", () => {
  const units = [{ title: "Only unit", components: [{ id: "one" }] }];
  assert.deepEqual(unitsAfterStartOver(units, "draft"), units);
  assert.deepEqual(unitsAfterStartOver(units, "delete-components"), []);
  const cleared = unitsAfterStartOver(units, "delete-components");
  assert.equal(cleared.length, 0);
});
