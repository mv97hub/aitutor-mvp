import { api } from "@/lib/api";
import type { KcPipeline } from "@/lib/kc";
import { checkedStageModel, generateStageObject } from "@/lib/kc-stage-model";
import { encodeEvent, isStage, runStage, type StageBundle, type StageEvent } from "@/lib/kc-stage";

export const runtime = "nodejs";
export const maxDuration = 300;

const COURSE_ID = /^[0-9a-f-]{36}$/i;

type Body = {
  action?: string;
  course_id?: string;
  stage?: string;
  unit?: number | null;
  units_total?: number;
  model?: string;
  answers?: { question: string; answer: string }[];
  skip?: boolean;
  blueprint?: unknown;
  approve?: boolean;
};

function failure(message: string, status: number) {
  return Response.json({ error: message }, { status });
}

function messageOf(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function streamStage(courseId: string, body: Body, signal: AbortSignal) {
  const stage = body.stage;
  if (!isStage(stage)) return failure("That stage does not exist.", 400);
  let model;
  try {
    model = checkedStageModel(String(body.model || ""));
  } catch (error) {
    return failure(messageOf(error, "That model is not allowed."), 400);
  }
  const unit = typeof body.unit === "number" ? body.unit : null;
  const base = `/kc/courses/${courseId}/pipeline/${stage}`;
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const emit = (event: StageEvent) => {
        try {
          controller.enqueue(encoder.encode(encodeEvent(event)));
        } catch {
          /* The reader has gone. The stage still finishes or is aborted by the signal. */
        }
      };
      try {
        const pipeline = await runStage(
          { stage, unit },
          {
            bundle: () =>
              api<StageBundle>(`${base}/prompt`, { method: "POST", body: JSON.stringify({ model, unit }) }),
            generate: (input) => generateStageObject(model, input, signal),
            store: (result) => api<KcPipeline>(base, { method: "POST", body: JSON.stringify({ result, unit }) }),
          },
          emit,
          Number(body.units_total) || 0,
        );
        emit({ type: "done", pipeline });
      } catch (error) {
        emit({ type: "error", message: messageOf(error, "The stage failed.") });
      } finally {
        try {
          controller.close();
        } catch {
          /* Already closed. */
        }
      }
    },
  });
  return new Response(stream, {
    headers: { "Content-Type": "application/x-ndjson; charset=utf-8", "Cache-Control": "no-store, no-transform" },
  });
}

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return failure("The request could not be read.", 400);
  }
  const courseId = String(body.course_id || "");
  if (!COURSE_ID.test(courseId)) return failure("Choose a course first.", 400);
  const base = `/kc/courses/${courseId}/pipeline`;
  try {
    if (body.action === "stage") return streamStage(courseId, body, request.signal);
    if (body.action === "answers") {
      const pipeline = await api<KcPipeline>(`${base}/answers`, {
        method: "POST",
        body: JSON.stringify({ answers: body.answers ?? [], skip: Boolean(body.skip) }),
      });
      return Response.json({ pipeline });
    }
    if (body.action === "blueprint") {
      const pipeline = await api<KcPipeline>(`${base}/blueprint`, {
        method: "PUT",
        body: JSON.stringify({ blueprint: body.blueprint, approve: Boolean(body.approve) }),
      });
      return Response.json({ pipeline });
    }
    if (body.action === "reset") {
      const pipeline = await api<KcPipeline>(base, { method: "DELETE" });
      return Response.json({ pipeline });
    }
  } catch (error) {
    return failure(messageOf(error, "That did not save."), 422);
  }
  return failure("That action does not exist.", 400);
}
