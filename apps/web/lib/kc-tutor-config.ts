import { BLOCK_TYPES } from "./kc-blocks.ts";
import type { KcBlockType } from "./kc.ts";

export type ConfigField =
  | { key: string; label: string; help: string; kind: "enum"; options: readonly (readonly [string, string])[] }
  | { key: string; label: string; help: string; kind: "int"; min: number; max: number }
  | { key: string; label: string; help: string; kind: "bool" };

export type KcTutorConfig = {
  overarching: Record<string, string>;
  blocks: Record<string, Record<string, string | number | boolean>>;
};

const ENUM = (
  key: string,
  label: string,
  help: string,
  options: readonly (readonly [string, string])[],
): ConfigField => ({ key, label, help, kind: "enum", options });

const INT = (key: string, label: string, help: string, min: number, max: number): ConfigField => ({
  key,
  label,
  help,
  kind: "int",
  min,
  max,
});

const BOOL = (key: string, label: string, help: string): ConfigField => ({ key, label, help, kind: "bool" });

export const OVERARCHING_FIELDS: ConfigField[] = [
  ENUM("orient_framing", "Orient framing", "How the component outline is introduced before the first block.", [
    ["none", "None"],
    ["brief_hook", "Brief hook"],
    ["elaborate_outline", "Elaborate outline"],
  ]),
  ENUM("stay_on_course", "Stay on course", "What the tutor does when the learner leaves the component.", [
    ["strict", "Strict"],
    ["brief_answer_then_return", "Brief answer, then return"],
    ["exploratory", "Exploratory"],
  ]),
  ENUM("misconception_policy", "Misconception policy", "How a named misconception is handled.", [
    ["explain_and_retry_once", "Explain and retry once"],
    ["immediate_redirect", "Immediate redirect"],
  ]),
  ENUM("encouragement_style", "Encouragement style", "Process praise names the reasoning move. Minimal stays quiet.", [
    ["process_praise", "Process praise"],
    ["minimal", "Minimal"],
  ]),
  ENUM("close_summary_depth", "Close summary depth", "How the tutor closes a finished component.", [
    ["concise", "Concise"],
    ["restate_in_learner_words", "Restate in the learner's words"],
    ["diagnostic_strengths_and_gaps", "Diagnostic strengths and gaps"],
  ]),
];

