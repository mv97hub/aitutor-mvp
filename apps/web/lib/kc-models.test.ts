import assert from "node:assert/strict";
import test from "node:test";

import { DEFAULT_KC_MODEL, KC_MODELS, kcModel } from "./kc-models.ts";

test("the KC menu keeps the CreateCourse models and adds a capable default and an expert", () => {
  assert.deepEqual(KC_MODELS.slice(0, 3), ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"]);
  assert.equal(DEFAULT_KC_MODEL, "gpt-4.1");
  assert.equal(KC_MODELS.at(-1), "gpt-6.1-sol");
  assert.equal(kcModel("gpt-6.1-sol"), "gpt-6.1-sol");
  assert.equal(kcModel("gpt-3.5-turbo"), DEFAULT_KC_MODEL);
  assert.equal(kcModel(""), DEFAULT_KC_MODEL);
});
