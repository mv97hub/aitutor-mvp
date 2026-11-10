import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_AVATAR_PRESET,
  TUTOR_AVATAR_CATEGORIES,
  TUTOR_AVATAR_PRESETS,
  getTutorAvatarPreset,
} from "./tutor-avatars.ts";

test("the avatar library has 64 presets across 8 categories of 8 icons", () => {
  assert.equal(TUTOR_AVATAR_CATEGORIES.length, 8);
  assert.equal(TUTOR_AVATAR_PRESETS.length, 64);

  const ids = new Set(TUTOR_AVATAR_PRESETS.map((item) => item.id));
  assert.equal(ids.size, 64);
  assert.ok(ids.has(DEFAULT_AVATAR_PRESET));

  for (const category of TUTOR_AVATAR_CATEGORIES) {
    const inCategory = TUTOR_AVATAR_PRESETS.filter((item) => item.category === category.id);
    assert.equal(inCategory.length, 8, `Expected 8 icons in ${category.id}`);
    for (const preset of inCategory) {
      assert.ok(preset.paths.length >= 1, `Expected SVG paths for ${preset.id}`);
    }
  }

  const fallback = getTutorAvatarPreset("unknown_icon");
  assert.equal(fallback.id, "default_circle");
  assert.equal(fallback.bg, "#e2e8f0");
});
