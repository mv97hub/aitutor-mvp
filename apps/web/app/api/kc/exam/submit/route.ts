import { generateText, jsonSchema, Output } from "ai";

import { api } from "@/lib/api";
import { examModelForCall, type BlindExamAttemptSummary } from "@/lib/blind-exam";
import { missingKeyMessage } from "@/lib/kc-models";
import { languageModel } from "@/lib/language-model";

export const runtime = "nodejs";
export const maxDuration = 60;

type GradePromptBundle = {
  has_transfer_items: boolean;
  exam_id?: string;
  item_ids?: string[];
  system_prompt?: string;
  user_prompt?: string;
  response_schema?: Record<string, unknown>;
  temperature?: number;
};

export async function POST(req: Request) {
  let body: {
    courseId?: string;
    examId?: string;
    studentId?: string;
    answers?: Record<string, string>;
    tutorModel?: string;
  };
  try {
    body = (await req.json()) as {
      courseId?: string;
      examId?: string;
      studentId?: string;
      answers?: Record<string, string>;
      tutorModel?: string;
    };
  } catch {
    return Response.json({ detail: "Expected JSON body." }, { status: 400 });
  }

  const courseId = (body.courseId || "").trim();
  const examId = (body.examId || "").trim();
  const studentId = (body.studentId || "").trim();
  const answers = body.answers && typeof body.answers === "object" ? body.answers : {};
  if (!courseId || !examId) {
    return Response.json({ detail: "courseId and examId are required." }, { status: 400 });
  }

  let transferGrades: unknown[] | null = null;
  try {
    const bundle = await api<GradePromptBundle>(`/kc/tutor/courses/${encodeURIComponent(courseId)}/exam/grade-prompt`, {
      method: "POST",
      body: JSON.stringify({ exam_id: examId, answers }),
    });
    if (bundle.has_transfer_items && bundle.system_prompt && bundle.user_prompt && bundle.response_schema) {
      const modelName = examModelForCall(body.tutorModel);
      if (!missingKeyMessage(modelName)) {
        try {
          const result = await generateText({
            model: languageModel(modelName),
            instructions: bundle.system_prompt,
            prompt: bundle.user_prompt,
            temperature: typeof bundle.temperature === "number" ? bundle.temperature : 0,
            output: Output.object({ schema: jsonSchema(bundle.response_schema) }),
          });
          const parsed = result.output as { grades?: unknown[] } | undefined;
          if (parsed && Array.isArray(parsed.grades)) {
            transferGrades = parsed.grades;
          }
        } catch {
          // Fallback to FastAPI deterministic key-point scorer so submissions never fail.
          transferGrades = null;
        }
      }
    }
  } catch {
    transferGrades = null;
  }

  try {
    const graded = await api<BlindExamAttemptSummary>(
      `/kc/tutor/courses/${encodeURIComponent(courseId)}/exam/attempts`,
      {
        method: "POST",
        body: JSON.stringify({
          exam_id: examId,
          student_id: studentId || null,
          answers,
          transfer_grades: transferGrades,
          mode: "human",
        }),
      },
    );
    return Response.json(graded);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not grade the blind exam.";
    return Response.json({ detail: message }, { status: 502 });
  }
}
