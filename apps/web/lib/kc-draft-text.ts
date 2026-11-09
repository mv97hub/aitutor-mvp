import type { KcComponentDraft } from "./kc";

/** Catalog type labels. The same strings the stored reply uses. */
const TYPE_LABELS: Record<string, string> = {
  topic_goal: "Topic / Goal",
  mcq: "Multiple Choice Question",
  case_study: "Case Study / Contrasting Cases",
  socratic: "Socratic Discussion",
  curiosity: "Curiosity / Wonder Hook",
  worked_example: "Worked Example + Faded Step",
  spot_the_flaw: "Spot the Flaw / Buggy Rule",
  teach_back: "Teach-Back / Feynman",
  retrieval_check: "Retrieval & Elaborative Interrogation",
};

const CATALOG_FIELDS: Record<string, [string, string][]> = {
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
};

type DraftBlock = { type?: string; data?: Record<string, unknown> };

function textOf(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value == null) return "";
  return String(value).trim();
}

function fieldLines(key: string, label: string, value: unknown): string[] {
  if (key === "choices") return choiceLines(value);
  if (key === "steps") return stepLines(value);
  if (Array.isArray(value)) {
    const items = value
      .filter((item) => item != null && (typeof item !== "object" || item === null))
      .map((item) => String(item).trim())
      .filter(Boolean);
    return items.length ? [`${label}: ${items.join("; ")}`] : [];
  }
  if (typeof value === "boolean") return [`${label}: ${value ? "yes" : "no"}`];
  if (typeof value === "number") return [`${label}: ${value}`];
  if (value == null) return [];
  const text = textOf(value);
  return text ? [`${label}: ${text}`] : [];
}

function choiceLines(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const rows: string[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const choice = item as Record<string, unknown>;
    const letter = textOf(choice.id);
    const text = textOf(choice.text);
    const head = letter && text ? `${letter}. ${text}` : text || letter;
    if (!head) continue;
    const notes: string[] = [];
    if (choice.is_correct === true) notes.push("correct");
    const trap = textOf(choice.distractor_rationale);
    if (trap) notes.push(`trap: ${trap}`);
    const code = textOf(choice.misconception_code);
    if (code) notes.push(`misconception: ${code}`);
    rows.push(`- ${head}${notes.length ? ` (${notes.join("; ")})` : ""}`);
  }
  return rows.length ? ["Choices:", ...rows] : [];
}

function stepLines(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const rows: string[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const step = item as Record<string, unknown>;
    const text = textOf(step.step_text);
    const why = textOf(step.rationale);
    if (text && why) rows.push(`- ${text} (${why})`);
    else if (text) rows.push(`- ${text}`);
    else if (why) rows.push(`- ${why}`);
  }
  return rows.length ? ["Steps:", ...rows] : [];
}

function blockLines(raw: unknown): string[] {
  if (!Array.isArray(raw) || raw.length === 0) return ["Blocks: none"];
  const lines: string[] = [];
  let shown = 0;
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const block = item as DraftBlock;
    const kind = textOf(block.type);
    if (!kind) continue;
    shown += 1;
    lines.push(`${shown}. ${TYPE_LABELS[kind] ?? kind}`);
    const data = block.data && typeof block.data === "object" ? block.data : {};
    for (const [key, label] of CATALOG_FIELDS[kind] ?? []) {
      if (!Object.prototype.hasOwnProperty.call(data, key)) continue;
      lines.push(...fieldLines(key, label, data[key]));
    }
  }
  return lines.length ? lines : ["Blocks: none"];
}

function codes(value: unknown): string {
  if (!Array.isArray(value)) return "none";
  const kept = value.map((item) => textOf(item)).filter(Boolean);
  return kept.length ? kept.join(", ") : "none";
}

/** The same block-field text the API stores, so a reloaded thread matches the bubble. */
export function draftReplyText(draft: Partial<KcComponentDraft> & { title?: string }): string {
  const title = textOf(draft.title) || "this component";
  const lines = [`Draft for ${title} only. Other components stay as they are.`];
  const description = textOf(draft.description);
  if (description) lines.push(`Description: ${description}`);
  lines.push(`Outline: ${textOf(draft.outline) || "none"}`);
  lines.push(...blockLines(draft.blocks));
  lines.push(`Core truth: ${textOf(draft.core_truth) || "none"}`);
  const wrongs: string[] = [];
  for (const item of draft.misconceptions ?? []) {
    if (!item) continue;
    const wrong = textOf(item.wrong_move);
    const broken = textOf(item.broken_kc);
    if (wrong || broken) wrongs.push(broken ? `${wrong} (${broken})` : wrong);
  }
  lines.push(`Misconceptions: ${wrongs.length ? wrongs.join("; ") : "none"}`);
  lines.push(`Prerequisites: ${codes(draft.prerequisite_codes)}`);
  lines.push(`Encompasses: ${codes(draft.encompasses_codes)}`);
  lines.push("Nothing is saved until you push it.");
  return lines.join("\n");
}

/** Prose from the discussion, then each block's filled catalog fields. */
export function creatorBubbleText(content: string, draft: KcComponentDraft | null): string {
  if (!draft) return content;
  const body = draftReplyText(draft);
  const marker = "\n\nDraft for ";
  const index = content.lastIndexOf(marker);
  const prose = (index >= 0 ? content.slice(0, index) : content).trim();
  return prose ? `${prose}\n\n${body}` : body;
}
