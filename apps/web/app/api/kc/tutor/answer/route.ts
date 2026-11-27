import { generateText, jsonSchema, Output, wrapLanguageModel, type LanguageModelMiddleware } from "ai";

import { api, ApiError } from "@/lib/api";
import { judgeModelForCall } from "@/lib/graph2";
import type { KcTutorSession } from "@/lib/kc";
import { languageModel } from "@/lib/language-model";
import { isKcModel, kcModel, missingKeyMessage, modelForCall } from "@/lib/kc-models";
import { readModelUsage, type ModelUsageCounts } from "@/lib/model-usage";
import { requestForCall, type ModelCall } from "@/lib/stored-prompt";
import { finishSavedTurn, newTutorMessageId } from "@/lib/tutor-turn";

export const runtime = "nodejs";
export const maxDuration = 60;

type TurnBundle = KcTutorSession & {
  replayed?: boolean;
  system_prompt: string;
  response_schema: Record<string, unknown>;
  temperature: number;
  user_message?: string;
};

type Decision = {
  reply: string;
  decision: string;
  substep_passed: boolean;
  block_complete: boolean;
  generated_mcq: Record<string, unknown> | null;
  rubric_met: string[];
  misconception: string | null;
  hint_tier: string;
  help_requested: boolean;
  off_course: boolean;
  ready_to_move_on: boolean;
  affect: string;
  confidence: string;
  score_justification: string;
  what_was_strong: string;
  what_to_work_on: string;
  safety_flag: string;
};

type StoredCall = {
  system_prompt: string;
  messages: unknown;
  model: string;
};

function replyUnreadable(reply: string, errorMessage = ""): boolean {
  const text = reply.trim();
  if (!errorMessage) return !text || /^[.…·\s]+$/.test(text);
  const low = errorMessage.toLowerCase();
  return (
    low.includes("no object generated") ||
    low.includes("could not parse") ||
    low.includes("did not write a reply")
  );
}

function blankDecision(): Decision & { reply_unreadable: true } {
  return {
    reply: "",
    decision: "stay",
    substep_passed: false,
    block_complete: false,
    generated_mcq: null,
    rubric_met: [],
    misconception: null,
    hint_tier: "nudge",
    help_requested: false,
    off_course: false,
    ready_to_move_on: false,
    affect: "engaged",
    confidence: "ok",
    score_justification: "",
    what_was_strong: "",
    what_to_work_on: "",
    safety_flag: "none",
    reply_unreadable: true,
  };
}

function asDecision(value: unknown): Decision | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Partial<Decision>;
  if (typeof row.reply !== "string" || typeof row.decision !== "string") return null;
  const generated = row.generated_mcq;
  return {
    reply: row.reply,
    decision: row.decision,
    substep_passed: Boolean(row.substep_passed),
    block_complete: Boolean(row.block_complete),
    generated_mcq:
      generated && typeof generated === "object" && !Array.isArray(generated)
        ? (generated as Record<string, unknown>)
        : null,
    rubric_met: Array.isArray(row.rubric_met) ? row.rubric_met.map(String) : [],
    misconception: typeof row.misconception === "string" ? row.misconception : null,
    hint_tier: typeof row.hint_tier === "string" ? row.hint_tier : "nudge",
    help_requested: Boolean(row.help_requested),
    off_course: Boolean(row.off_course),
    ready_to_move_on: row.ready_to_move_on === true,
    affect: typeof row.affect === "string" ? row.affect : "engaged",
    confidence: typeof row.confidence === "string" ? row.confidence : "ok",
    score_justification: typeof row.score_justification === "string" ? row.score_justification : "",
    what_was_strong: typeof row.what_was_strong === "string" ? row.what_was_strong : "",
    what_to_work_on: typeof row.what_to_work_on === "string" ? row.what_to_work_on : "",
    safety_flag: typeof row.safety_flag === "string" && row.safety_flag ? row.safety_flag : "none",
  };
}

type JudgePromptBundle = {
  skipped?: boolean;
  system_prompt?: string;
  user_prompt?: string;
  response_schema?: Record<string, unknown>;
  eligible_skills?: string[];
  temperature?: number;
};

