import type { LiveLine } from "./harness-runner.ts";

export type TranscriptLine = { role: "tutor" | "child"; text: string; seq?: number };

/** Session messages are the record. A stored seq is the turn number, not a renumbered list index. */
export function transcriptForChat(
  chatId: string,
  messages: { role?: string; content?: string; seq?: number }[] | undefined,
  pending: LiveLine[],
): TranscriptLine[] {
  const lines: TranscriptLine[] = [];
  const seen = new Set<string>();
  for (const message of messages || []) {
    const text = (message.content || "").trim();
    if (!text) continue;
    const role = message.role === "assistant" ? "tutor" : "child";
    const seq = typeof message.seq === "number" ? message.seq : undefined;
    const key = seq === undefined ? `${role}:${text}` : `seq:${seq}`;
    if (seen.has(key)) continue;
    seen.add(key);
    lines.push(seq === undefined ? { role, text } : { role, text, seq });
  }
  for (const line of pending) {
    if (line.chatId !== chatId) continue;
    const key = `${line.role}:${line.text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    lines.push({ role: line.role, text: line.text });
  }
  return lines;
}
