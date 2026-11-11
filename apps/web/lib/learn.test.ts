import assert from "node:assert/strict";
import test from "node:test";

import {
  CHILD_STATUSES,
  blockStepDivider,
  childWriteBody,
  displayChildStatus,
  explorerFor,
  friendlyStrength,
  initials,
  learnCoursePath,
  starBurst,
  topicStars,
  blankChildDraft,
} from "./learn.ts";

test("explorer ranks follow the shared star thresholds", () => {
  assert.equal(explorerFor(0).explorer_rank, "Curious Spark");
  assert.equal(explorerFor(74).explorer_level, 1);
  assert.equal(explorerFor(75).explorer_rank, "Concept Builder");
  assert.equal(explorerFor(249).explorer_level, 2);
  assert.equal(explorerFor(250).explorer_rank, "Discovery Navigator");
  assert.equal(explorerFor(600).explorer_rank, "Grand Scholar");
  assert.equal(explorerFor(600).explorer_next, null);
  assert.equal(explorerFor(600).explorer_percent, 100);
  assert.equal(explorerFor(75).explorer_percent, 0);
});

test("child status labels never include the technical mastery word", () => {
  assert.equal(displayChildStatus("Mastered", "completed", "known"), "Mastered");
  assert.equal(displayChildStatus("Completed", "completed", "fragile"), "Completed");
  assert.equal(displayChildStatus("Fragile", "completed", "fragile"), "Completed");
  assert.equal(displayChildStatus(undefined, "in_progress", ""), "In Progress");
  assert.equal(displayChildStatus(undefined, "not_started", ""), "Up Next");
  for (const label of CHILD_STATUSES) {
    assert.equal(/fragile/i.test(label), false);
  }
});

test("a new learner write includes the avatar, the persona fields, and the tutor model", () => {
  const draft = blankChildDraft();
  draft.name = "Nova";
  draft.age = "9";
  draft.avatar_preset = "fox";
  draft.interest_tags = ["space_and_science", "video_games"];
  draft.interests = "rockets";
  const body = childWriteBody(draft, { includeName: true });
  assert.equal(body.display_name, "Nova");
  const profile = body.child_profile as {
    avatar_preset: string;
    interest_tags: string[];
    interests: string;
    tutor_model: string;
  };
  assert.equal(profile.avatar_preset, "fox");
  assert.deepEqual(profile.interest_tags, ["space_and_science", "video_games"]);
  assert.equal(profile.interests, "rockets");
  assert.equal(profile.tutor_model, "gpt-4.1");
  assert.equal(body.tutor_model, "gpt-4.1");
  assert.equal(Object.keys(profile).length, 13);
});

test("topic stars and a passed block use the child star rules", () => {
  assert.equal(
    topicStars({
      status: "completed",
      mastery: "known",
      completed_blocks: 1,
      first_try_blocks_count: 1,
      revealed_blocks_count: 0,
    }),
    55,
  );
  assert.equal(
    topicStars({
      status: "completed",
      mastery: "fragile",
      completed_blocks: 1,
      first_try_blocks_count: 0,
      revealed_blocks_count: 1,
    }),
    35,
  );
  const first = starBurst([], [{ id: "a", status: "completed", outcome: "passed", attempts: 1 }]);
  assert.equal(first.award, 15);
  assert.equal(first.firstTry, true);
  const again = starBurst(first.seen, [{ id: "a", status: "completed", outcome: "passed", attempts: 1 }]);
  assert.equal(again.award, 0);
  assert.equal(friendlyStrength("A required block was revealed."), "You finished this topic.");
  assert.equal(learnCoursePath("stu", "course", { kc: "topic" }).includes("/kc-tutor"), false);
});

test("a step divider names the finished step and the one that is opening", () => {
  const blocks = [
    { index: 0, type_label: "Topic + Goal", short_title: "Rise of Julius Caesar" },
    { index: 1, type_label: "Worked example", short_title: "" },
    { index: 5, type_label: "Retrieval check", short_title: "Rise of Julius Caesar" },
  ];
  assert.equal(
    blockStepDivider(undefined, 0, blocks, 6),
    "Step 1 of 6 — Topic + Goal — Rise of Julius Caesar",
  );
  assert.equal(blockStepDivider(undefined, 2, blocks, 6), null);
  assert.equal(blockStepDivider(0, 0, blocks, 6), null);
  assert.equal(
    blockStepDivider(0, 1, blocks, 4),
    "Step 1 complete · Up next: Step 2 of 4 — Worked example",
  );
  assert.equal(
    blockStepDivider(4, 5, blocks, 6),
    "Step 5 complete · Up next: Step 6 of 6 — Retrieval check — Rise of Julius Caesar",
  );
  assert.equal(blockStepDivider(undefined, 0, [{ index: 0, type_label: "Topic + Goal" }], 6), "Step 1 of 6 — Topic + Goal");
});

test("initials fall back when a child has not picked an icon", () => {
  assert.equal(initials("Storm"), "ST");
  assert.equal(initials("Iron Man"), "IM");
  assert.equal(initials("  "), "?");
});
