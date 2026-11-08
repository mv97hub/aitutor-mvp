import type { KcBlock, KcBlockType } from "./kc";

export const BLOCK_TYPES: KcBlockType[] = [
  "topic_goal",
  "mcq",
  "case_study",
  "socratic",
  "curiosity",
  "worked_example",
  "spot_the_flaw",
  "teach_back",
  "retrieval_check",
];

export const BLOCK_LABELS: Record<KcBlockType, string> = {
  topic_goal: "Topic + Goal",
  mcq: "Multiple choice",
  case_study: "Case study",
  socratic: "Socratic",
  curiosity: "Curiosity",
  worked_example: "Worked example",
  spot_the_flaw: "Spot the flaw",
  teach_back: "Teach back",
  retrieval_check: "Retrieval check",
};

const SHORT_LABELS: Record<KcBlockType, [string, string]> = {
  topic_goal: ["Topic", "Topics"],
  mcq: ["MCQ", "MCQs"],
  case_study: ["Case study", "Case studies"],
  socratic: ["Socratic", "Socratic"],
  curiosity: ["Curiosity", "Curiosity"],
  worked_example: ["Worked example", "Worked examples"],
  spot_the_flaw: ["Spot the flaw", "Spot the flaw"],
  teach_back: ["Teach back", "Teach backs"],
  retrieval_check: ["Retrieval", "Retrievals"],
};

export function isBlockType(value: string): value is KcBlockType {
  return (BLOCK_TYPES as string[]).includes(value);
}

export function newBlockId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `blk_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function blankBlock(type: KcBlockType, id = newBlockId()): KcBlock {
  return { id, type, data: blankData(type) };
}

export function blankData(type: KcBlockType): Record<string, unknown> {
  if (type === "topic_goal") {
    return {
      topic: "",
      goal: "",
      reveal_after_recall: true,
      contrast_note: "",
      common_mixup: "",
      why_it_matters: "",
    };
  }
  if (type === "mcq") {
    return {
      mode: "static",
      question: "",
      options: ["", "", "", ""],
      correct_index: 0,
      why_correct: "",
      why_wrong: ["", "", "", ""],
      generation_prompt: "",
      why_correct_guidance: "",
      why_wrong_guidance: "",
    };
  }
  if (type === "case_study") {
    return {
      scenario: "",
      decision_point: "",
      decision_options: ["", ""],
      best_option_index: 0,
      why_best: "",
      why_others: "",
      follow_up_question: "",
      what_transfers: "",
    };
  }
  if (type === "socratic") {
    return {
      opening_question: "",
      probe_if_shallow: "",
      probe_if_close: "",
      target_insight: "",
      max_exchanges: 4,
    };
  }
  if (type === "curiosity") {
    return {
      hook_question: "",
      expected_hunch: "",
      reveal: "",
      why_surprising: "",
      bridge_to_goal: "",
    };
  }
  if (type === "worked_example") {
    return {
      problem: "",
      steps: [{ action: "", reason: "" }],
      faded_step_index: 0,
      solo_problem: "",
      solo_check: "",
    };
  }
  if (type === "spot_the_flaw") {
    return { artifact: "", flaw_location: "", why_its_wrong: "", fix: "", transfer_question: "" };
  }
  if (type === "teach_back") {
    return { prompt: "", must_include: [], rubric_note: "", follow_up_if_thin: "" };
  }
  return { prompt: "", acceptable_points: [], partial_credit_note: "" };
}

/** Run-length label, such as `1 Curiosity · 2 Topics`. */
export function blockSummary(blocks: { type: string }[]): string {
  const runs: { type: string; count: number }[] = [];
  for (const block of blocks) {
    const last = runs[runs.length - 1];
    if (last && last.type === block.type) last.count += 1;
    else runs.push({ type: block.type, count: 1 });
  }
  return runs
    .map((run) => {
      const labels = isBlockType(run.type) ? SHORT_LABELS[run.type] : null;
      const name = labels ? labels[run.count === 1 ? 0 : 1] : run.type;
      return `${run.count} ${name}`;
    })
    .join(" · ");
}

export type RecommendedChip = { label: string; focus: string };

/** Ordered block-type chips from a stored recommendation, seeded blocks, or the description sentence. */
export function recommendedChips(
  description: string | undefined,
  recommended?: { type: string; focus?: string }[] | null,
  blocks?: { type: string }[] | null,
): RecommendedChip[] {
  if (recommended?.length) {
    return recommended.map((item) => ({
      label: isBlockType(item.type) ? BLOCK_LABELS[item.type] : item.type,
      focus: item.focus?.trim() ?? "",
    }));
  }
  if (blocks?.length) {
    return blocks.map((item) => ({
      label: isBlockType(item.type) ? BLOCK_LABELS[item.type] : item.type,
      focus: "",
    }));
  }
  const match = (description ?? "").match(/Recommended blocks:\s*(.+)$/i);
  if (!match) return [];
  return match[1]
    .replace(/\.\s*$/, "")
    .split("->")
    .map((part) => {
      const cleaned = part.replace(/^\s*\d+\.\s*/, "").trim();
      const focus = cleaned.match(/^(.*?)\s*\((.*)\)\s*$/);
      if (focus) return { label: focus[1].trim(), focus: focus[2].trim() };
      return { label: cleaned, focus: "" };
    })
    .filter((chip) => chip.label);
}

/** Keep known types in canvas order. An empty pick falls back to Topic + Goal. */
export function orderScope(picked: Iterable<string>): KcBlockType[] {
  const set = new Set(picked);
  const ordered = BLOCK_TYPES.filter((type) => set.has(type));
  return ordered.length ? ordered : ["topic_goal"];
}

/** A missing list means the course has not stored a scope yet, so every type stays available. */
export function scopeFromCourse(value: readonly string[] | null | undefined): KcBlockType[] {
  if (value == null) return [...BLOCK_TYPES];
  return orderScope(value);
}

export function toggleScope(current: readonly KcBlockType[], type: KcBlockType): KcBlockType[] {
  const set = new Set(current);
  if (set.has(type)) set.delete(type);
  else set.add(type);
  return orderScope(set);
}
