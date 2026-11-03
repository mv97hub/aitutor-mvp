import { openai } from "@ai-sdk/openai";
import { Output, convertToModelMessages, jsonSchema, streamText, type JSONSchema7, type UIMessage } from "ai";

import { api, apiBase } from "@/lib/api";
import type { StudioMessage } from "@/lib/studio";

export const runtime = "nodejs";
export const maxDuration = 60;

const MISSING_KEY =
  "OPENAI_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENAI_API_KEY to your real key, and restart the Next.js server.";

const ALLOWED_MODELS = new Set(["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"]);

type PromptBundle = {
  model: string;
  system_prompt: string;
  response_schema: JSONSchema7;
  temperature: number;
};

type CourseEdit = {
  reply?: string;
  patch?: { operations?: unknown[] } | null;
};

function rejectionReply(reason: string): string {
  return reason.trim();
}

function detailFrom(body: unknown, fallback: string): string {
  if (typeof body === "string" && body.trim()) return body;
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export async function POST(req: Request) {
  let body: { courseId?: string; content?: string };
  try {
    body = (await req.json()) as { courseId?: string; content?: string };
  } catch {
    return new Response("Expected JSON with courseId and content.", { status: 400 });
  }
  const courseId = body.courseId;
  const content = body.content?.trim() ?? "";
  if (!courseId) return new Response("courseId is required.", { status: 400 });
  if (!content) return new Response("content is required.", { status: 400 });

  if (!process.env.OPENAI_API_KEY?.trim()) {
    return new Response(MISSING_KEY, {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  let user: StudioMessage;
  try {
    user = await api<StudioMessage>(`/studio/courses/${courseId}/messages`, {
      method: "POST",
      body: JSON.stringify({ role: "user", content }),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not save that message.";
    return new Response(message, { status: 502 });
  }

  let bundle: PromptBundle;
  let history: StudioMessage[];
  try {
    bundle = await api<PromptBundle>(`/studio/courses/${courseId}/prompt`);
    history = await api<StudioMessage[]>(`/studio/courses/${courseId}/messages`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the course.";
    return new Response(message, { status: 502 });
  }

  if (!ALLOWED_MODELS.has(bundle.model)) {
    return new Response("That CreateCourse model is not allowed.", { status: 422 });
  }

  const uiMessages: UIMessage[] = history.map((message) => ({
    id: message.id,
    role: message.role,
    parts: [{ type: "text", text: message.content }],
  }));
  const modelMessages = await convertToModelMessages(uiMessages);

  let output: CourseEdit;
  try {
    const result = streamText({
      model: openai(bundle.model),
      output: Output.object({
        schema: jsonSchema(bundle.response_schema),
        name: "course_edit",
        description: "A reply and an optional typed patch addressed by code. No web search.",
      }),
      instructions: bundle.system_prompt,
      messages: modelMessages,
      temperature: bundle.temperature,
    });
    output = (await result.output) as CourseEdit;
  } catch (error) {
    const message = error instanceof Error ? error.message : "The model did not answer.";
    return new Response(message, { status: 502 });
  }

  const reply = typeof output.reply === "string" ? output.reply.trim() : "";
  const operations = output.patch && Array.isArray(output.patch.operations) ? output.patch.operations : [];
  const proposal = operations.length > 0 ? { operations } : null;
  let assistantText = reply || (proposal ? "Here is a change to accept." : "I don't have a change for the course yet.");

  let assistant: StudioMessage | null = null;
  if (proposal) {
    const saved = await fetch(`${apiBase()}/studio/courses/${courseId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "assistant", content: assistantText, proposal }),
      cache: "no-store",
    });
    const savedBody = await readBody(saved);
    if (saved.ok) {
      assistant = savedBody as StudioMessage;
    } else if (saved.status === 422) {
      assistantText = rejectionReply(detailFrom(savedBody, "That change was rejected."));
    } else {
      return new Response(detailFrom(savedBody, "Could not save the reply."), { status: 502 });
    }
  }

  if (!assistant) {
    try {
      assistant = await api<StudioMessage>(`/studio/courses/${courseId}/messages`, {
        method: "POST",
        body: JSON.stringify({ role: "assistant", content: assistantText }),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not save the reply.";
      return new Response(message, { status: 502 });
    }
  }

  return Response.json({ user, assistant });
}
