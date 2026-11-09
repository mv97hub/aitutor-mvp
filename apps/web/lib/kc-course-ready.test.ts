import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { detailFrom } from "./api.ts";

test("a course-ready rejection shows the gap text", () => {
  assert.equal(
    detailFrom({ detail: ["Angle sum: no truth", "Angle sum: no outline"] }, "fallback"),
    "Angle sum: no truth · Angle sum: no outline",
  );
  assert.equal(detailFrom({ detail: ["The course has no components."] }, "fallback"), "The course has no components.");
  assert.equal(detailFrom({ detail: [{ msg: "Field required", type: "missing" }] }, "fallback"), "Field required");
});

test("KC Creator marks the whole course ready from the banner", () => {
  const creator = readFileSync(new URL("../components/KcCreator.tsx", import.meta.url), "utf8");
  const banner = creator.slice(creator.indexOf('className="kc-fast"'), creator.indexOf("</KcBanner>"));
  const ready = banner.indexOf("Mark whole course ready");
  const count = banner.indexOf("kc-fast-count");
  const scope = banner.indexOf("<KcBlockScope");
  const fast = banner.indexOf("Fast Create All");
  assert.ok(ready >= 0 && count > ready && scope > count && fast > scope);
  assert.match(banner, /\{course \? \(/);
  assert.match(banner, /course\.ready \?/);
  assert.match(banner, /type="button" disabled>\s*Course ready/);
  assert.match(banner, /action=\{markKcCourseReady\}/);
  assert.doesNotMatch(banner, /markKcComplete/);
  assert.doesNotMatch(banner, /\/complete/);
});
