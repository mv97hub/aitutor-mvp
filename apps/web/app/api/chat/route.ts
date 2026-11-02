import { openai } from "@ai-sdk/openai";
import {
  convertToModelMessages,
  createUIMessageStreamResponse,
  isStepCount,
  streamText,
  toUIMessageStream,
  tool,
  type UIMessage,
} from "ai";
import { z } from "zod";

import { api } from "@/lib/api";
import { KICKOFF } from "@/lib/kickoff";
import { buildSystemPrompt } from "@/lib/prompt";
import type { LessonContext } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 60;

const MISSING_KEY =
  "OPENAI_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENAI_API_KEY to your real key, and restart the Next.js server.";

function textOf(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();
}

export async function POST(req: Request) {
  if (!process.env.OPENAI_API_KEY?.trim()) {
    return new Response(MISSING_KEY, {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  let body: { messages?: UIMessage[]; sessionId?: string };
  try {
    body = (await req.json()) as { messages?: UIMessage[]; sessionId?: string };
  } catch {
    return new Response("Expected JSON with sessionId and messages.", { status: 400 });
  }

  const sessionId = body.sessionId;
  const messages = body.messages ?? [];
  if (!sessionId) {
    return new Response("sessionId is required.", { status: 400 });
  }

  let context: LessonContext;
  try {
    context = await api<LessonContext>(`/sessions/${sessionId}/context`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the lesson.";
    return new Response(message, { status: 502 });
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

  const modelName = process.env.OPENAI_MODEL?.trim() || "gpt-4o-mini";
  const result = streamText({
    model: openai(modelName),
    instructions: buildSystemPrompt(context, { kickoff }),
    messages: await convertToModelMessages(messages),
    stopWhen: isStepCount(8),
    temperature: 0.4,
    tools: {
      get_current_step: tool({
        description:
          "Read the current topic and checkpoint from the lesson record. Use this instead of guessing the syllabus.",
        inputSchema: z.object({}),
        execute: async () => api(`/sessions/${sessionId}/current-step`),
      }),
      record_checkpoint_result: tool({
        description:
          "Record a score for the current checkpoint only. score is an integer from 0 to 100. passed is true only when the pass criteria are met. feedback is one or two sentences the student can read. The newest result is the one that counts.",
        inputSchema: z.object({
          score: z.number().int().min(0).max(100),
          passed: z.boolean(),
          feedback: z.string().min(1).max(2000),
        }),
        execute: async (input) =>
          api(`/sessions/${sessionId}/checkpoint-results`, {
            method: "POST",
            body: JSON.stringify(input),
          }),
      }),
      advance_checkpoint: tool({
        description:
          "Move to the next checkpoint after a finished teach step, or after the current practice or quiz has a passing result. Refuses to leave a quiz or practice step that has not passed.",
        inputSchema: z.object({}),
        execute: async () => api(`/sessions/${sessionId}/advance`, { method: "POST" }),
      }),
    },
  });

  return createUIMessageStreamResponse({
    stream: toUIMessageStream({
      stream: result.stream,
      onEnd: async ({ responseMessage, isAborted }) => {
        if (isAborted || !responseMessage || !lastUser) return;
        const text = responseMessage.parts
          .filter((part) => part.type === "text")
          .map((part) => part.text)
          .join("\n")
          .trim();
        if (!text) return;
        try {
          await api(`/sessions/${sessionId}/messages`, {
            method: "POST",
            body: JSON.stringify({
              role: "assistant",
              content: text,
              client_id: `${lastUser.id}:assistant`,
            }),
          });
        } catch (error) {
          console.error("Could not store the tutor reply", error);
        }
      },
    }),
  });
}
