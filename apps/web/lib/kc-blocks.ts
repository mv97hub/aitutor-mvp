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
  "explanation",
];

/** Long names, the same strings the stored draft reply and the API catalog use. */
export const BLOCK_REPLY_LABELS: Record<KcBlockType, string> = {
  topic_goal: "Topic / Goal",
  mcq: "Multiple Choice Question",
  case_study: "Case Study / Contrasting Cases",
  socratic: "Socratic Discussion",
  curiosity: "Curiosity / Wonder Hook",
  worked_example: "Worked Example + Faded Step",
  spot_the_flaw: "Spot the Flaw / Buggy Rule",
  teach_back: "Teach-Back / Feynman",
  retrieval_check: "Retrieval & Elaborative Interrogation",
  explanation: "Explanatory Walkthrough",
};

/** Field order and labels for one block, shared by the draft reply and the catalog. */
export const BLOCK_FIELD_LABELS: Record<KcBlockType, [string, string][]> = {
  topic_goal: [
    ["topic", "Topic"],
    ["goal", "Goal"],
    ["acceptance_criteria", "Acceptance criteria"],
    ["teaching_notes", "Teaching notes"],
  ],
  mcq: [
    ["mode", "Mode"],
    ["question_stem", "Question stem"],
    ["choices", "Choices"],
    ["correct_explanation", "Correct explanation"],
    ["target_skill", "Target skill"],
    ["difficulty", "Difficulty"],
    ["num_choices", "Number of choices"],
    ["distractor_guidance", "Distractor guidance"],
    ["stem_constraints", "Stem constraints"],
  ],
  case_study: [
    ["case_a", "Case A"],
    ["case_b", "Case B"],
    ["prediction_prompt", "Prediction prompt"],
    ["invariant_principle", "Invariant principle"],
    ["transfer_prompt", "Transfer prompt"],
    ["transfer_expected", "Transfer expected"],
  ],
  socratic: [
    ["central_dilemma", "Central dilemma"],
    ["initial_probe", "Opening probe"],
    ["counterexamples", "Counterexamples"],
    ["target_synthesis", "Target synthesis"],
  ],
  curiosity: [
    ["phenomenon_hook", "Phenomenon hook"],
    ["prediction_question", "Prediction question"],
    ["bridge_to_unit", "Bridge to unit"],
    ["wonder_branches", "Wonder branches"],
  ],
  worked_example: [
    ["problem_statement", "Problem statement"],
    ["steps", "Steps"],
    ["faded_step_index", "Faded step"],
    ["solo_problem", "Solo problem"],
    ["solo_expected_answer", "Solo expected answer"],
  ],
  spot_the_flaw: [
    ["rookie_work", "Rookie work"],
    ["flaw_description", "Flaw description"],
    ["underlying_misconception", "Underlying misconception"],
    ["corrected_version", "Corrected version"],
  ],
  teach_back: [
    ["peer_persona_prompt", "Peer prompt"],
    ["required_concepts", "Required concepts"],
    ["peer_follow_up_question", "Peer follow-up"],
  ],
  retrieval_check: [
    ["recall_prompt", "Recall prompt"],
    ["expected_fact", "Expected fact"],
    ["elaborative_why_prompt", "Elaborative why prompt"],
    ["expected_why_rationale", "Expected why rationale"],
  ],
  explanation: [
    ["block_title", "Block title"],
    ["topics", "Topics"],
    ["summary_takeaway", "Summary takeaway"],
  ],
};

/** Short names for the canvas and the course structure. */
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
  explanation: "Explanatory walkthrough",
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
  explanation: ["Explanation", "Explanations"],
};

export function isBlockType(value: string): value is KcBlockType {
  return (BLOCK_TYPES as string[]).includes(value);
}

export function newBlockId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `blk_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export type ExplanationTopic = {
  id: string;
  title: string;
  explanation: string;
  key_points: string;
  examples_or_analogies: string;
};

export function blankExplanationTopic(index: number): ExplanationTopic {
  return {
    id: `top_${index}`,
    title: "",
    explanation: "",
    key_points: "",
    examples_or_analogies: "",
  };
}

export function blankBlock(type: KcBlockType, id = newBlockId()): KcBlock {
  return { id, type, data: blankData(type) };
}

export type McqChoice = {
  id: string;
  text: string;
  is_correct: boolean;
  distractor_rationale: string;
  misconception_code: string;
};

export type WorkedStep = { step_text: string; rationale: string };

const CHOICE_IDS = ["a", "b", "c", "d", "e"] as const;

export function blankChoice(index: number, correct = false): McqChoice {
  return {
    id: CHOICE_IDS[index] ?? String(index + 1),
    text: "",
    is_correct: correct,
    distractor_rationale: "",
    misconception_code: "",
  };
}

/** Empty data for one block type, using the field-catalog keys. */
export function blankData(type: KcBlockType): Record<string, unknown> {
  if (type === "topic_goal") {
    return { topic: "", goal: "", acceptance_criteria: "", teaching_notes: "" };
  }
  if (type === "mcq") {
    return {
      mode: "static",
      question_stem: "",
      choices: [blankChoice(0, true), blankChoice(1)],
      correct_explanation: "",
      target_skill: "",
      difficulty: "standard",
      num_choices: 4,
      distractor_guidance: "",
      stem_constraints: "",
    };
  }
  if (type === "case_study") {
    return {
      case_a: "",
      case_b: "",
      prediction_prompt: "",
      invariant_principle: "",
      transfer_prompt: "",
      transfer_expected: "",
    };
  }
  if (type === "socratic") {
    return { central_dilemma: "", initial_probe: "", counterexamples: [""], target_synthesis: "" };
  }
  if (type === "curiosity") {
    return { phenomenon_hook: "", prediction_question: "", bridge_to_unit: "", wonder_branches: [] };
  }
  if (type === "worked_example") {
    return {
      problem_statement: "",
      steps: [
        { step_text: "", rationale: "" },
        { step_text: "", rationale: "" },
      ],
      faded_step_index: 1,
      solo_problem: "",
      solo_expected_answer: "",
    };
  }
  if (type === "spot_the_flaw") {
    return { rookie_work: "", flaw_description: "", underlying_misconception: "", corrected_version: "" };
  }
  if (type === "teach_back") {
    return { peer_persona_prompt: "", required_concepts: [""], peer_follow_up_question: "" };
  }
  if (type === "explanation") {
    return {
      block_title: "",
      topics: [blankExplanationTopic(1)],
      summary_takeaway: "",
    };
  }
  return {
    recall_prompt: "",
    expected_fact: "",
    elaborative_why_prompt: "",
    expected_why_rationale: "",
  };
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
