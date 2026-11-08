import type { KcComponent, KcComponentDraft } from "./kc";

/** The body Push draft sends. Every topic-goal pair on the draft is kept. */
export function creatorPushPayload(draft: KcComponentDraft, component: KcComponent) {
  return {
    description: draft.description ?? component.description,
    outline: draft.outline ?? component.outline,
    topics: draft.topics ?? component.topics,
    title: draft.title,
    kc_type: draft.kc_type,
    core_truth: draft.core_truth,
    rubric: draft.rubric,
    misconceptions: draft.misconceptions,
    prerequisite_codes: draft.prerequisite_codes,
    encompasses_codes: draft.encompasses_codes,
    type_fields: draft.type_fields,
  };
}
