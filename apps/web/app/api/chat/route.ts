import { openai } from "@ai-sdk/openai";
import {
  Output,
  convertToModelMessages,
  createUIMessageStream,
  createUIMessageStreamResponse,
  streamText,
  type UIMessage,
} from "ai";
import { z } from "zod";

import { api } from "@/lib/api";
import { KICKOFF } from "@/lib/kickoff";
import { openaiModelName } from "@/lib/model";
import { buildSystemPrompt } from "@/lib/prompt";
import type { LessonContext } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 60;

const MISSING_KEY =
  "OPENAI_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENAI_API_KEY to your real key, and restart the Next.js server.";

const turnScore = z.object({
  reply: z.string(),
  rubric_met: z.array(z.string()),
  misconception: z.string().nullable(),
  hint_tier: z.enum(["nudge", "analogy", "scaffold"]),
  advance: z.boolean(),
});

type WidgetBody = {
  choice?: string | string[];
  explanation?: string;
};

function textOf(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();
}

export async function POST(req: Request) {
  let body: { messages?: UIMessage[]; sessionId?: string; widget?: WidgetBody };
  try {
    body = (await req.json()) as { messages?: UIMessage[]; sessionId?: string; widget?: WidgetBody };
  } catch {
    return new Response("Expected JSON with sessionId and messages.", { status: 400 });
  }

  const sessionId = body.sessionId;
  const messages = body.messages ?? [];
  if (!sessionId) {
    return new Response("sessionId is required.", { status: 400 });
  }

  if (body.widget && body.widget.choice != null) {
    try {
      const graded = await api<{ ok: boolean; reason?: string }>(`/sessions/${sessionId}/grade-widget`, {
        method: "POST",
        body: JSON.stringify({
          choice: body.widget.choice,
          explanation: body.widget.explanation ?? "",
        }),
      });
      if (!graded.ok) {
        return new Response(graded.reason || "That choice could not be graded.", { status: 400 });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not grade that choice.";
      return new Response(message, { status: 502 });
    }
  }

  if (!process.env.OPENAI_API_KEY?.trim()) {
    return new Response(MISSING_KEY, {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  const lastUser = [...messages].reverse().find((message) => message.role === "user");
  if (lastUser) {
    const content = textOf(lastUser);
    if (content) {
      try {
        await api(`/sessions/${sessionId}/messages`, {
          method: "POST",
          body: JSON.stringify({
            role: "user",
            content,
            client_id: lastUser.id,
          }),
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Could not save the message.";
        return new Response(message, { status: 502 });
      }
    }
  }

  const kickoff =
    messages.filter((message) => message.role === "user").length === 1 &&
    lastUser != null &&
    textOf(lastUser) === KICKOFF;

  let context: LessonContext;
  try {
    context = await api<LessonContext>(`/sessions/${sessionId}/context`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the lesson.";
    return new Response(message, { status: 502 });
  }

  const result = streamText({
    model: openai(openaiModelName()),
    output: Output.object({
      schema: turnScore,
      name: "turn_score",
      description: "Rubric rows met, misconception if any, hint tier, and the tutor reply.",
    }),
    instructions: buildSystemPrompt(context, { kickoff }),
    messages: await convertToModelMessages(messages),
    temperature: 0.4,
  });

  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      const id = "tutor-reply";
      writer.write({ type: "text-start", id });
      let sent = "";
      for await (const partial of result.partialOutputStream) {
        const reply = typeof partial?.reply === "string" ? partial.reply : "";
        if (!reply.startsWith(sent)) continue;
        const delta = reply.slice(sent.length);
        if (delta) writer.write({ type: "text-delta", id, delta });
        sent = reply;
      }
      writer.write({ type: "text-end", id });
      const finalScore = await result.output;
      if (!kickoff) {
        try {
          await api(`/sessions/${sessionId}/turn-score`, {
            method: "POST",
            body: JSON.stringify({
              rubric_met: finalScore.rubric_met,
              misconception: finalScore.misconception,
              hint_tier: finalScore.hint_tier,
              advance: finalScore.advance,
            }),
          });
        } catch (error) {
          console.error("Could not store the turn score", error);
        }
      }
      if (lastUser && sent.trim()) {
        try {
          await api(`/sessions/${sessionId}/messages`, {
            method: "POST",
            body: JSON.stringify({
              role: "assistant",
              content: sent.trim(),
              client_id: `${lastUser.id}:assistant`,
            }),
          });
        } catch (error) {
          console.error("Could not store the tutor reply", error);
        }
      }
    },
  });

  return createUIMessageStreamResponse({ stream });
}
