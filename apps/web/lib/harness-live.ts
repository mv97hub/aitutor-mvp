import type { LiveLine } from "./harness-runner.ts";

export type TranscriptLine = { role: "tutor" | "child"; text: string; seq: number };

const LIVE_WINDOW = 40;

function assignSeq(preferred: number | undefined, used: Set<number>, maxSeq: number): { seq: number; maxSeq: number } {
  if (typeof preferred === "number" && preferred > 0 && !used.has(preferred)) {
    used.add(preferred);
    return { seq: preferred, maxSeq: Math.max(maxSeq, preferred) };
  }
  const seq = maxSeq + 1;
  used.add(seq);
  return { seq, maxSeq: seq };
}

/** Session messages are the record. A stored seq is the turn number, not a renumbered list index. */
export function transcriptForChat(
  chatId: string,
  messages: { role?: string; content?: string; seq?: number }[] | undefined,
  pending: LiveLine[],
): TranscriptLine[] {
  const lines: TranscriptLine[] = [];
  const seen = new Set<string>();
  const used = new Set<number>();
  let maxSeq = 0;
  for (const message of messages || []) {
    const text = (message.content || "").trim();
    if (!text) continue;
    const role = message.role === "assistant" ? "tutor" : "child";
    const seq = typeof message.seq === "number" ? message.seq : undefined;
    const key = seq === undefined ? `${role}:${text}` : `seq:${seq}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const assigned = assignSeq(message.seq, used, maxSeq);
    maxSeq = assigned.maxSeq;
    lines.push({ role, text, seq: assigned.seq });
  }
  for (const line of pending) {
    if (line.chatId !== chatId) continue;
    const key = `${line.role}:${line.text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const assigned = assignSeq(line.seq, used, maxSeq);
    maxSeq = assigned.maxSeq;
    lines.push({ role: line.role, text: line.text, seq: assigned.seq });
  }
  return lines;
}

/** A short window of the latest lines. Each line keeps its own sequence. */
export function recentLines(lines: TranscriptLine[], limit = LIVE_WINDOW): TranscriptLine[] {
  if (limit < 1 || lines.length <= limit) return lines;
  return lines.slice(lines.length - limit);
}
