import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../app/documentation/kc-prompt-layers/page.tsx", import.meta.url), "utf8");

test("the layers page explains the model prompt at the bottom", () => {
  const start = page.indexOf("How the prompt is written");
  assert.ok(start > page.indexOf("Variables panel keeps the seven headings"));
  const section = page.slice(start);
  for (const heading of [
    "This turn",
    "What to teach",
    "Who you are talking to",
    "How to teach",
    "How to sound",
    "What just happened",
    "What to return",
  ]) {
    assert.equal(section.split(heading).length - 1, 1, heading);
  }
  assert.match(page, /only when this turn reads it/);
  assert.match(page, /active block only/);
  assert.match(page, /Close component/);
  assert.match(page, /Close course/);
  assert.match(page, /Layer 2, child persona settings/);
  assert.match(page, /Response length/);
  assert.match(page, /Expression style/);
  assert.match(page, /Explanation style/);
  assert.match(page, /Challenge appetite/);
  assert.match(page, /Communication tone/);
  assert.match(page, /Learning support/);
  assert.match(page, /Interest tags/);
  assert.doesNotMatch(section, /You are the knowledge-component tutor/);
  assert.doesNotMatch(section, /Grade the answer against this core truth/);
});
