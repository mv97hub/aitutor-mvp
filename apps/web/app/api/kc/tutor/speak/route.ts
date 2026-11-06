import { openai } from "@ai-sdk/openai";
import { generateText } from "ai";

import { api } from "@/lib/api";
import { openaiModelName } from "@/lib/model";
import type { KcTutorSession } from "@/lib/kc";

export const runtime = "nodejs";
export const maxDuration = 60;

const MISSING_KEY =
  "OPENAI_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENAI_API_KEY to your real key, and restart the Next.js server.";

type PromptBundle = {
  system_prompt: string;
  recipe: string;
  step: number;
  step_label: string;
};

export async function POST(req: Request) {
  let body: { sessionId?: string };
  try {
    body = (await req.json()) as { sessionId?: string };
  } catch {
    return new Response("Expected JSON with sessionId.", { status: 400 });
  }
  const sessionId = body.sessionId;
  if (!sessionId) return new Response("sessionId is required.", { status: 400 });

  if (!process.env.OPENAI_API_KEY?.trim()) {
    return new Response(MISSING_KEY, {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  let bundle: PromptBundle;
  try {
    bundle = await api<PromptBundle>(`/kc/tutor/sessions/${sessionId}/prompt`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the prompt.";
    return new Response(message, { status: 502 });
  }

  let spoken = "";
  try {
    const result = await generateText({
      model: openai(openaiModelName()),
      instructions: bundle.system_prompt,
      prompt:
        "Say this step to the student now. Follow the system instructions. Do not set the type, the edges, or the score.",
    });
    spoken = result.text.trim();
  } catch (error) {
    const message = error instanceof Error ? error.message : "The tutor could not say this step.";
    return new Response(message, { status: 502 });
  }
  if (!spoken) {
    return new Response("The tutor did not say this step.", { status: 502 });
  }

  try {
    const session = await api<KcTutorSession>(`/kc/tutor/sessions/${sessionId}/speech`, {
      method: "POST",
      body: JSON.stringify({ content: spoken }),
    });
    return Response.json(session);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not store that step.";
    return new Response(message, { status: 502 });
  }
}
