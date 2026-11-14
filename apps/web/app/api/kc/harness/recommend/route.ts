import { generateText, jsonSchema, Output } from "ai";

import {
  applyModelReplacements,
  draftPromptCards,
  drafterPrompt,
  recommendationMarkdown,
  writeRecommendationDoc,
  type DraftMaterials,
  type ModelDraft,
} from "@/lib/harness-draft";
import { isKcModel, missingKeyMessage, modelForCall } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";
import { readModelUsage } from "@/lib/model-usage";

export const runtime = "nodejs";
export const maxDuration = 60;

const RECOMMENDATION_DOC_FLAG = "docs/harness-prompt-recommendations.md";

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
          current_quote: { type: "string" },
          replacement: { type: "string" },
          shorter: { type: "string" },
          evidence_summary: { type: "string" },
        },
        required: ["current_quote", "replacement", "shorter", "evidence_summary"],
      },
    },
  },
  required: ["cards"],
};

export async function POST(req: Request) {
  let body: DraftMaterials & { model?: string };
  try {
    body = (await req.json()) as typeof body;
  } catch {
    return new Response("Expected JSON.", { status: 400 });
  }
  const requested = modelForCall(body.model || "");
  const modelName = requested || "gpt-6.1-sol";
  if (!isKcModel(modelName)) return new Response("That model is not allowed.", { status: 422 });
  const grounded = draftPromptCards(body);
  if (grounded.length === 0) {
    const findings = Array.isArray(body.findings) ? body.findings : body.findings?.findings;
    if (!findings || findings.length === 0) {
      return new Response("This run has no findings, so there is nothing to draft.", { status: 422 });
    }
    return new Response("This run has no stored tutor prompt to quote, so no card was drafted.", { status: 422 });
  }
  let cards = grounded;
  let drafter = "prompt-builder";
  let usage = readModelUsage(undefined);
  const missing = missingKeyMessage(modelName);
  if (!missing) {
    try {
      const result = await generateText({
        model: languageModel(modelName),
        prompt: drafterPrompt(body, grounded),
        temperature: 0.2,
        output: Output.object({ schema: jsonSchema(schema) }),
      });
      const output = result.output as { cards?: ModelDraft[] };
      cards = applyModelReplacements(grounded, output.cards ?? []);
      usage = readModelUsage(result.usage);
      drafter = modelName;
    } catch {
      cards = grounded;
      drafter = "prompt-builder";
    }
  }
  const runId = String(body.run_id || "");
  const wrote = writeRecommendationDoc(recommendationMarkdown(runId, cards));
  return Response.json({
    cards,
    usage,
    judge_model: modelName,
    drafter,
    recommendations_doc: wrote ? RECOMMENDATION_DOC_FLAG : "",
  });
}