async function runPostCloseJudge(sessionId: string, tutorModel: string): Promise<void> {
  try {
    const promptBundle = await api<JudgePromptBundle>(
      `/kc/tutor/sessions/${encodeURIComponent(sessionId)}/graph2/judge-prompt`,
      { method: "POST" },
    );
    if (
      promptBundle.skipped ||
      !promptBundle.system_prompt ||
      !promptBundle.user_prompt ||
      !promptBundle.response_schema
    ) {
      return;
    }
    const judgeModel = judgeModelForCall(tutorModel, process.env.GRAPH2_JUDGE_MODEL);
    if (missingKeyMessage(judgeModel)) {
      await api(`/kc/tutor/sessions/${encodeURIComponent(sessionId)}/graph2/judge-failed`, { method: "POST" }).catch(
        () => undefined,
      );
      return;
    }
    const result = await generateText({
      model: languageModel(judgeModel),
      instructions: promptBundle.system_prompt,
      prompt: promptBundle.user_prompt,
      temperature: typeof promptBundle.temperature === "number" ? promptBundle.temperature : 0,
      output: Output.object({ schema: jsonSchema(promptBundle.response_schema) }),
    });
    const parsed =
      result.output && typeof result.output === "object"
        ? result.output
        : result.text
          ? JSON.parse(result.text)
          : null;
    if (!parsed || typeof parsed !== "object") {
      throw new Error("Batch judge returned an unreadable payload.");
    }
    await api(`/kc/tutor/sessions/${encodeURIComponent(sessionId)}/graph2/judge-result`, {
      method: "POST",
      body: JSON.stringify(parsed),
    });
    const judgeUsage = readModelUsage(result.usage);
    await api(`/kc/sessions/${encodeURIComponent(sessionId)}/token-usage`, {
      method: "POST",
      body: JSON.stringify({
        kind: "judge",
        model: judgeModel,
        message_id: null,
        ...judgeUsage,
      }),
    }).catch(() => undefined);
  } catch {
    // Sync biomarkers, end card, and previous tutor note remain intact on judge failure.
    await api(`/kc/tutor/sessions/${encodeURIComponent(sessionId)}/graph2/judge-failed`, { method: "POST" }).catch(
      () => undefined,
    );
  }
}

function schedulePostCloseTask(task: () => Promise<void>): void {
  // Use Next.js `after()` in server requests so the batch judge runs post-response
  // without blocking the closing reply, while staying loadable under Node ESM tests.
  void import("next/server")
    .then((mod) => {
      if (typeof mod.after === "function") {
        mod.after(task);
        return;
      }
      void task();
    })
    .catch(() => {
      void task();
    });
}

