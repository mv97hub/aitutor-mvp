import assert from "node:assert/strict";
import test from "node:test";

import { detailFrom, plainFailure, replyIfUnwritten, retryNote, settleModelResult } from "./studio-chat.ts";

const schemaDump =
  'No object generated: response did not match schema. {"close_style":"quiz","path":"patch.operations.0"}';

test("a schema failure is retried once with a plain sentence", () => {
  const first = settleModelResult({
    attempt: 0,
    failure: schemaDump,
    kind: "schema",
    reply: "",
    operations: [],
  });
  assert.equal(first.action, "retry");
  if (first.action !== "retry") return;
  assert.match(first.note, /The model reply could not be read/);
  assert.equal(first.note.includes("close_style"), false);
  assert.equal(first.note.includes("{"), false);
  assert.match(first.note, /Do not say the course was saved/);

  const second = settleModelResult({
    attempt: 1,
    failure: schemaDump,
    kind: "schema",
    reply: "",
    operations: [],
  });
  assert.deepEqual(second, { action: "banner", text: "The model reply could not be read." });
});

test("a checker rejection is retried once, then shown with no proposal", () => {
  const reason = "Position must be an integer from 1 to 200.";
  const first = settleModelResult({
    attempt: 0,
    failure: `  ${reason}  `,
    kind: "checker",
    reply: "The structure was saved.",
    operations: [{ op: "add" }],
  });
  assert.equal(first.action, "retry");
  if (first.action !== "retry") return;
  assert.equal(retryNote(reason), first.note);
  assert.match(first.note, new RegExp(reason.replace(/[.]/g, "\\.")));
  assert.equal(first.note.includes("The structure was saved"), false);
  assert.match(first.note, /Do not say the course was saved/);

  const second = settleModelResult({
    attempt: 1,
    failure: reason,
    kind: "checker",
    reply: "The structure was saved.",
    operations: [{ op: "add" }],
  });
  assert.deepEqual(second, { action: "save", text: reason, proposal: null });
});

test("a good reply is saved, and a transport error is a banner", () => {
  const saved = settleModelResult({
    attempt: 0,
    failure: null,
    kind: null,
    reply: "Here is the first unit.",
    operations: [{ op: "add", code: "GEO-U1" }],
  });
  assert.equal(saved.action, "save");
  if (saved.action !== "save") return;
  assert.equal(saved.text, "Here is the first unit.");
  assert.deepEqual(saved.proposal, { operations: [{ op: "add", code: "GEO-U1" }] });

  const empty = settleModelResult({
    attempt: 0,
    failure: null,
    kind: null,
    reply: "",
    operations: [],
  });
  assert.deepEqual(empty, {
    action: "save",
    text: "I don't have a change for the course yet.",
    proposal: null,
  });

  const held = settleModelResult({
    attempt: 0,
    failure: null,
    kind: null,
    reply: "   ",
    operations: [{ op: "add" }],
  });
  assert.equal(held.action, "save");
  if (held.action !== "save") return;
  assert.match(held.text, /Push draft to Tree/i);
  assert.equal(held.text.toLowerCase().includes("accept"), false);
  assert.deepEqual(held.proposal, { operations: [{ op: "add" }] });

  const down = settleModelResult({
    attempt: 0,
    failure: detailFrom({ detail: "Could not save the reply." }, "fallback"),
    kind: "transport",
    reply: "",
    operations: [],
  });
  assert.deepEqual(down, { action: "banner", text: "Could not save the reply." });
});

test("replyIfUnwritten refuses a claim that the quests were added", () => {
  assert.equal(replyIfUnwritten("I've added the quests"), "Those quests are not in the course yet.");
  assert.equal(replyIfUnwritten("Those titles are a draft."), "Those titles are a draft.");
});

test("plainFailure keeps a short sentence and drops a field path", () => {
  assert.equal(plainFailure("The model did not answer"), "The model did not answer.");
  assert.equal(plainFailure(schemaDump).includes("close_style"), false);
  assert.equal(detailFrom("  Close style must be one or several.  ", "fallback"), "Close style must be one or several.");
});
