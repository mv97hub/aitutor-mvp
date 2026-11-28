import assert from "node:assert/strict";
import test from "node:test";

import {
  placementProbeCountLabel,
  retentionPercent,
  shouldOfferPlacementEntry,
  warmupBadgeLabel,
} from "./f5-placement.ts";
import type { KcTutorCourse } from "./kc.ts";

function sampleCourse(overrides: Partial<KcTutorCourse> = {}): KcTutorCourse {
  return {
    id: "course-1",
    code: "ai-work",
    title: "How does AI Work",
    description: "Learn how AI learns from data.",
    audience: "9-11",
    kind: "mastery",
    minutes: null,
    component_count: 5,
    started: false,
    ...overrides,
  };
}

test("shouldOfferPlacementEntry honors backend eligibility and >=4 unstarted fallback", () => {
  assert.equal(shouldOfferPlacementEntry(sampleCourse({ placement_eligible: true })), true);
  assert.equal(shouldOfferPlacementEntry(sampleCourse({ placement_eligible: false })), false);
  assert.equal(shouldOfferPlacementEntry(sampleCourse({ component_count: 5, started: false })), true);
  assert.equal(shouldOfferPlacementEntry(sampleCourse({ component_count: 3, started: false })), false);
  assert.equal(shouldOfferPlacementEntry(sampleCourse({ component_count: 5, started: true })), false);
  assert.equal(
    shouldOfferPlacementEntry(sampleCourse({ component_count: 5, started: false, placement_status: "completed" })),
    false,
  );
});

test("placementProbeCountLabel caps at 4 quick questions", () => {
  assert.equal(placementProbeCountLabel(sampleCourse({ component_count: 5, placement_max_probes: 3 })), "up to 3 quick questions");
  assert.equal(placementProbeCountLabel(sampleCourse({ component_count: 20, placement_max_probes: 4 })), "up to 4 quick questions");
  assert.equal(placementProbeCountLabel(sampleCourse({ component_count: 1, placement_max_probes: 1 })), "1 quick question");
});

test("warmupBadgeLabel and retentionPercent format cleanly", () => {
  assert.equal(warmupBadgeLabel(0), null);
  assert.equal(warmupBadgeLabel(1), "2-min memory boost ready");
  assert.equal(warmupBadgeLabel(3), "3 quick memory boosts ready");
  assert.equal(retentionPercent({ retrieval_strength: 0.584 }), 58);
  assert.equal(retentionPercent({ retrieval_strength: -0.2 }), 0);
  assert.equal(retentionPercent({ retrieval_strength: 1.4 }), 100);
});
