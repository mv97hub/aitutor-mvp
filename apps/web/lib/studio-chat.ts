/** Chat-route policy: one retry, then a plain sentence. No model call lives here. */

export type FailureKind = "schema" | "checker" | "transport";

export type SettleResult =
  | { action: "retry"; note: string }
  | { action: "banner"; text: string }
  | { action: "save"; text: string; proposal: { operations: unknown[] } | null };

export function rejectionReply(reason: string): string {
  return reason.trim();
}

export function detailFrom(body: unknown, fallback: string): string {
  if (typeof body === "string" && body.trim()) return body.trim();
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
  }
  return fallback;
}

export function plainFailure(error: unknown): string {
  const raw = error instanceof Error ? error.message : typeof error === "string" ? error : "";
  const collapsed = raw.replace(/\s+/g, " ").trim();
  if (!collapsed || collapsed.length > 180 || /[{[`]|schema|json/i.test(collapsed)) {
    return "The model reply could not be read.";
  }
  return collapsed.endsWith(".") ? collapsed : `${collapsed}.`;
}

export function retryNote(reason: string): string {
  return `The previous reply was rejected. ${reason.trim()} Send a patch that fixes this. Do not say the course was saved.`;
}

export function settleModelResult(input: {
  attempt: number;
  failure: string | null;
  kind: FailureKind | null;
  reply: string;
  operations: unknown[];
}): SettleResult {
  if (input.failure) {
    const sentence =
      input.kind === "schema" ? plainFailure(input.failure) : rejectionReply(input.failure);
    if (input.kind === "transport") return { action: "banner", text: sentence };
    if (input.attempt < 1) return { action: "retry", note: retryNote(sentence) };
    if (input.kind === "schema") return { action: "banner", text: sentence };
    return { action: "save", text: sentence, proposal: null };
  }
  const proposal = input.operations.length > 0 ? { operations: input.operations } : null;
  const text =
    input.reply.trim() ||
    (proposal ? "Here is a change to accept." : "I don't have a change for the course yet.");
  return { action: "save", text, proposal };
}
