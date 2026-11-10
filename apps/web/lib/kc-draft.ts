import { Output, jsonSchema, streamText, type JSONSchema7 } from "ai";

import { api } from "@/lib/api";
import type { KcDraft } from "@/lib/kc";
import { languageModel } from "@/lib/language-model";
import { isKcModel, missingKeyMessage, modelForCall, usesOpenRouter, type KcModel } from "@/lib/kc-models";
import {
  KcDraftError,
  promptTurnId,
  releaseRecord,
  shareInFlight,
  takeComponentRows,
  type SentPrompt,
} from "@/lib/kc-prompt-log";

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

export type DraftedCourse = CourseResult & {
  prompts: SentPrompt[];
  promptTurnId: string;
};

const inflight = new Map<string, Promise<DraftedCourse>>();

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

function turnIdFor(courseId: string, message: string, prompts: SentPrompt[]) {
  return promptTurnId([
    courseId,
    message,
    ...prompts.flatMap((item) => [item.label, item.instructions, item.prompt]),
  ]);
}

async function completeObject(
  model: KcModel,
  instructions: string,
  prompt: string,
  schema: JSONSchema7,
  sent: SentPrompt[],
  label: string,
) {
  sent.push({ label, instructions, prompt });
  const output = await streamText({
    model: languageModel(model),
    output: Output.object({
      schema: jsonSchema(schema),
      name: "kc_draft",
      description: "A curriculum draft. No web search.",
    }),
    instructions,
    prompt,
    ...(model.startsWith("gpt-4") || usesOpenRouter(model) ? { temperature: 0.3 } : {}),
  }).output;
  if (!output || typeof output !== "object") {
    throw new Error("The model reply could not be read.");
  }
  return output as Record<string, unknown>;
}

async function withModel<T>(
  model: KcModel,
  bundle: PromptBundle,
  finish: (proposal: Record<string, unknown>) => Promise<T>,
  sent: SentPrompt[],
  label: string,
): Promise<T> {
  let note = "";
  let last = "The model reply could not be read.";
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const proposal = await completeObject(
        model,
        noted(bundle.system_prompt, note),
        bundle.user_prompt,
        bundle.schema,
        sent,
        label,
      );
      try {
        return await finish(proposal);
      } finally {
        releaseRecord(proposal);
      }
    } catch (error) {
      last = error instanceof Error ? error.message : last;
      note = `The previous reply was rejected. ${last}`;
    }
  }
  throw new KcDraftError(last, sent);
}

function noted(prompt: string, note: string) {
  return note ? `${prompt}\n${note}` : prompt;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

function scopeBody(allowedBlockTypes?: string[]) {
  return allowedBlockTypes && allowedBlockTypes.length ? { allowed_block_types: allowedBlockTypes } : {};
}

function readTitlePass(proposal: Record<string, unknown>) {
  const titles = stringList(proposal.titles);
  const subject = typeof proposal.subject === "string" ? proposal.subject : "";
  const majorIdeas = stringList(proposal.major_ideas);
  releaseRecord(proposal);
  return { titles, subject, majorIdeas };
}

async function draftLongCourse(
  courseId: string,
  message: string,
  model: KcModel,
  bundle: PromptBundle,
  allowedBlockTypes: string[] | undefined,
  sent: SentPrompt[],
): Promise<CourseResult> {
  let note = "";
  let last = "The model reply could not be read.";
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const titleCall = await completeObject(
        model,
        noted(bundle.system_prompt, note),
        bundle.user_prompt,
        bundle.schema,
        sent,
        "Title pass",
      );
      const { titles, subject, majorIdeas } = readTitlePass(titleCall);
      const plan = await api<SlicePlan>(`/kc/courses/${courseId}/draft-slices`, {
        method: "POST",
        body: JSON.stringify({ message, model, titles, subject, major_ideas: majorIdeas, ...scopeBody(allowedBlockTypes) }),
      });
      const components: Record<string, unknown>[] = [];
      const slices: Array<SliceBundle | undefined> = plan.slices.splice(0, plan.slices.length);
      for (let index = 0; index < slices.length; index += 1) {
        const slice = slices[index];
        if (!slice) continue;
        const instructions = noted(slice.system_prompt, note);
        const prompt = slice.user_prompt;
        const schema = slice.schema;
        slices[index] = undefined;
        const piece = await completeObject(model, instructions, prompt, schema, sent, `Slice ${index + 1}`);
        components.push(...takeComponentRows(piece));
      }
      const body = JSON.stringify({
        message,
        proposal: { subject, major_ideas: majorIdeas, components },
        ...scopeBody(allowedBlockTypes),
      });
      components.length = 0;
      return await api<CourseResult>(`/kc/courses/${courseId}/draft-finish`, {
        method: "POST",
        body,
      });
    } catch (error) {
      last = error instanceof Error ? error.message : last;
      note = `The previous reply was rejected. ${last}`;
    }
  }
  throw new KcDraftError(last, sent);
}

