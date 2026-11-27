import { generateText, jsonSchema, Output } from "ai";

import { api } from "@/lib/api";
import { examModelForCall, normalizeExamPhase, type BlindExamPublic } from "@/lib/blind-exam";
import { missingKeyMessage } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";

export const runtime = "nodejs";
export const maxDuration = 60;

type PromptResponse =
  | { cached: true; exam: BlindExamPublic }
  | {
      cached: false;
      goal_id: string;
      course_title: string;
      phase: "pre" | "post";
      spec_fingerprint: string;
      system_prompt: string;
      user_prompt: string;
      response_schema: Record<string, unknown>;
      temperature?: number;
      target_total?: number;
    };

export async function POST(req: Request) {
  let body: { courseId?: string; phase?: string; tutorModel?: string; numItems?: number };
  try {
    body = (await req.json()) as { courseId?: string; phase?: string; tutorModel?: string; numItems?: number };
  } catch {
    return Response.json({ detail: "Expected JSON with courseId." }, { status: 400 });
  }
  const courseId = (body.courseId || "").trim();
  if (!courseId) return Response.json({ detail: "courseId is required." }, { status: 400 });
  const phase = normalizeExamPhase(body.phase);

  let promptData: PromptResponse;
  try {
    promptData = await api<PromptResponse>(`/kc/tutor/courses/${encodeURIComponent(courseId)}/exam/prompt`, {
      method: "POST",
      body: JSON.stringify({
        phase,
        ...(typeof body.numItems === "number" ? { num_items: body.numItems } : {}),
      }),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not prepare the blind exam.";
    return Response.json({ detail: message }, { status: 502 });
  }

  if (promptData.cached) {
    return Response.json({ cached: true, exam: promptData.exam });
  }

  const modelName = examModelForCall(body.tutorModel);
  const missingKey = missingKeyMessage(modelName);
  let generatedItems: unknown[] | null = null;
  let usedModel: string | null = modelName;

  if (!missingKey) {
    try {
      const result = await generateText({
        model: languageModel(modelName),
        instructions: promptData.system_prompt,
        prompt: promptData.user_prompt,
        temperature: typeof promptData.temperature === "number" ? promptData.temperature : 0.2,
        output: Output.object({ schema: jsonSchema(promptData.response_schema) }),
      });
      const parsed = result.output as { items?: unknown[] } | undefined;
      if (parsed && Array.isArray(parsed.items) && parsed.items.length > 0) {
        generatedItems = parsed.items;
      }
    } catch {
      generatedItems = null;
    }
  }

  try {
    const stored = await api<BlindExamPublic>(`/kc/tutor/courses/${encodeURIComponent(courseId)}/exam`, {
      method: "POST",
      body: JSON.stringify(
        generatedItems
          ? {
              phase,
              spec_fingerprint: promptData.spec_fingerprint,
              items: generatedItems,
              model: usedModel,
            }
          : {
              phase,
              spec_fingerprint: promptData.spec_fingerprint,
              use_deterministic_fallback: true,
              model: "deterministic",
              ...(typeof promptData.target_total === "number" ? { num_items: promptData.target_total } : {}),
            },
      ),
    });
    return Response.json({ cached: false, exam: stored });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not save the blind exam.";
    return Response.json({ detail: message }, { status: 502 });
  }
}
