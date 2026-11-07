import { Output, jsonSchema, streamText, type JSONSchema7 } from "ai";

import { api } from "@/lib/api";
import type { KcDraft } from "@/lib/kc";
import { languageModel } from "@/lib/language-model";
import { isKcModel, missingKeyMessage, modelForCall, usesOpenRouter, type KcModel } from "@/lib/kc-models";

type PromptBundle = {
  model: string;
  system_prompt: string;
  user_prompt: string;
  schema: JSONSchema7;
  pass?: "full" | "titles";
};

type SliceBundle = PromptBundle & {
  titles?: string[];
};

type SlicePlan = {
  slice_size?: number;
  slices: SliceBundle[];
};

type CourseResult = {
  reply: string;
  draft: Extract<KcDraft, { kind: "course" }>;
};

const cache = new Map<string, CourseResult>();

function requireKey(model: string) {
  const missing = missingKeyMessage(model);
  if (missing) throw new Error(missing);
}

function requireModel(model: string): KcModel {
  const called = modelForCall(model);
  if (!isKcModel(called)) {
    throw new Error("That model is not allowed.");
  }
  return called;
}

async function completeObject(model: KcModel, instructions: string, prompt: string, schema: JSONSchema7) {
  const result = streamText({
    model: languageModel(model),
    output: Output.object({
      schema: jsonSchema(schema),
      name: "kc_draft",
      description: "A curriculum draft. No web search.",
    }),
    instructions,
    prompt,
    ...(model.startsWith("gpt-4") || usesOpenRouter(model) ? { temperature: 0.3 } : {}),
  });
  const output = await result.output;
  if (!output || typeof output !== "object") {
    throw new Error("The model reply could not be read.");
  }
  return output as Record<string, unknown>;
}

async function withModel<T>(
  model: KcModel,
  bundle: PromptBundle,
  finish: (proposal: Record<string, unknown>) => Promise<T>,
): Promise<T> {
  let note = "";
  let last = "The model reply could not be read.";
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const proposal = await completeObject(
        model,
        note ? `${bundle.system_prompt}\n${note}` : bundle.system_prompt,
        bundle.user_prompt,
        bundle.schema,
      );
      return await finish(proposal);
    } catch (error) {
      last = error instanceof Error ? error.message : last;
      note = `The previous reply was rejected. ${last}`;
    }
  }
  throw new Error(last);
}

function noted(prompt: string, note: string) {
  return note ? `${prompt}\n${note}` : prompt;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

function componentRows(proposal: Record<string, unknown>): Record<string, unknown>[] {
  const raw = proposal.components;
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object");
}

async function draftLongCourse(
  courseId: string,
  message: string,
  model: KcModel,
  bundle: PromptBundle,
): Promise<CourseResult> {
  let note = "";
  let last = "The model reply could not be read.";
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const titlesProposal = await completeObject(
        model,
        noted(bundle.system_prompt, note),
        bundle.user_prompt,
        bundle.schema,
      );
      const titles = stringList(titlesProposal.titles);
      const subject = typeof titlesProposal.subject === "string" ? titlesProposal.subject : "";
      const majorIdeas = stringList(titlesProposal.major_ideas);
      const plan = await api<SlicePlan>(`/kc/courses/${courseId}/draft-slices`, {
        method: "POST",
        body: JSON.stringify({ message, model, titles, subject, major_ideas: majorIdeas }),
      });
      const components: Record<string, unknown>[] = [];
      for (const slice of plan.slices) {
        const piece = await completeObject(model, noted(slice.system_prompt, note), slice.user_prompt, slice.schema);
        components.push(...componentRows(piece));
      }
      return await api<CourseResult>(`/kc/courses/${courseId}/draft-finish`, {
        method: "POST",
        body: JSON.stringify({
          message,
          proposal: { subject, major_ideas: majorIdeas, components },
        }),
      });
    } catch (error) {
      last = error instanceof Error ? error.message : last;
      note = `The previous reply was rejected. ${last}`;
    }
  }
  throw new Error(last);
}

export async function draftKcCourse(input: {
  courseId: string;
  message: string;
  model: string;
}): Promise<CourseResult> {
  const model = requireModel(input.model);
  requireKey(model);
  const message = input.message.trim();
  if (!message) throw new Error("Write a message first.");
  const key = `${input.courseId}\n${model}\n${message}`;
  const cached = cache.get(key);
  if (cached) return cached;
  const bundle = await api<PromptBundle>(`/kc/courses/${input.courseId}/draft-prompt`, {
    method: "POST",
    body: JSON.stringify({ message, model }),
  });
  const finished =
    bundle.pass === "titles"
      ? await draftLongCourse(input.courseId, message, model, bundle)
      : await withModel(model, bundle, (proposal) =>
          api<CourseResult>(`/kc/courses/${input.courseId}/draft-finish`, {
            method: "POST",
            body: JSON.stringify({ message, proposal }),
          }),
        );
  cache.set(key, finished);
  return finished;
}

export async function draftKcComponent(input: {
  nodeId: string;
  message: string;
  model: string;
}): Promise<void> {
  const model = requireModel(input.model);
  requireKey(model);
  const message = input.message.trim();
  if (!message) throw new Error("Write a message first.");
  const bundle = await api<PromptBundle>(`/kc/nodes/${input.nodeId}/creator-prompt`, {
    method: "POST",
    body: JSON.stringify({ message, model }),
  });
  await withModel(model, bundle, async (proposal) => {
    const discussion = typeof proposal.discussion === "string" ? proposal.discussion : "";
    await api(`/kc/nodes/${input.nodeId}/model-turn`, {
      method: "POST",
      body: JSON.stringify({ message, discussion, draft: proposal }),
    });
  });
}
