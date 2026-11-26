/** Judge one finished harness chat. This is not on the live tutor path. */

import { generateText, jsonSchema, Output } from "ai";

import { api } from "@/lib/api";
import {
  acceptJudgeOutput,
  DIMENSIONS,
  evaluationFromJudge,
  judgePrompt,
  judgedAlready,
  TAGS,
  type JudgeEvaluation,
  type JudgeTurn,
  type SideCheck,
} from "@/lib/harness-judge";
import { isKcModel, missingKeyMessage, modelForCall } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";
import { readModelUsage } from "@/lib/model-usage";

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

type ChatForJudge = {
  run_cap_reached?: boolean;
  judge_model?: string;
  child?: { description?: string };
  turns?: { seq: number; intent?: string; child_text?: string; session_after?: { tutor_reply?: string } }[];
  evaluations?: { kind?: string; scores?: { length?: number } | null; child_realism?: number | null; error?: string; checks?: { side?: SideCheck[] } }[];
};

export async function judgeTranscript(input: {
  model?: string;
  child?: string;
  turns: JudgeTurn[];
  checks?: { side?: SideCheck[] };
}): Promise<JudgeEvaluation> {
  const requested = modelForCall(input.model || "");
  if (!isKcModel(requested)) {
    return evaluationFromJudge({ ok: false, error: "That model is not allowed.", judge_model: requested });
  }
  const missing = missingKeyMessage(requested);
  if (missing) return evaluationFromJudge({ ok: false, error: missing, judge_model: requested });
  const turns = input.turns || [];
  const prompt = turns.length
    ? judgePrompt({ child: input.child, turns })
    : [judgePrompt({ child: input.child, turns: [] }), "Transcript:\n"].join("\n\n");
  try {
    const result = await generateText({
      model: languageModel(requested),
      prompt,
      temperature: 0,
      output: Output.object({ schema: jsonSchema(schema) }),
    });
    const usage = readModelUsage(result.usage);
    const output = result.output as { scores?: []; tags?: []; child_realism?: number };
    const accepted = acceptJudgeOutput(output, { turns, checks: input.checks });
    return evaluationFromJudge({
      ok: true,
      ...accepted,
      judge_model: requested,
      usage,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "The judge failed.";
    return evaluationFromJudge({ ok: false, error: message, judge_model: requested });
  }
}

export async function judgeFinishedChat(chatId: string): Promise<JudgeEvaluation | null> {
  const detail = await api<ChatForJudge>(`/kc/harness/chats/${chatId}`);
  if (detail.run_cap_reached || judgedAlready(detail.evaluations)) return null;
  const turns: JudgeTurn[] = (detail.turns || []).map((turn) => ({
    seq: turn.seq,
    intent: turn.intent,
    child_text: turn.child_text,
    tutor_reply: turn.session_after?.tutor_reply || "",
  }));
  const checks = detail.evaluations?.find((item) => item.kind === "automatic")?.checks;
  const judged = await judgeTranscript({
    model: detail.judge_model || "gpt-6.1-sol",
    child: detail.child?.description || "",
    turns,
    checks,
  });
  await api(`/kc/harness/chats/${chatId}/evaluations`, {
    method: "POST",
    body: JSON.stringify(judged),
  });
  return judged;
}
