import { api } from "@/lib/api";

export const runtime = "nodejs";

const COURSE_ID = /^[0-9a-f-]{36}$/i;

type Body = {
  action?: string;
  course_id?: string;
  document?: unknown;
  mode?: string;
  title?: string;
  grade?: string;
  audience?: string;
  curriculum?: string;
  block_notes?: string;
};

function failure(message: string, status: number) {
  return Response.json({ error: message }, { status });
}

function messageOf(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return failure("The request could not be read.", 400);
  }
  const courseId = String(body.course_id || "");
  try {
    if (body.action === "prompt") {
      const prompt = await api<{ prompt: string }>("/kc/courses/external-prompt", {
        method: "POST",
        body: JSON.stringify({
          title: body.title ?? "",
          grade: body.grade ?? "",
          audience: body.audience ?? "",
          curriculum: body.curriculum ?? "",
          block_notes: body.block_notes ?? "",
        }),
      });
      return Response.json(prompt);
    }
    if (!COURSE_ID.test(courseId)) return failure("Choose a course first.", 400);
    if (body.action === "export") {
      return Response.json(await api(`/kc/courses/${courseId}/export`));
    }
    if (body.action === "preview") {
      return Response.json(
        await api("/kc/courses/import-preview", {
          method: "POST",
          body: JSON.stringify({ document: body.document, mode: body.mode || "merge" }),
        }),
      );
    }
    if (body.action === "import") {
      const course = await api(`/kc/courses/${courseId}/import`, {
        method: "POST",
        body: JSON.stringify({ document: body.document, mode: body.mode === "replace" ? "replace" : "merge" }),
      });
      return Response.json({ course });
    }
  } catch (error) {
    return failure(messageOf(error, "That file did not import."), 422);
  }
  return failure("That action does not exist.", 400);
}
