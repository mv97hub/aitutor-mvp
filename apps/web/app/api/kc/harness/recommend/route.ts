import { generateText, jsonSchema, Output } from "ai";

import { ensureSimplification, type RecommendationCard } from "@/lib/harness";
import { isKcModel, missingKeyMessage, modelForCall } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";
import { readModelUsage } from "@/lib/model-usage";

export const runtime = "nodejs";
export const maxDuration = 60;

const schema = {
  type: "object",
  additionalProperties: false,
  properties: {
    cards: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          title: { type: "string" },
          cause_class: { type: "string" },
          place: { type: "string" },
          kind: { type: "string", enum: ["setting", "reword", "remove", "add"] },
          prompt_direction: { type: "string", enum: ["shorter", "longer", "same"] },
          proposed_text: { type: "string" },
          risk: { type: "string" },
          confidence: { type: "string" },
          evidence_summary: { type: "string" },
        },
        required: ["title", "cause_class", "place", "kind", "prompt_direction", "proposed_text", "risk", "confidence", "evidence_summary"],
      },
    },
  },
  required: ["cards"],
};

export async function POST(req: Request) {
  let body: { model?: string; findings?: unknown };
  try {
    body = (await req.json()) as typeof body;
  } catch {
    return new Response("Expected JSON.", { status: 400 });
  }
  const modelName = modelForCall(body.model || "");
  if (!isKcModel(modelName)) return new Response("That model is not allowed.", { status: 422 });
  const missing = missingKeyMessage(modelName);
  if (missing) return new Response(missing, { status: 503 });
  const prompt = [
    "Draft recommendation cards for a tutoring prompt. A person will review every card. Nothing is applied automatically.",
    "Look for a line to cut or shorten before you look for a line to add. A batch that only proposes additions is incomplete.",
    "kind is setting, reword, remove, or add. prompt_direction is shorter, longer, or same.",
    "Say whether the prompt gets shorter or longer. Adding text has to beat the shorter option.",
    `Findings:\n${JSON.stringify(body.findings ?? [], null, 2)}`,
  ].join("\n\n");
  try {
    const result = await generateText({
      model: languageModel(modelName),
      prompt,
      temperature: 0.2,
      output: Output.object({ schema: jsonSchema(schema) }),
    });
    const output = result.output as { cards?: RecommendationCard[] };
    const drafted = (output.cards ?? []).map((card) => ({
      title: card.title,
      cause_class: card.cause_class,
      place: card.place,
      kind: card.kind,
      prompt_direction: card.prompt_direction,
      proposed: { text: (card as { proposed_text?: string }).proposed_text || "" },
      risk: card.risk,
      confidence: card.confidence,
      evidence: { summary: (card as { evidence_summary?: string }).evidence_summary || "" },
    }));
    const cards = ensureSimplification(drafted);
    return Response.json({ cards, usage: readModelUsage(result.usage), judge_model: modelName });
  } catch (error) {
    const message = error instanceof Error ? error.message : "The drafter failed.";
    return new Response(message, { status: 502 });
  }
}