export const BLOCK_CONFIG_FIELDS: Record<KcBlockType, ConfigField[]> = {
  topic_goal: [
    INT("explanation_depth", "Explanation depth", "1 asks the goal first. 5 teaches thoroughly before asking.", 1, 5),
    INT("max_retries_before_reveal", "Retries before reveal", "Misses before the tutor reveals the goal and marks the block fragile.", 1, 5),
    ENUM("hint_ladder_style", "Hint ladder", "How hints escalate after a miss.", [
      ["progressive_nudge_analogy_scaffold", "Nudge, analogy, then scaffold"],
      ["socratic_questions_only", "Socratic questions only"],
      ["direct_scaffold", "Direct scaffold"],
    ]),
    ENUM("goal_evaluation_strictness", "Goal evaluation", "How closely an answer must match the goal.", [
      ["conceptual_gist", "Conceptual gist"],
      ["precise_vocabulary", "Precise vocabulary"],
      ["applied_transfer", "Applied transfer"],
    ]),
    BOOL("fragment_self_explanation", "Ask for a full sentence", "A one- or two-word answer gets one follow-up for a complete sentence."),
    ENUM("enrichment_mode", "Enrichment", "When extra explanation is offered.", [
      ["direct", "Direct"],
      ["on_request", "On request"],
      ["offer", "Offer"],
    ]),
  ],
  mcq: [
    INT("max_retry_attempts", "Retry attempts", "Attempts before the right option is revealed.", 1, 4),
    INT("wrong_answer_explanation_depth", "Wrong-answer depth", "1 is a nudge. 3 contrasts the distractor before the retry.", 1, 3),
    BOOL("disable_eliminated_choices", "Disable eliminated choices", "Already-chosen wrong options are greyed out on retry."),
    ENUM("confirm_why_on_correct", "Ask why it is correct", "When a correct pick must be explained.", [
      ["never", "Never"],
      ["on_retry_only", "On a retry only"],
      ["always", "Always"],
    ]),
    ENUM("correct_pass_explanation_depth", "Pass explanation", "How the tutor confirms a correct option.", [
      ["brief_confirm", "Brief confirm"],
      ["reinforce_why", "Reinforce why"],
    ]),
  ],
  case_study: [
    ENUM("case_presentation", "Case presentation", "Predict then contrast, or both cases in one turn.", [
      ["sequential_predict_then_contrast", "Predict, then contrast"],
      ["side_by_side_single_turn", "Side by side"],
    ]),
    INT("explanation_depth", "Explanation depth", "How much scaffolding the contrast gets.", 1, 5),
    INT("max_retries_before_reveal", "Retries before reveal", "Attempts to state the principle before it is revealed.", 1, 5),
    BOOL("require_transfer_application", "Require transfer", "Run the transfer substep when the block has one."),
  ],
  socratic: [
    INT("dialogue_depth_turns", "Dialogue turns", "Probing turns before the learner must synthesize.", 1, 4),
    ENUM("challenge_intensity", "Challenge intensity", "How hard the tutor pushes back.", [
      ["gentle_clarification", "Gentle clarification"],
      ["counterexample_entrapment", "Counterexample"],
      ["devil_advocate", "Devil's advocate"],
    ]),
    INT("max_retries_before_reveal", "Retries before reveal", "Attempts on the target synthesis before the tutor states it.", 1, 5),
    ENUM("hint_when_stuck", "Hint when stuck", "What the tutor offers when the dialogue stalls.", [
      ["highlight_contradiction", "Highlight the contradiction"],
      ["give_analogy", "Give an analogy"],
    ]),
  ],
  curiosity: [
    INT("max_wonder_turns", "Wonder turns", "Back-and-forth turns before the bridge into the next block.", 1, 3),
    BOOL("require_initial_prediction", "Require a prediction", "The learner guesses before hearing the bridge."),
    BOOL("counts_toward_mastery_score", "Counts toward mastery", "When off, a bold guess does not mark the component fragile."),
    ENUM("hook_framing_style", "Hook framing", "The shape of the opening hook.", [
      ["mystery_paradox", "Mystery or paradox"],
      ["real_world_surprise", "Real-world surprise"],
      ["thought_experiment", "Thought experiment"],
    ]),
  ],
  worked_example: [
    ENUM("fading_level", "Fading level", "How much of the worked example is left blank.", [
      ["single_blanked_step", "One blanked step"],
      ["two_steps", "Two steps"],
    ]),
    BOOL("require_step_self_explanation", "Require a why", "The learner explains why the blanked step works."),
    INT("max_retries_before_reveal", "Retries before reveal", "Retries on the faded step and the solo problem.", 1, 4),
    INT("wrong_step_explanation_depth", "Wrong-step depth", "How deeply a slip on the faded or solo step is diagnosed.", 1, 3),
  ],
  spot_the_flaw: [
    ENUM("critique_depth", "Critique depth", "Identify the flaw, or identify it and correct it.", [
      ["identify_only", "Identify only"],
      ["identify_and_correct", "Identify and correct"],
    ]),
    INT("wrong_answer_explanation_depth", "Wrong-answer depth", "How deeply a missed flaw is highlighted.", 1, 3),
    INT("max_retries_before_reveal", "Retries before reveal", "Attempts before the flaw is revealed.", 1, 4),
    BOOL("show_misconception_why", "Name why the trap is tempting", "After the flaw is caught, the tutor names why it was tempting."),
  ],
  teach_back: [
    ENUM("peer_confusion_level", "Peer confusion", "How the imagined peer pushes back.", [
      ["curious_beginner", "Curious beginner"],
      ["stubborn_misconception", "Stubborn misconception"],
    ]),
    INT("follow_up_questions_count", "Follow-up questions", "Peer pushback questions after the first explanation.", 0, 2),
    INT("max_retries_before_reveal", "Retries before reveal", "Attempts to cover missing concepts before the tutor completes them.", 1, 4),
    ENUM("evaluation_strictness", "Evaluation", "Plain-language clarity, or every required concept named exactly.", [
      ["plain_language_clarity", "Plain-language clarity"],
      ["all_required_concepts_exact", "Every required concept"],
    ]),
  ],
  retrieval_check: [
    ENUM("cue_scaffolding", "Cue scaffolding", "Free recall first, or a cue after the first miss.", [
      ["free_recall_first", "Free recall first"],
      ["cued_hint_on_first_miss", "Cue on the first miss"],
    ]),
    BOOL("require_elaborative_why", "Ask why", "After the fact is recalled, ask why it is so."),
    INT("max_retries_before_reveal", "Retries before reveal", "Attempts before the fact is revealed.", 1, 4),
    BOOL("accept_paraphrase", "Accept a paraphrase", "A restatement counts when it carries the fact."),
  ],
};

export const BLOCK_CONFIG_TITLES: Record<KcBlockType, string> = {
  topic_goal: "Topic / Goal",
  mcq: "Multiple Choice Question",
  case_study: "Case Study / Contrasting Cases",
  socratic: "Socratic Discussion",
  curiosity: "Curiosity / Wonder",
  worked_example: "Worked Example + Faded Step",
  spot_the_flaw: "Spot the Flaw / Buggy Rule",
  teach_back: "Teach-Back / Feynman",
  retrieval_check: "Retrieval & Elaborative Interrogation",
};

