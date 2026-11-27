import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  absoluteShareUrl,
  activeLockLabels,
  formatHakeGain,
  formatPercent,
  trajectoryTone,
} from "./parent-copilot.ts";

test("trajectory tones and score formatters match F6 UI contract", () => {
  assert.equal(trajectoryTone("flourishing"), "good");
  assert.equal(trajectoryTone("struggling"), "alert");
  assert.equal(trajectoryTone("needs_reinforcement"), "warn");
  assert.equal(trajectoryTone("returning"), "warn");
  assert.equal(trajectoryTone("steady_progress"), "calm");

  assert.equal(formatPercent(0.846), "85%");
  assert.equal(formatPercent(null), "—");
  assert.equal(formatHakeGain(0.5), "+50%");
  assert.equal(formatHakeGain(-0.12), "-12%");
  assert.equal(formatHakeGain(null), "—");
});

test("activeLockLabels and absoluteShareUrl format parent policy locks and share links cleanly", () => {
  assert.deepEqual(
    activeLockLabels({
      more_guided_examples: true,
      gentler_socratic: false,
      anchor_in_interest: "dogs",
    }),
    ["More guided examples", "Anchor in dogs"],
  );
  assert.deepEqual(activeLockLabels(undefined), []);
  assert.equal(
    absoluteShareUrl("/teacher/share/abc123", "https://aitutor-mvp-web.onrender.com/"),
    "https://aitutor-mvp-web.onrender.com/teacher/share/abc123",
  );
});

test("teacher share page stays strictly read-only with no chat transcript or tutor edit imports", () => {
  const teacherPage = readFileSync(
    new URL("../app/teacher/share/[token]/page.tsx", import.meta.url),
    "utf8",
  );
  assert.equal(teacherPage.includes("ParentChat"), false);
  assert.equal(teacherPage.includes("interventions/apply"), false);
  assert.equal(teacherPage.includes("SkillRadar"), true);
});
