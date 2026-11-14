import type { LiveLine } from "./harness-runner.ts";

export type TranscriptLine = { role: "tutor" | "child"; text: string };

/** Session messages are the record. Lines the open tab has already spoken are added until the session stores them. */
export function transcriptForChat(
  chatId: string,
  messages: { role?: string; content?: string }[] | undefined,
  pending: LiveLine[],
): TranscriptLine[] {
  const lines: TranscriptLine[] = [];
  const seen = new Set<string>();
  for (const message of messages || []) {
    const text = (message.content || "").trim();
    if (!text) continue;
    const role = message.role === "assistant" ? "tutor" : "child";
    const key = `${role}:${text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    lines.push({ role, text });
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
