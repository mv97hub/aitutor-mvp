import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_KC_MODEL,
  DEEPSEEK_FLASH_MODEL,
  KC_MODELS,
  LEGACY_DEEPSEEK_FLASH_MODEL,
  MISSING_OPENAI_KEY,
  MISSING_OPENROUTER_KEY,
  kcModel,
  missingKeyMessage,
  modelForCall,
} from "./kc-models.ts";

test("the KC menu keeps the CreateCourse models and adds a capable default and an expert", () => {
  assert.deepEqual(KC_MODELS.slice(0, 3), ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"]);
  assert.equal(DEFAULT_KC_MODEL, "gpt-4.1");
  assert.equal(KC_MODELS.includes("gpt-6.1-sol"), true);
  assert.equal(DEEPSEEK_FLASH_MODEL, "~deepseek/deepseek-flash-latest");
  assert.equal(KC_MODELS.at(-1), DEEPSEEK_FLASH_MODEL);
  assert.equal(kcModel("gpt-6.1-sol"), "gpt-6.1-sol");
  assert.equal(kcModel(DEEPSEEK_FLASH_MODEL), DEEPSEEK_FLASH_MODEL);
  assert.equal(kcModel(LEGACY_DEEPSEEK_FLASH_MODEL), DEEPSEEK_FLASH_MODEL);
  assert.equal(modelForCall(LEGACY_DEEPSEEK_FLASH_MODEL), DEEPSEEK_FLASH_MODEL);
  assert.equal(modelForCall("gpt-4o-mini"), "gpt-4o-mini");
  assert.equal(modelForCall("gpt-4.1"), "gpt-4.1");
  assert.equal(kcModel("gpt-3.5-turbo"), DEFAULT_KC_MODEL);
  assert.equal(kcModel(""), DEFAULT_KC_MODEL);
});

test("DeepSeek asks for the OpenRouter key and OpenAI models keep their own key", () => {
  const previousOpenAI = process.env.OPENAI_API_KEY;
  const previousRouter = process.env.OPENROUTER_API_KEY;
  try {
    delete process.env.OPENAI_API_KEY;
    delete process.env.OPENROUTER_API_KEY;
    assert.equal(missingKeyMessage("gpt-4.1"), MISSING_OPENAI_KEY);
    assert.equal(missingKeyMessage(DEEPSEEK_FLASH_MODEL), MISSING_OPENROUTER_KEY);
    assert.equal(missingKeyMessage(LEGACY_DEEPSEEK_FLASH_MODEL), MISSING_OPENROUTER_KEY);

    process.env.OPENAI_API_KEY = "sk-test";
    assert.equal(missingKeyMessage("gpt-4.1"), null);
    assert.equal(missingKeyMessage(DEEPSEEK_FLASH_MODEL), MISSING_OPENROUTER_KEY);

    process.env.OPENROUTER_API_KEY = "or-test";
    delete process.env.OPENAI_API_KEY;
    assert.equal(missingKeyMessage(DEEPSEEK_FLASH_MODEL), null);
    assert.equal(missingKeyMessage("gpt-4o"), MISSING_OPENAI_KEY);
  } finally {
    if (previousOpenAI === undefined) delete process.env.OPENAI_API_KEY;
    else process.env.OPENAI_API_KEY = previousOpenAI;
    if (previousRouter === undefined) delete process.env.OPENROUTER_API_KEY;
    else process.env.OPENROUTER_API_KEY = previousRouter;
  }
});
