import assert from "node:assert/strict";
import test from "node:test";

import { bulkPrompt, pendingInPhase, structureTemplate } from "./studio-build.ts";

test("structure templates name the course code and stay unaccepted", () => {
  const periods = structureTemplate("prem2", "periods", "");
  assert.match(periods.content, /Nothing is saved until you accept/);
  assert.deepEqual(
    periods.proposal.operations.map((op) => op.code),
    ["PREM2-U1", "PREM2-U2", "PREM2-U3"],
  );
  assert.equal(periods.proposal.operations[0].parent, "PREM2");

  const tree = structureTemplate("PREM2", "units", "");
  assert.deepEqual(
    tree.proposal.operations.map((op) => `${op.kind}:${op.code}`),
    ["unit:PREM2-U1", "quest:PREM2-U1-Q1", "quest:PREM2-U1-Q2", "unit:PREM2-U2", "quest:PREM2-U2-Q1", "quest:PREM2-U2-Q2"],
  );

  const named = structureTemplate("PREM2", "framework", "Premier League records");
  assert.match(named.content, /Premier League records/);
  assert.match(named.content, /suggestion/);
  assert.equal(named.proposal.operations[0].title, "Premier League records: opening");

  const fresh = structureTemplate("PREM2", "periods", "", ["PREM2-U1", "PREM2-U2"]);
  assert.deepEqual(
    fresh.proposal.operations.map((op) => op.code),
    ["PREM2-U3", "PREM2-U4", "PREM2-U5"],
  );
});

test("bulk prompts name the open codes and accept-all sees this phase", () => {
  const goals = bulkPrompt("goals", ["PREM2-U1-Q1", "PREM2-U1-Q2"]);
  assert.match(goals, /learning goal/);
  assert.match(goals, /PREM2-U1-Q1, PREM2-U1-Q2/);
  assert.match(goals, /Do not fill close style/);

  const close = bulkPrompt("close", ["PREM2-U1-Q1"]);
  assert.match(close, /quest-close choices/);
  assert.match(close, /PREM2-U1-Q1/);

  const pending = pendingInPhase(
    [
      { applied: false, proposal: { phase: "structure", operations: [{ op: "add" }] } },
      { applied: false, proposal: { phase: "goals", operations: [{ op: "update" }] } },
      { applied: true, proposal: { phase: "goals", operations: [{ op: "update" }] } },
      { applied: false, proposal: null },
    ],
    "goals",
  );
  assert.equal(pending.length, 1);
  assert.equal(pending[0].proposal?.phase, "goals");
});
