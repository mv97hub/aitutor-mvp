import { api } from "@/lib/api";
import { createAgentRun, harnessAuthResponse, type PersonaRef } from "@/lib/harness-agent";
import { startStoredRun } from "@/lib/harness-start";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Create a harness run and start it in this process. Returns the run id. */
export async function POST(req: Request) {
  const denied = harnessAuthResponse(req.headers.get("authorization"));
  if (denied) return denied;
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ detail: "The request body must be JSON." }, { status: 400 });
  }
  const result = await createAgentRun(body, {
    courses: () => api("/kc/courses"),
    personas: () => api<PersonaRef[]>("/kc/harness/personas"),
    ensureStarter: async () => {
      await api("/kc/harness/personas/starter", { method: "POST" });
      return api<PersonaRef[]>("/kc/harness/personas");
    },
    createRun: (plan) => api("/kc/harness/runs", { method: "POST", body: JSON.stringify(plan) }),
    start: async (id) => {
      const response = await startStoredRun(id);
      return { ok: response.ok, status: response.status, text: await response.text() };
    },
  });
  return Response.json(result.body, { status: result.status });
}
