import { generateText, jsonSchema, Output } from "ai";

import {
  acceptJudgeOutput,
  DIMENSIONS,
  judgePrompt,
  RUBRIC_VERSION,
  TAGS,
  type JudgeTurn,
  type SideCheck,
} from "@/lib/harness-judge";
import { isKcModel, missingKeyMessage, modelForCall } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";
import { readModelUsage } from "@/lib/model-usage";

export const runtime = "nodejs";
export const maxDuration = 60;

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

type JudgeBody = {
  model?: string;
  transcript?: string;
  child?: string;
  turns?: JudgeTurn[];
  checks?: { side?: SideCheck[] };
};

export async function POST(req: Request) {
  let body: JudgeBody;
  try {
    body = (await req.json()) as JudgeBody;
  } catch {
    return new Response("Expected JSON.", { status: 400 });
  }
  const modelName = modelForCall(body.model || "");
  if (!isKcModel(modelName)) return new Response("That model is not allowed.", { status: 422 });
  const missing = missingKeyMessage(modelName);
  if (missing) return new Response(missing, { status: 503 });
  const turns = Array.isArray(body.turns) ? body.turns : [];
  const prompt = turns.length
    ? judgePrompt({ child: body.child, turns })
    : [
        judgePrompt({ child: body.child, turns: [] }),
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
    const output = result.output as { scores?: []; tags?: []; child_realism?: number };
    const accepted = acceptJudgeOutput(output, { turns, checks: body.checks });
    return Response.json({
      ...accepted,
      rubric_version: RUBRIC_VERSION,
      judge_model: modelName,
      usage,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "The judge failed.";
    return new Response(message, { status: 502 });
  }
}