function fieldDefault(field: ConfigField): string | number | boolean {
  if (field.kind === "bool") return true;
  if (field.kind === "int") return Math.min(field.max, Math.max(field.min, 2));
  return field.options[0][0];
}

function defaults(): KcTutorConfig {
  const overarching: Record<string, string> = {
    orient_framing: "elaborate_outline",
    stay_on_course: "brief_answer_then_return",
    misconception_policy: "explain_and_retry_once",
    encouragement_style: "process_praise",
    close_summary_depth: "diagnostic_strengths_and_gaps",
  };
  const blocks: KcTutorConfig["blocks"] = {};
  for (const type of BLOCK_TYPES) {
    const values: Record<string, string | number | boolean> = {};
    for (const field of BLOCK_CONFIG_FIELDS[type]) values[field.key] = fieldDefault(field);
    blocks[type] = values;
  }
  blocks.topic_goal.explanation_depth = 3;
  blocks.topic_goal.max_retries_before_reveal = 3;
  blocks.topic_goal.hint_ladder_style = "progressive_nudge_analogy_scaffold";
  blocks.topic_goal.goal_evaluation_strictness = "conceptual_gist";
  blocks.topic_goal.fragment_self_explanation = true;
  blocks.topic_goal.enrichment_mode = "on_request";
  blocks.mcq.max_retry_attempts = 2;
  blocks.mcq.wrong_answer_explanation_depth = 2;
  blocks.mcq.disable_eliminated_choices = true;
  blocks.mcq.confirm_why_on_correct = "on_retry_only";
  blocks.mcq.correct_pass_explanation_depth = "reinforce_why";
  blocks.case_study.case_presentation = "sequential_predict_then_contrast";
  blocks.case_study.explanation_depth = 3;
  blocks.case_study.max_retries_before_reveal = 3;
  blocks.case_study.require_transfer_application = true;
  blocks.socratic.dialogue_depth_turns = 2;
  blocks.socratic.challenge_intensity = "counterexample_entrapment";
  blocks.socratic.max_retries_before_reveal = 3;
  blocks.socratic.hint_when_stuck = "highlight_contradiction";
  blocks.curiosity.max_wonder_turns = 2;
  blocks.curiosity.require_initial_prediction = true;
  blocks.curiosity.counts_toward_mastery_score = false;
  blocks.curiosity.hook_framing_style = "mystery_paradox";
  blocks.worked_example.fading_level = "single_blanked_step";
  blocks.worked_example.require_step_self_explanation = true;
  blocks.worked_example.max_retries_before_reveal = 2;
  blocks.worked_example.wrong_step_explanation_depth = 2;
  blocks.spot_the_flaw.critique_depth = "identify_and_correct";
  blocks.spot_the_flaw.wrong_answer_explanation_depth = 2;
  blocks.spot_the_flaw.max_retries_before_reveal = 2;
  blocks.spot_the_flaw.show_misconception_why = true;
  blocks.teach_back.peer_confusion_level = "curious_beginner";
  blocks.teach_back.follow_up_questions_count = 1;
  blocks.teach_back.max_retries_before_reveal = 2;
  blocks.teach_back.evaluation_strictness = "plain_language_clarity";
  blocks.retrieval_check.cue_scaffolding = "cued_hint_on_first_miss";
  blocks.retrieval_check.require_elaborative_why = true;
  blocks.retrieval_check.max_retries_before_reveal = 2;
  blocks.retrieval_check.accept_paraphrase = true;
  return { overarching, blocks };
}

export const DEFAULT_KC_TUTOR_CONFIG: KcTutorConfig = defaults();

function accepts(field: ConfigField, value: unknown): value is string | number | boolean {
  if (field.kind === "bool") return typeof value === "boolean";
  if (field.kind === "int") return typeof value === "number" && Number.isInteger(value) && value >= field.min && value <= field.max;
  return typeof value === "string" && field.options.some(([id]) => id === value);
}

/** Fill any missing or invalid tutor-config value from the academic defaults. */
export function kcTutorConfigFrom(raw: unknown): KcTutorConfig {
  const next = defaults();
  if (!raw || typeof raw !== "object") return next;
  const source = raw as { overarching?: Record<string, unknown>; blocks?: Record<string, unknown> };
  const over = source.overarching;
  if (over && typeof over === "object") {
    for (const field of OVERARCHING_FIELDS) {
      if (accepts(field, over[field.key])) next.overarching[field.key] = over[field.key] as string;
    }
  }
  const blocks = source.blocks;
  if (blocks && typeof blocks === "object") {
    for (const type of BLOCK_TYPES) {
      const incoming = blocks[type];
      if (!incoming || typeof incoming !== "object") continue;
      const values = incoming as Record<string, unknown>;
      for (const field of BLOCK_CONFIG_FIELDS[type]) {
        if (accepts(field, values[field.key])) next.blocks[type][field.key] = values[field.key] as string | number | boolean;
      }
    }
  }
  return next;
}
