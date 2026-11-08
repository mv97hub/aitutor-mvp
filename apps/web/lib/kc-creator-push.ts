import type { KcComponent, KcComponentDraft } from "./kc";

/** The body Push draft sends. Topic pairs are not required. The draft's blocks are. */
export function creatorPushPayload(draft: KcComponentDraft, component: KcComponent) {
  const payload: {
    description: string;
    outline: string;
    title: string;
    core_truth: string;
    misconceptions: KcComponentDraft["misconceptions"];
    prerequisite_codes: string[];
    encompasses_codes: string[];
    blocks: NonNullable<KcComponentDraft["blocks"]>;
    rubric?: string[];
  } = {
    description: draft.description ?? component.description,
    outline: draft.outline ?? component.outline,
    title: draft.title,
    core_truth: draft.core_truth,
    misconceptions: draft.misconceptions,
    prerequisite_codes: draft.prerequisite_codes,
    encompasses_codes: draft.encompasses_codes,
    blocks: draft.blocks ?? [],
  };
  if (!draft.blocks?.length && draft.rubric) {
    payload.rubric = draft.rubric;
  }
  return payload;
}
