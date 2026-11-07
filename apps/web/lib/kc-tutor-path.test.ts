import assert from "node:assert/strict";
import test from "node:test";

import { openedSessionPath, tutorPath, tutorSessionTarget } from "./kc-tutor-path.ts";

test("a component link opens once, then a refresh loads that session", () => {
  const open = { student: "sam", course: "geo", kc: "angle", model: "gpt-4.1" };
  assert.deepEqual(tutorSessionTarget(open), {
    kind: "open",
    studentId: "sam",
    courseId: "geo",
    kcId: "angle",
  });

  const next = { student: "sam", course: "geo", session: "sess-1", model: "gpt-4.1" };
  assert.equal(openedSessionPath(open, "sess-1"), tutorPath(next));
  assert.equal(openedSessionPath(open, "sess-1").includes("kc="), false);
  assert.deepEqual(tutorSessionTarget(next), { kind: "load", sessionId: "sess-1" });
});

test("a completed session stays on its URL instead of opening step zero again", () => {
  assert.deepEqual(
    tutorSessionTarget({ student: "sam", course: "geo", kc: "angle", session: "sess-done" }),
    { kind: "load", sessionId: "sess-done" },
  );
});

test("Start Course Over and TEST KC Selection open the component they name", () => {
  const first = { student: "sam", course: "geo", kc: "first", model: "gpt-4.1" };
  const picked = { student: "sam", course: "geo", kc: "later", model: "gpt-4.1" };
  assert.deepEqual(tutorSessionTarget(first), {
    kind: "open",
    studentId: "sam",
    courseId: "geo",
    kcId: "first",
  });
  assert.deepEqual(tutorSessionTarget(picked), {
    kind: "open",
    studentId: "sam",
    courseId: "geo",
    kcId: "later",
  });
  assert.equal(tutorPath(first).includes("session="), false);
  assert.equal(tutorPath(picked).includes("session="), false);
});

test("choosing a child and course does not open a session", () => {
  assert.deepEqual(tutorSessionTarget({ student: "sam", course: "geo" }), { kind: "none" });
  assert.deepEqual(tutorSessionTarget({}), { kind: "none" });
});
