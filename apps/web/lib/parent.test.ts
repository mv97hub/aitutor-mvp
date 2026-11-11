import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  childCountLabel,
  knownId,
  landingPathFor,
  parentChildHref,
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
  assert.match(parent, /<SessionView session=\{session\} heading="work" \/>/);
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

test("the child menu changes chats and progress and stays put on the dashboard", () => {
  assert.equal(parentChildHref("chats", id, child), parentChats(id, child));
  assert.equal(parentChildHref("progress", id, child), parentProgress(id, child));
  assert.equal(parentChildHref("home", id, child), null);
  assert.equal(parentChildHref("settings", id, child), null);
});

test("dashboard, settings, chats, and parent progress share one parent frame", () => {
  for (const path of [
    "../components/parent/ParentDashboard.tsx",
    "../components/parent/ParentSettings.tsx",
    "../components/parent/ParentChats.tsx",
    "../app/parent/[parentId]/child/[studentId]/progress/page.tsx",
  ]) {
    assert.match(source(path), /ParentFrame/);
  }
  const frame = source("../components/parent/ParentFrame.tsx");
  assert.match(frame, /Parent portal · \{parentName\}/);
  assert.match(frame, /ds-top-btn/);
  assert.match(frame, /aria-label="Child"/);
  assert.match(frame, /parentChildHref/);
  for (const label of ["Dashboard", "Chats", "Progress", "Settings"]) {
    assert.match(frame, new RegExp(label));
  }
  assert.match(frame, /Choose a child first/);
  const dashboard = source("../components/parent/ParentDashboard.tsx");
  assert.doesNotMatch(dashboard, /BrandMark/);
  assert.doesNotMatch(dashboard, /Recent activity/);
  assert.doesNotMatch(dashboard, /This week/);
  assert.doesNotMatch(dashboard, /Needs attention/);
  assert.doesNotMatch(dashboard, /Next step/);
  assert.match(dashboard, /parentChats/);
  assert.match(dashboard, /parentProgress/);
  const settings = source("../components/parent/ParentSettings.tsx");
  assert.doesNotMatch(settings, /BrandMark/);
  const home = source("../app/parent/[parentId]/page.tsx");
  assert.match(home, /learners\.length === 0\) redirect\(parentSettings/);
  assert.doesNotMatch(home, /\/dashboard/);
  const admin = source("../components/ViewKcChats.tsx");
  assert.match(admin, /AdminFrame/);
  assert.doesNotMatch(admin, /ParentFrame/);
  const child = source("../app/kc-progress/page.tsx");
  assert.doesNotMatch(child, /ParentFrame/);
});

test("the dashboard is child boxes and two links, and the child menu matches the bar", () => {
  const dashboard = source("../components/parent/ParentDashboard.tsx");
  assert.match(dashboard, /parent-work-head/);
  assert.match(dashboard, /<h1>Dashboard<\/h1>/);
  assert.match(dashboard, /aria-label="Your children"/);
  assert.match(dashboard, /progress-card\$\{on \? " is-selected" : ""\}/);
  assert.match(dashboard, /aria-pressed=\{on\}/);
  assert.match(dashboard, /onClick=\{\(\) => setPickedId\(child\.id\)\}/);
  assert.match(dashboard, /onStudentChange=\{setPickedId\}/);
  assert.match(dashboard, /learners\.length === 1 \? learners\[0\]\.id : null/);
  assert.match(dashboard, /className="parent-choice"/);
  assert.match(dashboard, /parentChats\(parent\.id, picked\.id\)/);
  assert.match(dashboard, /parentProgress\(parent\.id, picked\.id\)/);
  assert.match(dashboard, /Choose a child first/);
  assert.doesNotMatch(dashboard, /ProgressTotals|ProgressRecommend|parent-board-card|learn-child-grid/);
  const frame = source("../components/parent/ParentFrame.tsx");
  assert.match(frame, /aria-label="Child"/);
  assert.match(frame, /parentChildHref/);
  const css = source("../app/globals.css");
  const marker = ".parent-frame .ds-admin-bar .parent-child-menu select";
  const selectAt = css.indexOf(`${marker} {`);
  assert.ok(selectAt >= 0);
  const selectRule = css.slice(selectAt, css.indexOf("}", selectAt));
  for (const bit of [
    "appearance: none",
    "min-height: 36px",
    "padding: 7px 32px 7px 14px",
    "border-radius: 9px",
    "color: #f8fafc",
  ]) {
    assert.ok(selectRule.includes(bit), bit);
  }
  const optionAt = css.indexOf(`${marker} option`);
  assert.ok(optionAt >= 0);
  const optionRule = css.slice(optionAt, css.indexOf("}", optionAt));
  assert.ok(optionRule.includes("color: #0f172a"));
});

test("the parent portal is on the documentation list", () => {
  const list = source("../app/documentation/page.tsx");
  assert.match(list, /\/documentation\/parent-portal/);
  const page = source("../app/documentation/parent-portal/page.tsx");
  assert.match(page, /There is no login yet/);
});
