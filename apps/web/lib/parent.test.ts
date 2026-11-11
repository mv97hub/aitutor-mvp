import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  childCountLabel,
  knownId,
  landingPathFor,
  parentChats,
  parentHome,
  parentProgress,
  parentSettings,
  toggledIds,
} from "./parent.ts";

const id = "11111111-2222-3333-4444-555555555555";
const child = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

function source(path: string): string {
  return readFileSync(new URL(path, import.meta.url), "utf8");
}

test("parent paths stay under /parent", () => {
  assert.equal(parentHome(id), `/parent/${id}`);
  assert.equal(parentSettings(id), `/parent/${id}/settings`);
  assert.equal(parentChats(id, child), `/parent/${id}/child/${child}/chats`);
  assert.equal(parentProgress(id, child), `/parent/${id}/child/${child}/progress`);
  assert.equal(parentProgress(id, child, "c 1"), `/parent/${id}/child/${child}/progress?course=c%201`);
  for (const path of [parentHome(id), parentSettings(id), parentChats(id, child), parentProgress(id, child, id)]) {
    assert.ok(path.startsWith("/parent/"), path);
    assert.ok(!path.startsWith("/learn"), path);
  }
});

test("ids must be UUIDs", () => {
  assert.equal(knownId(` ${id} `), id);
  assert.equal(knownId("sam"), null);
  assert.equal(knownId(undefined), null);
  assert.equal(knownId("../admin"), null);
});

test("a new parent or one with no children lands on settings first", () => {
  assert.equal(landingPathFor({ id, child_count: 0 }), parentSettings(id));
  assert.equal(landingPathFor({ id, child_count: 2 }), parentHome(id));
  assert.equal(childCountLabel(0), "No children linked yet");
  assert.equal(childCountLabel(1), "1 child");
  assert.equal(childCountLabel(3), "3 children");
});

test("ticking a child adds it once and unticking removes it", () => {
  assert.deepEqual(toggledIds([], "a", true), ["a"]);
  assert.deepEqual(toggledIds(["a"], "a", true), ["a"]);
  assert.deepEqual(toggledIds(["a", "b"], "a", false), ["b"]);
  assert.deepEqual(toggledIds(["b"], "a", false), ["b"]);
});

test("the shared transcript only reads prompts when debug is on", () => {
  const view = source("../components/KcSessionView.tsx");
  assert.match(view, /debug = false/);
  assert.match(view, /debug\s*\?\s*promptsOnTranscript/);
  const admin = source("../components/ViewKcChats.tsx");
  assert.match(admin, /session=\{session\}/);
  assert.match(admin, /\bdebug\b/);
  assert.match(admin, /downloadKcChat\(session\)/);
  const parent = source("../components/parent/ParentChats.tsx");
  assert.match(parent, /<SessionView session=\{session\} \/>/);
  assert.doesNotMatch(parent, /debug|PromptDialog|AdminFrame|downloadKcChat|Download/);
});

test("the parent chat type has no prompts key", () => {
  const types = source("./parent.ts");
  const detail = types.slice(types.indexOf("export type ParentChatDetail"), types.indexOf("/** Ids are UUIDs"));
  assert.doesNotMatch(detail, /prompts/);
});

test("progress takes an area so parent links never leave /parent", () => {
  const progress = source("../components/KcCourseProgress.tsx");
  assert.match(progress, /export type ProgressArea/);
  assert.match(progress, /area \? areaCourseHref\(area, course\.id\)/);
  assert.match(progress, /progressPath: string/);
  assert.match(progress, /\{area \? null : \(/);
  const page = source("../app/parent/[parentId]/child/[studentId]/progress/page.tsx");
  assert.match(page, /area=\{\{/);
  assert.doesNotMatch(page, /["`]\/(learn|kc-progress)/);
});

test("the parent portal is on the documentation list", () => {
  const list = source("../app/documentation/page.tsx");
  assert.match(list, /\/documentation\/parent-portal/);
  const page = source("../app/documentation/parent-portal/page.tsx");
  assert.match(page, /There is no login yet/);
});
