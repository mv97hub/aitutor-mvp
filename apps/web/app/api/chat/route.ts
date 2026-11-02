import { openai } from "@ai-sdk/openai";
import {
  Output,
  convertToModelMessages,
  createUIMessageStream,
  createUIMessageStreamResponse,
  jsonSchema,
  streamText,
  wrapLanguageModel,
  type JSONSchema7,
  type LanguageModelMiddleware,
  type UIMessage,
} from "ai";

import { api } from "@/lib/api";
import { KICKOFF } from "@/lib/kickoff";
import { openaiModelName } from "@/lib/model";
import type { PromptBundle } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 60;

const MISSING_KEY =
  "OPENAI_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENAI_API_KEY to your real key, and restart the Next.js server.";

type TurnScore = {
  reply: string;
  rubric_met: string[];
  misconception: string | null;
  hint_tier: "nudge" | "analogy" | "scaffold";
  advance: boolean;
};

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

function jsonSafe(value: unknown): unknown {
  return JSON.parse(
    JSON.stringify(value, (_key, item: unknown) => {
      if (typeof item === "bigint") return item.toString();
      if (item instanceof Uint8Array) return Buffer.from(item).toString("base64");
      return item;
    }),
  );
}

type ModelCall = {
  prompt?: Array<{ role?: string; content?: unknown }>;
  temperature?: number;
  maxOutputTokens?: number;
  topP?: number;
  topK?: number;
  presencePenalty?: number;
  frequencyPenalty?: number;
  stopSequences?: string[];
  seed?: number;
  responseFormat?: unknown;
  tools?: unknown;
  toolChoice?: unknown;
  reasoning?: string;
};

function textOfContent(content: unknown) {
  return typeof content === "string" ? content : JSON.stringify(content);
}

function requestForCall(params: ModelCall, fallbackSystem: string) {
  const prompt = Array.isArray(params.prompt) ? params.prompt : [];
  const systemParts = prompt
    .filter((message) => message.role === "system")
    .map((message) => textOfContent(message.content))
    .filter((text) => text.length > 0);
  let systemPrompt = systemParts.join("\n\n");
  if (fallbackSystem && !systemPrompt.includes(fallbackSystem)) {
    systemPrompt = systemPrompt ? `${fallbackSystem}\n\n${systemPrompt}` : fallbackSystem;
  }
  const messages = prompt.filter((message) => message.role !== "system");
  const extras: Record<string, unknown> = {};
  if (params.temperature != null) extras.temperature = params.temperature;
  if (params.maxOutputTokens != null) extras.maxOutputTokens = params.maxOutputTokens;
  if (params.topP != null) extras.topP = params.topP;
  if (params.topK != null) extras.topK = params.topK;
  if (params.presencePenalty != null) extras.presencePenalty = params.presencePenalty;
  if (params.frequencyPenalty != null) extras.frequencyPenalty = params.frequencyPenalty;
  if (params.stopSequences != null) extras.stopSequences = params.stopSequences;
  if (params.seed != null) extras.seed = params.seed;
  if (params.responseFormat != null) extras.responseFormat = params.responseFormat;
  if (params.tools != null) extras.tools = params.tools;
  if (params.toolChoice != null) extras.toolChoice = params.toolChoice;
  if (params.reasoning != null && params.reasoning !== "provider-default") extras.reasoning = params.reasoning;
  const storedMessages = Object.keys(extras).length > 0 ? [...messages, { role: "request", content: extras }] : messages;
  return {
    system_prompt: systemPrompt || fallbackSystem,
    messages: jsonSafe(storedMessages),
  };
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

  let turnMessageId: string | null = null;
  const lastUser = [...messages].reverse().find((message) => message.role === "user");
  if (lastUser) {
    const content = textOf(lastUser);
    if (content) {
      try {
        const saved = await api<{ id: string }>(`/sessions/${sessionId}/messages`, {
          method: "POST",
          body: JSON.stringify({
            role: "user",
            content,
            client_id: lastUser.id,
          }),
        });
        turnMessageId = saved.id;
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

  let bundle: PromptBundle;
  try {
    bundle = await api<PromptBundle>(
      `/sessions/${sessionId}/prompt?kickoff=${kickoff ? "true" : "false"}`,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the prompt.";
    return new Response(message, { status: 502 });
  }

  const system = bundle.system_prompt;
  const modelMessages = await convertToModelMessages(messages);
  const modelName = openaiModelName();
  const captureRequest: LanguageModelMiddleware = {
    specificationVersion: "v4",
    wrapStream: async ({ doStream, params, model }) => {
      const request = requestForCall(params, system);
      const messagesForStore = Array.isArray(request.messages) ? request.messages : [];
      try {
        await api(`/sessions/${sessionId}/model-prompts`, {
          method: "POST",
          body: JSON.stringify({
            system_prompt: request.system_prompt,
            messages: messagesForStore,
            model: model.modelId || modelName,
            message_id: turnMessageId,
          }),
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Could not store the prompt.";
        throw new Error(message);
      }
      return doStream();
    },
  };

  const result = streamText({
    model: wrapLanguageModel({ model: openai(modelName), middleware: captureRequest }),
    output: Output.object({
      schema: jsonSchema(bundle.response_schema as JSONSchema7),
      name: "turn_score",
      description: "Rubric rows met, misconception if any, hint tier, and the tutor reply.",
    }),
    instructions: system,
    messages: modelMessages,
    temperature: bundle.temperature,
  });

  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      const id = "tutor-reply";
      writer.write({ type: "text-start", id });
      let sent = "";
      for await (const partial of result.partialOutputStream) {
        const piece = partial as Partial<TurnScore>;
        const reply = typeof piece.reply === "string" ? piece.reply : "";
        if (!reply.startsWith(sent)) continue;
        const delta = reply.slice(sent.length);
        if (delta) writer.write({ type: "text-delta", id, delta });
        sent = reply;
      }
      writer.write({ type: "text-end", id });
      const finalScore = (await result.output) as TurnScore;
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
