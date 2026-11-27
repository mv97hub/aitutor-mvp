import { startStoredRun } from "@/lib/harness-start";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Start the server loop and return. The tab does not have to stay open. */
export async function POST(_req: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  return startStoredRun(id);
}
