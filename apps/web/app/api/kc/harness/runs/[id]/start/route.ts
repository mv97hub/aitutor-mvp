import { POST as child } from "@/app/api/kc/harness/child/route";
import { POST as finish } from "@/app/api/kc/harness/finish/route";
import { POST as turn } from "@/app/api/kc/harness/turn/route";
import { POST as answer } from "@/app/api/kc/tutor/answer/route";
import { POST as speak } from "@/app/api/kc/tutor/speak/route";
import { api } from "@/lib/api";
import { beginBackgroundRun, clampConcurrency, finishBackgroundRun, launchBackgroundRun } from "@/lib/harness-background";
import type { ClaimedChat } from "@/lib/harness-runner";
import { serverTransport } from "@/lib/harness-transport";

export const runtime = "nodejs";
export const maxDuration = 60;

type RunBody = { status?: string; plan?: { concurrency?: number } };

/** Start the server loop and return. The tab does not have to stay open. */
export async function POST(_req: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const signal = beginBackgroundRun(id);
  if (!signal) return Response.json({ ok: true, running: true });
  try {
    const run = await api<RunBody>(`/kc/harness/runs/${id}/resume`, { method: "POST" });
    if (run.status === "cancelled" || run.status === "completed") {
      finishBackgroundRun(id, signal);
      return Response.json({ ok: true, running: false, status: run.status });
    }
    launchBackgroundRun({
      runId: id,
      signal,
      concurrency: clampConcurrency(run.plan?.concurrency),
      claim: async () => {
        const claimed = await api<{ chat: ClaimedChat | null }>(`/kc/harness/runs/${id}/claim`, { method: "POST" });
        return claimed.chat;
      },
      transport: serverTransport(id, { speak, answer, child, turn, finish }),
    });
    return Response.json({ ok: true, running: true });
  } catch (error) {
    finishBackgroundRun(id, signal);
    const message = error instanceof Error ? error.message : "Could not start the run.";
    return new Response(message, { status: 502 });
  }
}
