import { judgeTranscript } from "@/lib/harness-judge-run";
import type { JudgeTurn, SideCheck } from "@/lib/harness-judge";

export const runtime = "nodejs";
export const maxDuration = 60;

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
  const turns = Array.isArray(body.turns) ? body.turns : [];
  const judged = await judgeTranscript({
    model: body.model,
    child: body.child,
    turns: turns.length
      ? turns
      : [{ seq: 1, child_text: body.transcript || "", tutor_reply: "" }],
    checks: body.checks,
  });
  if (judged.error) return new Response(judged.error, { status: judged.error === "That model is not allowed." ? 422 : 502 });
  return Response.json(judged);
}
