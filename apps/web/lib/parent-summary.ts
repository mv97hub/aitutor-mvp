import type { ParentChatDetail } from "./parent.ts";

export type ParentSummary = {
  summary: string;
  talking_points: string[];
};

/** Strict structured output: every key is required and nothing else is allowed. */
export const PARENT_SUMMARY_SCHEMA = {
  type: "object",
  properties: {
    summary: {
      type: "string",
      description: "Two to four short sentences for a parent: what the child worked on and where they got stuck.",
    },
    talking_points: {
      type: "array",
      description: "Three to five things the parent could say or ask the child in conversation.",
      items: { type: "string" },
    },
  },
  required: ["summary", "talking_points"],
  additionalProperties: false,
} as const;

export const PARENT_SUMMARY_INSTRUCTIONS = [
  "You write a short note for a parent about one chat their child had with an AI tutor.",
  "Use plain, warm words. No jargon, no scores talk, no mention of prompts, models, or settings.",
  "Say what the child worked on, what they got right, and where they got stuck or unsure.",
  "Use only what is in the chat. Do not invent facts. If the chat is short, say so.",
  "Then give three to five talking points the parent can use in conversation: a question to ask, something to praise, or a small idea to try together.",
  "Write each talking point as one friendly sentence the parent could say out loud.",
  "Refer to the child by first name. Address the parent as you.",
].join("\n");

export const PARENT_SUMMARY_PROMPT =
  "Here is the chat. Return the summary object: a short summary for the parent, then the talking points.";

/** Long chats keep their most recent lines so the model sees where the child ended up. */
export const TRANSCRIPT_LIMIT = 12000;

function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || "The child";
}

export function transcriptText(
  chat: Pick<ParentChatDetail, "messages" | "student" | "component" | "course" | "status">,
  limit: number = TRANSCRIPT_LIMIT,
): string {
  const child = firstName(chat.student.display_name);
  const lines = [...chat.messages]
    .sort((a, b) => a.seq - b.seq)
    .map((message) => `${message.role === "user" ? child : "Tutor"}: ${message.content.trim()}`);
  let text = lines.join("\n");
  if (text.length > limit) {
    text = `…\n${text.slice(text.length - limit)}`;
  }
  const status = chat.status === "completed" ? "finished" : "still in progress";
  return [
    `Child: ${child}`,
    `Course: ${chat.course.title}`,
    `Topic: ${chat.component.title} (${status})`,
    "",
    text,
  ].join("\n");
}

export function parseParentSummary(value: unknown): ParentSummary | null {
  if (!value || typeof value !== "object") return null;
  const row = value as { summary?: unknown; talking_points?: unknown };
  const summary = typeof row.summary === "string" ? row.summary.trim() : "";
  if (!summary) return null;
  const points = Array.isArray(row.talking_points)
    ? row.talking_points
        .map((item) => (typeof item === "string" ? item.trim() : ""))
        .filter(Boolean)
        .slice(0, 6)
    : [];
  return { summary, talking_points: points };
}
