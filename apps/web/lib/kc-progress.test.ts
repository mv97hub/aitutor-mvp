import assert from "node:assert/strict";
import test from "node:test";

import { networkStatusClass, statusByCode, unitsByStatus, type KcProgressUnit } from "./kc-progress.ts";

function unit(code: string, status: KcProgressUnit["status"], patch = false): KcProgressUnit {
  return { id: code, code, title: code, kc_type: "factual", patch, status };
}

test("the three lists keep course order and the map joins on component code", () => {
  const units = [
    unit("known", "completed"),
    unit("open", "in_progress"),
    unit("untouched", "not_started"),
    unit("also-known", "completed"),
    unit("patch", "not_started", true),
  ];
  const groups = unitsByStatus(units);
  assert.deepEqual(
    groups.completed.map((item) => item.code),
    ["known", "also-known"],
  );
  assert.deepEqual(
    groups.in_progress.map((item) => item.code),
    ["open"],
  );
  assert.deepEqual(
    groups.not_started.map((item) => item.code),
    ["untouched", "patch"],
  );
  assert.deepEqual(statusByCode(units), {
    known: "completed",
    open: "in_progress",
    untouched: "not_started",
    "also-known": "completed",
    patch: "not_started",
  });
  assert.equal(networkStatusClass("completed"), "is-completed");
  assert.equal(networkStatusClass("in_progress"), "is-in-progress");
  assert.equal(networkStatusClass("not_started"), "is-not-started");
  assert.equal(networkStatusClass(undefined), "");
});
