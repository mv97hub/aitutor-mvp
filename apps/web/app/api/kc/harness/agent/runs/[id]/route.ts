import { apiBase } from "@/lib/api";
import { harnessAuthResponse } from "@/lib/harness-agent";

export const runtime = "nodejs";

/** Read a run until its status is finished or stopped. */
export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const denied = harnessAuthResponse(req.headers.get("authorization"));
  if (denied) return denied;
  const { id } = await context.params;
  const response = await fetch(`${apiBase()}/kc/harness/runs/${id}/agent`, { cache: "no-store" });
  const text = await response.text();
  return new Response(text, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") || "application/json; charset=utf-8" },
  });
}
