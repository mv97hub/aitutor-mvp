import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  kcChatDownload,
  kcChatDownloadFilename,
  kcChatDownloadJson,
  type ChatDownloadSession,
} from "./kc-chat-download.ts";

const sessionId = "11111111-2222-3333-4444-555555555555";

function session(overrides: Partial<ChatDownloadSession> = {}): ChatDownloadSession {
  return {
    id: sessionId,
    status: "in_progress",
    created_at: "2026-11-11T12:00:00Z",
    updated_at: "2026-11-11T12:04:00Z",
    student: { id: "student-1", display_name: "Ada Lovelace" },
    course: { id: "course-1", title: "Rivers" },
    component: { id: "kc-1", code: "river-fact", title: "River fact" },
    messages: [
      {
        role: "assistant",
        content: "What is true of River fact?",
        created_at: "2026-11-11T12:01:00Z",
      },
      {
        role: "user",
        content: "Water flows downhill.",
        created_at: "2026-11-11T12:02:00Z",
        block_step: "Block 2 · Teach back",
      },
    ],
    prompts: [
      {
        system_prompt: "You are the knowledge-component tutor.",
        messages: [
          { role: "user", content: "Say this step to the student now." },
          { role: "request", content: { temperature: 0.2 } },
        ],
        model: "gpt-4o-mini",
        created_at: "2026-11-11T12:01:00Z",
        rubric_met: ["names the flow"],
        misconception: null,
      },
    ],
    ...overrides,
  };
}

test("the download payload matches the loaded session, including the prompt", () => {
  const loaded = session({ tutor: { name: "Owl" }, safety_events: [{ id: "event-1", category: "other" }] });
  const payload = kcChatDownload(loaded);

  assert.equal(payload.student, loaded.student);
  assert.equal(payload.course, loaded.course);
  assert.equal(payload.component, loaded.component);
  assert.deepEqual(payload.tutor, { name: "Owl" });
  assert.equal(payload.session_id, loaded.id);
  assert.equal(payload.status, loaded.status);
  assert.equal(payload.started_at, loaded.created_at);
  assert.equal(payload.updated_at, loaded.updated_at);
  assert.deepEqual(Object.keys(payload), [
    "student",
    "course",
    "component",
    "tutor",
    "session_id",
    "status",
    "started_at",
    "updated_at",
    "messages",
    "prompts",
    "safety_events",
  ]);

  assert.deepEqual(payload.messages, [
    {
      role: "assistant",
      text: "What is true of River fact?",
      time: "2026-11-11T12:01:00Z",
    },
    {
      role: "user",
      text: "Water flows downhill.",
      time: "2026-11-11T12:02:00Z",
      block_step: "Block 2 · Teach back",
    },
  ]);
  assert.equal(payload.prompts[0]?.system_prompt, loaded.prompts?.[0]?.system_prompt);
  assert.deepEqual(payload.prompts[0]?.messages, loaded.prompts?.[0]?.messages);
  assert.equal(payload.prompts[0]?.model, "gpt-4o-mini");
  assert.equal(payload.prompts[0]?.time, "2026-11-11T12:01:00Z");
  assert.deepEqual(payload.prompts[0]?.rubric_met, ["names the flow"]);
  assert.deepEqual(payload.safety_events, [{ id: "event-1", category: "other" }]);

  const file = kcChatDownloadJson(loaded);
  assert.match(file, /^\{\n  "student":/);
  assert.deepEqual(JSON.parse(file), payload);
  assert.equal(kcChatDownloadFilename(loaded), `kc-chat-Ada-Lovelace-${sessionId}.json`);
});

test("a session with no stored prompt still downloads the messages and an empty prompt list", () => {
  const loaded = session({ prompts: [] });
  const payload = kcChatDownload(loaded);

  assert.equal(payload.messages.length, loaded.messages.length);
  assert.equal(payload.messages[0]?.text, loaded.messages[0]?.content);
  assert.deepEqual(payload.prompts, []);
  assert.equal(payload.tutor, null);
  assert.equal("safety_events" in payload, false);
  assert.equal("block_step" in (payload.messages[0] ?? {}), false);

  const omitted = kcChatDownload(session({ prompts: undefined }));
  assert.deepEqual(omitted.prompts, []);
  assert.equal(omitted.messages[1]?.text, "Water flows downhill.");

  const file = kcChatDownloadJson(loaded);
  assert.equal(JSON.parse(file).prompts.length, 0);
  assert.equal(JSON.parse(file).messages.length, 2);
});

test("the parent chat view does not gain a download or prompts", () => {
  const parent = readFileSync(new URL("../components/parent/ParentChats.tsx", import.meta.url), "utf8");
  const admin = readFileSync(new URL("../components/ViewKcChats.tsx", import.meta.url), "utf8");
  assert.match(parent, /<SessionView session=\{session\} \/>/);
  assert.doesNotMatch(parent, /downloadKcChat|Download|prompts/);
  assert.match(admin, /downloadKcChat\(session\)/);
  assert.match(admin, /\bdebug\b/);
});
