import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  SAFETY_FIELDS,
  SAFETY_GROUPS,
  eventsForChat,
  filterChatsWithUnreviewed,
  safetyExcerpt,
  showSafetyTag,
  unreviewedChatTotal,
  unreviewedEvents,
} from "./ai-safety.ts";
import { menuSections } from "./menu-pages.ts";

test("the safety field list has the seventeen settings in seven groups", () => {
  assert.equal(SAFETY_FIELDS.length, 17);
  assert.deepEqual([...SAFETY_GROUPS], [
    "Overall",
    "Content",
    "Wellbeing",
    "Privacy",
    "Honesty",
    "Manipulation",
    "Review",
  ]);
  for (const field of SAFETY_FIELDS) {
    assert.ok(SAFETY_GROUPS.includes(field.group), field.label);
    assert.ok(field.hover.length > 20, field.label);
  }
  assert.deepEqual(
    SAFETY_FIELDS.map((field) => field.label),
    [
      "Safety strictness",
      "Age scaling",
      "Blocked topics",
      "Sensitive school topics",
      "Harmful words from the child",
      "Distress response",
      "Trusted-adult message",
      "Emotional reliance",
      "Personal information",
      "No secrets",
      "AI disclosure",
      "Uncertainty",
      "Advice limits",
      "Links and media",
      "Jailbreak resistance",
      "Role-play limits",
      "Flag safety moments",
    ],
  );
});

test("the admin bar and the menu link to AI Safety", () => {
  const menu = readFileSync(new URL("../components/admin/AdminMenu.tsx", import.meta.url), "utf8");
  assert.match(menu, /href: "\/admin\/ai-safety"/);
  assert.match(menu, /label: "AI Safety"/);
  const admin = menuSections.find((section) => section.id === "administration");
  assert.ok(admin?.links.some((link) => link.href === "/admin/ai-safety" && link.label === "AI Safety"));
  const page = readFileSync(new URL("../app/documentation/ai-safety/page.tsx", import.meta.url), "utf8");
  assert.match(page, /Safety strictness/);
  assert.match(page, /Flag safety moments/);
});

test("the safety popup groups events for one chat and hides chats with none", () => {
  const events = [
    { id: "1", kc_session_id: "chat-a", reviewed_at: null, category: "distress" },
    { id: "2", kc_session_id: "chat-a", reviewed_at: "2026-11-11T00:00:00Z", category: "other" },
    { id: "3", kc_session_id: "chat-b", reviewed_at: null, category: "manipulation" },
  ];
  const chatA = eventsForChat(events, "chat-a");
  assert.equal(chatA.length, 2);
  assert.equal(unreviewedEvents(chatA).length, 1);
  assert.equal(showSafetyTag(chatA.length), true);
  assert.equal(showSafetyTag(eventsForChat(events, "chat-c").length), false);

  const chats = [
    { id: "chat-a", unreviewed_safety_count: 1, safety_event_count: 2 },
    { id: "chat-b", unreviewed_safety_count: 1, safety_event_count: 1 },
    { id: "chat-c", unreviewed_safety_count: 0, safety_event_count: 0 },
  ];
  assert.equal(unreviewedChatTotal(chats), 2);
  assert.deepEqual(
    filterChatsWithUnreviewed(chats, true).map((chat) => chat.id),
    ["chat-a", "chat-b"],
  );
  assert.equal(filterChatsWithUnreviewed(chats, false).length, 3);

  const view = readFileSync(new URL("../components/ViewKcChats.tsx", import.meta.url), "utf8");
  assert.match(view, /showSafetyTag/);
  assert.match(view, /Mark reviewed/);
  assert.match(view, /Chats with unreviewed safety/);
  assert.doesNotMatch(view, /parent portal|\/parents/);
});

test("the prompt tester can lift the Safety section from the front of the prompt", () => {
  const prompt = "Safety\nThese rules apply on every turn.\n\nThis turn\nAsk the question.";
  assert.equal(safetyExcerpt(prompt), "Safety\nThese rules apply on every turn.");
  assert.equal(safetyExcerpt("This turn\nAsk."), "");
  const tester = readFileSync(new URL("../components/KcPromptTester.tsx", import.meta.url), "utf8");
  assert.match(tester, /aria-label="Safety text"/);
});
