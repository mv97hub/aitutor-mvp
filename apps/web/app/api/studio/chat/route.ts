import { openai } from "@ai-sdk/openai";
import { Output, convertToModelMessages, jsonSchema, streamText, type JSONSchema7, type UIMessage } from "ai";

import { api, apiBase } from "@/lib/api";
import type { StudioMessage } from "@/lib/studio";
import { detailFrom, plainFailure, replyIfUnwritten, settleModelResult } from "@/lib/studio-chat";

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

  let user: StudioMessage | undefined;
  try {
    const turn = await api<{
      wrote: boolean;
      handled?: boolean;
      user?: StudioMessage;
      assistant?: StudioMessage;
      course?: unknown;
    }>(`/studio/courses/${courseId}/turns`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
    user = turn.user;
    if (turn.handled && turn.user && turn.assistant) {
      return Response.json({
        user: turn.user,
        assistant: turn.assistant,
        course: turn.course,
        wrote: false,
        handled: true,
      });
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not read that message.";
    return new Response(message, { status: 502 });
  }

  if (!process.env.OPENAI_API_KEY?.trim()) {
    try {
      const drafted = await api<{ assistant: StudioMessage; course?: unknown }>(
        `/studio/courses/${courseId}/fallback`,
        {
          method: "POST",
          body: JSON.stringify({ content }),
        },
      );
      return Response.json({
        user,
        assistant: drafted.assistant,
        course: drafted.course,
        wrote: false,
        handled: true,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not draft that reply.";
      return new Response(message, { status: 502 });
    }
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

  let assistantText = "";
  let proposal: { operations: unknown[] } | null = null;
  let assistant: StudioMessage | null = null;
  let note = "";

  for (let attempt = 0; attempt < 2 && !assistant; attempt++) {
    let output: CourseEdit;
    try {
      const result = streamText({
        model: openai(bundle.model),
        output: Output.object({
          schema: jsonSchema(bundle.response_schema),
          name: "course_edit",
          description: "A reply and an optional typed patch addressed by code. No web search.",
        }),
        instructions: note ? `${bundle.system_prompt}\n${note}` : bundle.system_prompt,
        messages: modelMessages,
        temperature: bundle.temperature,
      });
      output = (await result.output) as CourseEdit;
    } catch (error) {
      const decision = settleModelResult({
        attempt,
        failure: error instanceof Error ? error.message : "The model did not answer.",
        kind: "schema",
        reply: "",
        operations: [],
      });
      if (decision.action === "retry") {
        note = decision.note;
        continue;
      }
      return new Response(decision.action === "banner" ? decision.text : plainFailure(error), { status: 502 });
    }

    const reply = typeof output.reply === "string" ? output.reply : "";
    const operations = output.patch && Array.isArray(output.patch.operations) ? output.patch.operations : [];
    const decision = settleModelResult({
      attempt,
      failure: null,
      kind: null,
      reply,
      operations,
    });
    if (decision.action !== "save") {
      return new Response("The model reply could not be read.", { status: 502 });
    }
    assistantText = replyIfUnwritten(decision.text);
    proposal = decision.proposal;
    if (!proposal) break;

    const saved = await fetch(`${apiBase()}/studio/courses/${courseId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "assistant", content: assistantText, proposal }),
      cache: "no-store",
    });
    const savedBody = await readBody(saved);
    if (saved.ok) {
      assistant = savedBody as StudioMessage;
      break;
    }
    const failureKind = saved.status === 422 ? "checker" : "transport";
    const failed = settleModelResult({
      attempt,
      failure: detailFrom(savedBody, saved.status === 422 ? "That change was rejected." : "Could not save the reply."),
      kind: failureKind,
      reply: assistantText,
      operations,
    });
    if (failed.action === "retry") {
      note = failed.note;
      proposal = null;
      continue;
    }
    if (failed.action === "banner") {
      return new Response(failed.text, { status: 502 });
    }
    assistantText = failed.text;
    proposal = null;
    break;
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
