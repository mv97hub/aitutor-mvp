/** Counts from the AI SDK usage object. Missing numbers are 0. Do not re-tokenize. */

export type ModelUsageCounts = {
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
};

function firstCount(...values: unknown[]): number {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return Math.max(0, Math.round(value));
  }
  return 0;
}

export function readModelUsage(usage: unknown): ModelUsageCounts {
  const row = usage && typeof usage === "object" ? (usage as Record<string, unknown>) : {};
  const details =
    row.inputTokenDetails && typeof row.inputTokenDetails === "object"
      ? (row.inputTokenDetails as Record<string, unknown>)
      : {};
  return {
    input_tokens: firstCount(row.inputTokens, row.input, row.promptTokens),
    output_tokens: firstCount(row.outputTokens, row.output, row.completionTokens),
    cached_tokens: firstCount(row.cachedInputTokens, row.cachedTokens, row.cached, details.cacheReadTokens),
  };
}