export async function POST(req: Request) {
  let body: { sessionId?: string; answer?: string; model?: string; turnId?: string; revision?: number };
  try {
    body = (await req.json()) as { sessionId?: string; answer?: string; model?: string; turnId?: string; revision?: number };
  } catch {
    return new Response("Expected JSON with sessionId and answer.", { status: 400 });
  }
  const sessionId = body.sessionId;
  const answer = typeof body.answer === "string" ? body.answer.trim() : "";
  const turnId = typeof body.turnId === "string" ? body.turnId.trim() : "";
  const revision = typeof body.revision === "number" ? body.revision : 0;
  if (!sessionId) return new Response("sessionId is required.", { status: 400 });
  if (!answer) return new Response("Write an answer first.", { status: 400 });

  const requested = typeof body.model === "string" ? body.model.trim() : "";
  const called = requested ? modelForCall(requested) : "";
  if (requested && !isKcModel(called)) {
    return new Response("That model is not allowed.", { status: 422 });
  }

  let prior: KcTutorSession;
  try {
    prior = await api<KcTutorSession>(`/kc/tutor/sessions/${sessionId}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the session.";
    return new Response(message, { status: 502 });
  }
  const modelName = called && isKcModel(called) ? called : kcModel(prior.tutor_model);
  const missingKey = missingKeyMessage(modelName);
  // A legacy unkeyed claim immediately writes the learner message.
  if (!turnId && missingKey) return new Response(missingKey, { status: 503 });

  let bundle: TurnBundle;
  try {
    bundle = await api<TurnBundle>(`/kc/tutor/sessions/${sessionId}/turn`, {
      method: "POST",
      body: JSON.stringify(turnId ? { answer, turn_id: turnId, revision } : { answer }),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not store the answer.";
    return new Response(message, { status: error instanceof ApiError && error.status === 409 ? 409 : 502 });
  }
  if (bundle.replayed) return Response.json(bundle);
  if (missingKey) return new Response(missingKey, { status: 503 });

  let captured: StoredCall | null = null;
  const captureRequest: LanguageModelMiddleware = {
    specificationVersion: "v4",
    wrapGenerate: async ({ doGenerate, params, model }) => {
      const request = requestForCall(params as ModelCall, bundle.system_prompt);
      captured = {
        system_prompt: request.system_prompt,
        messages: Array.isArray(request.messages) ? request.messages : [],
        model: model.modelId || modelName,
      };
      return doGenerate();
    },
  };

  const graded = typeof bundle.user_message === "string" ? bundle.user_message.trim() : "";
  const childLine = graded || answer;
  let decision: Decision | null = null;
  let usage: ModelUsageCounts = readModelUsage(undefined);
  try {
    const result = await generateText({
      model: wrapLanguageModel({ model: languageModel(modelName), middleware: captureRequest }),
      instructions: bundle.system_prompt,
      prompt: childLine,
      temperature: bundle.temperature,
      output: Output.object({ schema: jsonSchema(bundle.response_schema) }),
    });
    usage = readModelUsage(result.usage);
    decision = asDecision(result.output);
    if (!decision && result.text) {
      try {
        decision = asDecision(JSON.parse(result.text));
      } catch {
        decision = null;
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "The tutor could not answer.";
    if (!replyUnreadable("", message)) {
      return new Response(message, { status: 502 });
    }
    decision = blankDecision();
  }
  if (!decision || replyUnreadable(decision.reply)) {
    decision = blankDecision();
  }

  let session: KcTutorSession & { replayed?: boolean; loop_result?: Record<string, unknown> | null; loop_decision?: string };
  try {
    session = await api<KcTutorSession & { loop_result?: Record<string, unknown> | null; loop_decision?: string }>(
      `/kc/tutor/sessions/${sessionId}/decision`,
      {
        method: "POST",
        body: JSON.stringify(turnId ? { ...decision, turn_id: turnId } : decision),
      },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not apply that decision.";
    return new Response(message, { status: error instanceof ApiError && error.status === 409 ? 409 : 502 });
  }
  // Two in-flight calls can finish together. Record actual provider usage for
  // both, attaching only the winning decision to the saved learner turn.
  const messageId = session.replayed ? null : newTutorMessageId(bundle.messages, session.messages);
  const stored = captured ?? {
    system_prompt: bundle.system_prompt,
    messages: [{ role: "user", content: childLine }],
    model: modelName,
  };
  const saved = await finishSavedTurn(session, async () => {
    await api(`/kc/sessions/${sessionId}/model-prompts`, {
      method: "POST",
      body: JSON.stringify({
        system_prompt: stored.system_prompt,
        messages: stored.messages,
        model: stored.model,
        message_id: messageId,
        rubric_met: decision.rubric_met,
        misconception: decision.misconception,
        decision: {
          ...decision,
          loop_result: session.replayed ? null : session.loop_result ?? null,
          loop_decision: session.replayed ? "" : session.loop_decision || "",
        },
      }),
    });
    await api(`/kc/sessions/${sessionId}/token-usage`, {
      method: "POST",
      body: JSON.stringify({
        kind: "answer",
        model: stored.model,
        message_id: messageId,
        ...usage,
      }),
    });
  });
  if (saved.replayed) return Response.json(saved);
  if (saved.unit_complete && saved.graph2_judge_pending) {
    schedulePostCloseTask(async () => {
      await runPostCloseJudge(sessionId, modelName);
    });
  }
  return Response.json({
    ...saved,
    loop_result: saved.loop_result ?? null,
    loop_decision: saved.loop_decision || decision.decision,
  });
}