async function draftCourseCall(input: {
  courseId: string;
  message: string;
  model: KcModel;
  allowedBlockTypes?: string[];
}): Promise<DraftedCourse> {
  const sent: SentPrompt[] = [];
  try {
    const bundle = await api<PromptBundle>(`/kc/courses/${input.courseId}/draft-prompt`, {
      method: "POST",
      body: JSON.stringify({ message: input.message, model: input.model, ...scopeBody(input.allowedBlockTypes) }),
    });
    const finished =
      bundle.pass === "titles"
        ? await draftLongCourse(input.courseId, input.message, input.model, bundle, input.allowedBlockTypes, sent)
        : await withModel(
            input.model,
            bundle,
            (proposal) =>
              api<CourseResult>(`/kc/courses/${input.courseId}/draft-finish`, {
                method: "POST",
                body: JSON.stringify({ message: input.message, proposal, ...scopeBody(input.allowedBlockTypes) }),
              }),
            sent,
            "Draft",
          );
    return { ...finished, prompts: sent, promptTurnId: turnIdFor(input.courseId, input.message, sent) };
  } catch (error) {
    const prompts = error instanceof KcDraftError ? error.prompts : sent;
    const message = error instanceof Error ? error.message : "The model reply could not be read.";
    throw new KcDraftError(message, prompts, turnIdFor(input.courseId, input.message, prompts));
  }
}

export async function draftKcCourse(input: {
  courseId: string;
  message: string;
  model: string;
  allowedBlockTypes?: string[];
}): Promise<DraftedCourse> {
  const model = requireModel(input.model);
  requireKey(model);
  const message = input.message.trim();
  if (!message) throw new Error("Write a message first.");
  const scope = (input.allowedBlockTypes ?? []).join(",");
  const key = `${input.courseId}\n${model}\n${scope}\n${message}`;
  return shareInFlight(inflight, key, () =>
    draftCourseCall({
      courseId: input.courseId,
      message,
      model,
      allowedBlockTypes: input.allowedBlockTypes,
    }),
  );
}

export async function draftKcComponent(input: {
  nodeId: string;
  message: string;
  model: string;
  allowedBlockTypes?: string[];
}): Promise<SentPrompt[]> {
  const model = requireModel(input.model);
  requireKey(model);
  const message = input.message.trim();
  if (!message) throw new Error("Write a message first.");
  const sent: SentPrompt[] = [];
  const bundle = await api<PromptBundle>(`/kc/nodes/${input.nodeId}/creator-prompt`, {
    method: "POST",
    body: JSON.stringify({ message, model, ...scopeBody(input.allowedBlockTypes) }),
  });
  await withModel(
    model,
    bundle,
    async (proposal) => {
      const discussion = typeof proposal.discussion === "string" ? proposal.discussion : "";
      await api(`/kc/nodes/${input.nodeId}/model-turn`, {
        method: "POST",
        body: JSON.stringify({ message, discussion, draft: proposal, ...scopeBody(input.allowedBlockTypes) }),
      });
    },
    sent,
    "Draft",
  );
  return sent;
}
