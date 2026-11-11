import assert from "node:assert/strict";
import test from "node:test";

import { readModelUsage } from "./model-usage.ts";

test("usage counts come from the SDK object and missing fields are zero", () => {
  assert.deepEqual(
    readModelUsage({ inputTokens: 12, outputTokens: 4, cachedInputTokens: 9 }),
    { input_tokens: 12, output_tokens: 4, cached_tokens: 9 },
  );
  assert.deepEqual(readModelUsage({}), { input_tokens: 0, output_tokens: 0, cached_tokens: 0 });
  assert.deepEqual(readModelUsage(undefined), { input_tokens: 0, output_tokens: 0, cached_tokens: 0 });
  assert.deepEqual(
    readModelUsage({ input: 3, output: 1, inputTokenDetails: { cacheReadTokens: 2 } }),
    { input_tokens: 3, output_tokens: 1, cached_tokens: 2 },
  );
  assert.deepEqual(readModelUsage({ inputTokens: 0, outputTokens: 0 }), {
    input_tokens: 0,
    output_tokens: 0,
    cached_tokens: 0,
  });
});
