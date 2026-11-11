import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const tutor = readFileSync(new URL("../app/documentation/kc-tutor/page.tsx", import.meta.url), "utf8");
const layers = readFileSync(new URL("../app/documentation/kc-prompt-layers/page.tsx", import.meta.url), "utf8");
const flow = readFileSync(new URL("../components/docs/BlockCloseFlow.tsx", import.meta.url), "utf8");

test("both documentation pages render the block close flows", () => {
  for (const page of [tutor, layers]) {
    assert.match(page, /Block close flows/);
    assert.match(page, /BLOCK_CLOSE_FLOWS/);
    assert.match(page, /BlockCloseFlow/);
  }
  for (const title of ["Explanatory", "Topic / Goal", "Guided Discussion", "Assessment & Practice"]) {
    assert.match(flow, new RegExp(title.replace("/", "\\/")));
  }
  for (const step of [
    "explain_topic",
    "summary_check",
    "main",
    "initial_thesis",
    "counterexample_probe",
    "hook_and_predict",
    "critique",
    "faded_step",
    "solo_solve",
    "recall",
  ]) {
    assert.match(flow, new RegExp(step));
  }
  assert.match(flow, /did not fully complete this block/);
  assert.match(flow, /Never say congratulations/);
  assert.match(flow, /Redemption/);
  assert.match(flow, /next block opens in its own speech/);
});
