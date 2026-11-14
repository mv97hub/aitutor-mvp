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

function blockNames(findings: unknown): string {
  const labels: string[] = [];
  if (Array.isArray(findings)) {
    for (const finding of findings) {
      if (!finding || typeof finding !== "object") continue;
      const label = String((finding as { block_label?: string }).block_label || "").trim();
      if (label && !labels.includes(label)) labels.push(label);
    }
  }
  return labels.join(", ") || "an unknown block";
}

function stampBlockType(cards: RecommendationCard[], findings: unknown): RecommendationCard[] {
  const named = blockNames(findings);
  return cards.map((card) => {
    const evidence = { ...(card.evidence || {}), block_type: named };
    const blob = `${card.title} ${card.place} ${evidence.summary || ""}`;
    const already = named.split(", ").every((label) => blob.includes(label));
    return {
      ...card,
      block_type: named,
      title: already ? card.title : `${card.title} on ${named}`,
      place: already ? card.place : `${card.place} Block type: ${named}.`,
      evidence,
    };
  });
}

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
    "Every card title and place must name the finding's block_label, the block type the issue happened on.",
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
    const cards = stampBlockType(ensureSimplification(drafted), body.findings);
    return Response.json({ cards, usage: readModelUsage(result.usage), judge_model: modelName });
  } catch (error) {
    const message = error instanceof Error ? error.message : "The drafter failed.";
    return new Response(message, { status: 502 });
  }
}
