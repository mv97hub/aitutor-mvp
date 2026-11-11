import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  PARENT_SUMMARY_INSTRUCTIONS,
  PARENT_SUMMARY_SCHEMA,
  parseParentSummary,
  transcriptText,
} from "./parent-summary.ts";

const chat = {
  status: "in_progress",
  student: { id: "s", display_name: "Ada Lovelace" },
  course: { id: "c", code: "rivers", title: "Rivers" },
  component: { id: "k", code: "river-1", title: "River color" },
  messages: [
    { id: "2", role: "user" as const, content: " I think blue. ", seq: 2, created_at: "2026-11-11T00:00:02Z" },
    { id: "1", role: "assistant" as const, content: "What color is the river?", seq: 1, created_at: "2026-11-11T00:00:01Z" },
  ],
};

test("the schema asks for a summary and talking points and nothing else", () => {
  assert.deepEqual(Object.keys(PARENT_SUMMARY_SCHEMA.properties), ["summary", "talking_points"]);
  assert.deepEqual([...PARENT_SUMMARY_SCHEMA.required], ["summary", "talking_points"]);
  assert.equal(PARENT_SUMMARY_SCHEMA.additionalProperties, false);
  assert.match(PARENT_SUMMARY_INSTRUCTIONS, /plain, warm words/i);
  assert.match(PARENT_SUMMARY_INSTRUCTIONS, /talking points/i);
});

test("the transcript is in order, uses the first name, and says where the chat stands", () => {
  const text = transcriptText(chat);
  assert.ok(text.includes("Child: Ada"));
  assert.ok(text.includes("Topic: River color (still in progress)"));
  assert.ok(text.indexOf("Tutor: What color is the river?") < text.indexOf("Ada: I think blue."));
  assert.ok(transcriptText({ ...chat, status: "completed" }).includes("(finished)"));
});

test("a long transcript keeps the most recent lines", () => {
  const long = {
    ...chat,
    messages: Array.from({ length: 200 }, (_, index) => ({
      id: String(index),
      role: "assistant" as const,
      content: `line number ${index}`,
      seq: index,
      created_at: "2026-11-11T00:00:00Z",
    })),
  };
  const text = transcriptText(long, 300);
  assert.ok(text.includes("line number 199"));
  assert.ok(!text.includes("line number 0\n"));
  assert.ok(text.includes("…"));
});

test("a model reply is cleaned and an empty one is rejected", () => {
  assert.deepEqual(
    parseParentSummary({ summary: "  Ada tried the river question. ", talking_points: [" Ask why ", "", 7, "Praise the guess"] }),
    { summary: "Ada tried the river question.", talking_points: ["Ask why", "Praise the guess"] },
  );
  assert.equal(parseParentSummary({ summary: "  ", talking_points: ["x"] }), null);
  assert.equal(parseParentSummary(null), null);
  assert.equal(parseParentSummary("text"), null);
  assert.deepEqual(parseParentSummary({ summary: "Ok" }), { summary: "Ok", talking_points: [] });
  assert.equal(parseParentSummary({ summary: "Ok", talking_points: Array(10).fill("a") })?.talking_points.length, 6);
});

test("the route checks the key, uses the parent endpoint, and saves nothing", () => {
  const route = readFileSync(new URL("../app/api/parent/summary/route.ts", import.meta.url), "utf8");
  assert.match(route, /missingKeyMessage\(DEFAULT_KC_MODEL\)/);
  assert.match(route, /\/parents\/\$\{parentId\}\/children\/\$\{studentId\}\/sessions\/\$\{sessionId\}/);
  assert.match(route, /generateText\(/);
  assert.match(route, /Output\.object\(/);
  assert.doesNotMatch(route, /method: "(POST|PUT|PATCH)"/);
  assert.doesNotMatch(route, /model-prompts/);
});
