import { generateText, jsonSchema, Output } from "ai";

import { isKcModel, missingKeyMessage, modelForCall } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";
import { readModelUsage } from "@/lib/model-usage";

export const runtime = "nodejs";
export const maxDuration = 60;

const DIMENSIONS = [
  "teaching_quality",
  "correctness",
  "engagement",
  "side_remarks",
  "age_fit",
  "pacing",
  "feedback",
  "scoring_fairness",
  "emotional_attunement",
  "safety",
  "getting_stuck",
  "natural_conversation",
  "closing",
  "child_realism",
];

const TAGS = [
  "ignored_question",
  "too_long",
  "vocabulary_too_hard",
  "repeated_itself",
  "gave_away_answer",
  "generic_praise",
  "missed_boredom",
  "missed_frustration",
  "abrupt_return",
  "talked_down",
  "factual_error",
];

const schema = {
  type: "object",
  additionalProperties: false,
  properties: {
    scores: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          dimension: { type: "string", enum: DIMENSIONS },
          score: { type: "integer" },
          quote: { type: "string" },
          turn: { type: "integer" },
        },
        required: ["dimension", "score", "quote", "turn"],
      },
    },
    tags: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          tag: { type: "string", enum: TAGS },
          turn: { type: "integer" },
          quote: { type: "string" },
        },
        required: ["tag", "turn", "quote"],
      },
    },
    child_realism: { type: "integer" },
  },
  required: ["scores", "tags", "child_realism"],
};

export async function POST(req: Request) {
  let body: { model?: string; transcript?: string; child?: string };
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
    "Score this tutoring chat from 1 to 5 on every dimension. Quote the turn you used. Use only the fixed tags.",
    "child_realism scores the test child, not the tutor. A low score means the child did not match the description.",
    `Child: ${body.child || ""}`,
    `Transcript:\n${body.transcript || ""}`,
  ].join("\n\n");
  try {
    const result = await generateText({
      model: languageModel(modelName),
      prompt,
      temperature: 0,
      output: Output.object({ schema: jsonSchema(schema) }),
    });
    const usage = readModelUsage(result.usage);
    return Response.json({
      ...(result.output as object),
      rubric_version: "1",
      judge_model: modelName,
      usage,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "The judge failed.";
    return new Response(message, { status: 502 });
  }
}
