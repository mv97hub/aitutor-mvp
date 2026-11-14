import { generateText } from "ai";

import { childPrompt } from "@/lib/harness-policy";
import type { Intent, Traits } from "@/lib/harness-policy";
import { isKcModel, missingKeyMessage, modelForCall } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";
import { readModelUsage } from "@/lib/model-usage";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(req: Request) {
  let body: {
    model?: string;
    intent?: string;
    description?: string;
    traits?: Traits;
    expected?: string;
    wrongMove?: string;
    lastTutor?: string;
    interests?: string;
    text?: string;
    needsModel?: boolean;
  };
  try {
    body = (await req.json()) as typeof body;
  } catch {
    return new Response("Expected JSON.", { status: 400 });
  }
  if (body.needsModel === false && typeof body.text === "string" && body.text.trim()) {
    return Response.json({ text: body.text.trim(), intent: body.intent || "", input_tokens: 0, output_tokens: 0, model: "" });
  }
  const requested = typeof body.model === "string" ? body.model.trim() : "";
  const modelName = modelForCall(requested);
  if (!requested || !isKcModel(modelName)) return new Response("That model is not allowed.", { status: 422 });
  const missing = missingKeyMessage(modelName);
  if (missing) return new Response(missing, { status: 503 });
  try {
    const result = await generateText({
      model: languageModel(modelName),
      prompt: childPrompt({
        description: body.description || "A test child.",
        traits: body.traits || {},
        intent: (body.intent || "answer_part") as Intent,
        expected: body.expected,
        wrongMove: body.wrongMove,
        lastTutor: body.lastTutor || "",
        interests: body.interests,
      }),
      temperature: 0.9,
    });
    const usage = readModelUsage(result.usage);
    const text = result.text.trim().slice(0, 2000);
    if (!text) return new Response("The child model did not write a message.", { status: 502 });
    return Response.json({ text, intent: body.intent || "", model: modelName, ...usage });
  } catch (error) {
    const message = error instanceof Error ? error.message : "The child model failed.";
    return new Response(message, { status: 502 });
  }
}
