/** Turn stored harness turns and findings into observations.

An observation quotes the child and the tutor from the transcript and, when a
stored prompt line was in force, names that line. Nothing here edits
kc_prompt.py or kc_loop.py, and nothing here proposes new prompt wording.
*/

import { type RecommendationCard } from "./harness.ts";

export const RECOMMENDATION_DOC =
  "/cursor/stores/bc-755f27de-cf8f-4751-bc70-3f161bf28a51/docs/harness-prompt-recommendations.md";

export type DraftFinding = {
  title?: string;
  tag?: string;
  block_label?: string;
  count?: number;
  cause_class?: string;
  place?: string;
  run_id?: string;
  examples?: { chat_id?: string; turn?: number; block?: string; child?: string; run_id?: string }[];
  nudges?: StuckNudge[];
};

export type StuckNudge = {
  turn?: number;
  asked?: string;
  answered?: string;
  block_type?: string;
  block_id?: string;
  substep?: string;
  child?: string;
  run_id?: string;
};

export type DraftSource = {
  run_id?: string;
  turn?: number;
  block_type?: string;
  chat_id?: string;
};

export type BuilderExcerpt = {
  symbol: string;
  section: string;
  function: string;
  source: string;
  literals?: string[];
};

export type ExampleTurn = {
  chat_id?: string;
  turn?: number;
  intent?: string;
  child_text?: string;
  tutor_reply?: string;
  block_label?: string;
  block_title?: string;
  block_id?: string;
  substep?: string;
  tutor_prompt?: string;
  sections?: Record<string, string>;
  run_id?: string;
};

export type DraftMaterials = {
  run_id?: string;
  findings?: DraftFinding[] | { findings?: DraftFinding[] };
  examples?: ExampleTurn[];
  builder?: BuilderExcerpt[];
  runs?: DraftMaterials[];
};

export type DraftEvidence = {
  summary?: string;
  block_type?: string;
  section?: string;
  function?: string;
  symbol?: string;
  current?: string;
  replacement?: string;
  shorter?: string;
  nudges?: StuckNudge[];
  sources?: DraftSource[];
  findings?: { tag?: string; title?: string }[];
  block_title?: string;
  substep?: string;
  child_text?: string;
  tutor_reply?: string;
  turn?: number;
  run_id?: string;
  fault?: string;
  mismatch?: string;
};

export type DraftCard = RecommendationCard & {
  evidence: DraftEvidence;
  proposed: { text: string; shorter: string };
};

export type ModelDraft = {
  current_quote?: string;
  replacement?: string;
  shorter?: string;
  evidence_summary?: string;
};

const TAG_SYMBOLS: Record<string, string[]> = {
  stuck: ["_GOAL_START_DEEPEN", "_GOAL_START_EXPLAIN", "_GOAL_START_ASIDE", "_how_to_teach"],
  one_question: ["_GOAL_START_DEEPEN", "_GOAL_START_EXPLAIN", "_GOAL_START_ASK", "_GOAL_START_ASIDE", "_how_to_teach"],
  stay_on_course: ["_GOAL_START_ASIDE", "_GOAL_START_CLARIFY", "_SIDE_STAY", "_how_to_teach"],
  repeated_itself: ["_block_config_rules", "_how_to_teach", "_this_turn"],
  ignored_question: ["_GOAL_START_ASIDE", "_GOAL_START_CLARIFY", "_SIDE_STAY"],
};

// Old stored prompts say "more deeply". The current Tell me more line says
// "still on the explanation" and "from a fresh angle".
const STUCK_LINE = /more deeply|still on the explanation|from a fresh angle/;

const TAG_PREFER: Record<string, RegExp> = {
  stuck: new RegExp(`${STUCK_LINE.source}|why it matters|do not ask any question`),
  one_question: /do not ask any question|one question/,
  stay_on_course: /side remark|question they typed/,
  repeated_itself: /nudge|hint|missed answer/,
  ignored_question: /question they typed|side remark|answer that question/,
};

export function nudgeSentences(nudges: StuckNudge[], block: string): string[] {
  return nudges.map((nudge) => {
    const named = nudge.block_type || block || "an unknown block";
    const place = [nudge.block_id, nudge.substep].filter(Boolean).join(" / ");
    const where = place ? `${named} (${place})` : named;
    return `Turn ${nudge.turn ?? ""}: the child asked "${nudge.asked || ""}". The tutor answered "${nudge.answered || ""}". ${where} did not move.`;
  });
}

export function fold(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

export function findingsOf(materials: DraftMaterials): DraftFinding[] {
  const raw = materials.findings;
  if (Array.isArray(raw)) return raw.filter((item) => item && typeof item === "object");
  if (raw && Array.isArray(raw.findings)) return raw.findings.filter((item) => item && typeof item === "object");
  return [];
}

export const RECENT_RUN_PICKS = 3;

export function defaultSelectedRunIds(runIds: string[], count = RECENT_RUN_PICKS): string[] {
  return runIds.filter(Boolean).slice(0, count);
}

export function skippedRunMessage(failures: { runId: string; message: string }[]): string {
  const named = failures
    .filter((item) => item.runId)
    .map((item) => `${item.runId}: ${item.message || "Could not read this run."}`);
  if (named.length === 0) return "";
  return `Could not read ${named.join("; ")}. The other selected runs were still drafted.`;
}

export function materialsFromRuns(runs: DraftMaterials[]): DraftMaterials {
  const findings: DraftFinding[] = [];
  const examples: ExampleTurn[] = [];
  let builder: BuilderExcerpt[] = [];
  const ids: string[] = [];
  for (const run of runs) {
    const runId = String(run.run_id || "");
    if (runId) ids.push(runId);
    if (builder.length === 0 && run.builder && run.builder.length > 0) builder = run.builder;
    for (const finding of findingsOf(run)) {
      findings.push({
        ...finding,
        run_id: finding.run_id || runId,
        nudges: (finding.nudges || []).map((nudge) => ({ ...nudge, run_id: nudge.run_id || runId })),
        examples: (finding.examples || []).map((example) => ({ ...example, run_id: example.run_id || runId })),
      });
    }
    for (const example of run.examples || []) {
      examples.push({ ...example, run_id: example.run_id || runId });
    }
  }
  return { run_id: ids.join(","), findings, examples, builder };
}

export function flattenMaterials(materials: DraftMaterials): DraftMaterials {
  if (materials.runs && materials.runs.length > 0) return materialsFromRuns(materials.runs);
  return materialsFromRuns([materials]);
}

function namedBlock(value?: string): string {
  const text = (value || "").trim();
  if (!text || text === "an unknown block") return "";
  return text;
}

function uniqueText(values: string[]): string[] {
  const seen: string[] = [];
  for (const value of values) {
    const text = value.trim();
    if (text && !seen.includes(text)) seen.push(text);
  }
  return seen;
}

export function sourceSentences(sources: DraftSource[]): string[] {
  return sources.map((source) => {
    const run = source.run_id || "an unknown run";
    const turn = source.turn === undefined || source.turn === null ? "" : ` turn ${source.turn}`;
    const block = source.block_type || "an unknown block";
    return `Run ${run}${turn}, ${block}.`;
  });
}

function appearsIn(prompt: string, sentence: string): boolean {
  const needle = fold(sentence).toLowerCase();
  if (needle.length < 20) return false;
  return fold(prompt).toLowerCase().includes(needle);
}

function quoteFromPrompt(prompt: string, sentence: string): string {
  const folded = fold(sentence);
  if (prompt.includes(sentence)) return sentence;
  if (prompt.includes(folded)) return folded;
  if (appearsIn(prompt, folded)) return folded;
  return "";
}

function literalsOf(excerpt: BuilderExcerpt): string[] {
  if (excerpt.literals && excerpt.literals.length > 0) return excerpt.literals;
  const found: string[] = [];
  const pattern = /"([^"\\]|\\.){40,}"|'([^'\\]|\\.){40,}'/g;
  for (const match of excerpt.source.matchAll(pattern)) {
    const raw = match[0].slice(1, -1);
    if (raw) found.push(fold(raw));
  }
  return found;
}

function scoreLiteral(tag: string, literal: string): number {
  const text = literal.toLowerCase();
  const prefer = TAG_PREFER[tag];
  let score = Math.min(literal.length, 400);
  if (prefer && prefer.test(text)) score += 2000;
  if (tag === "one_question" && text.includes("side remark")) score -= 800;
  if (tag === "stuck" && STUCK_LINE.test(text)) score += 400;
  return score;
}

function pickQuote(
  tag: string,
  excerpts: BuilderExcerpt[],
  prompts: string[],
): { excerpt: BuilderExcerpt; current: string } | null {
  const symbols = new Set(TAG_SYMBOLS[tag] || []);
  let best: { excerpt: BuilderExcerpt; current: string; score: number } | null = null;
  for (const excerpt of excerpts) {
    for (const literal of literalsOf(excerpt)) {
      for (const prompt of prompts) {
        const current = quoteFromPrompt(prompt, literal);
        if (!current) continue;
        let score = scoreLiteral(tag, literal);
        if (symbols.size === 0 || symbols.has(excerpt.symbol)) score += 500;
        if (!best || score > best.score) best = { excerpt, current, score };
      }
    }
  }
  return best ? { excerpt: best.excerpt, current: best.current } : null;
}

function nudgeKey(nudge: StuckNudge, runId: string): string {
  return `${nudge.run_id || runId}|${nudge.turn ?? ""}|${nudge.asked || ""}|${nudge.block_type || ""}`;
}

const FAULTS: Record<string, string> = {
  ignored_question: "The tutor ignored the child's question.",
  repeated_itself: "The tutor repeated itself.",
  stuck: "The step stayed where it was.",
  too_long: "The tutor's reply was too long.",
  generic_praise: "The tutor gave generic praise.",
  missed_boredom: "The tutor missed that the child was bored.",
  false_pass: "A wrong answer was marked as passed.",
  stay_on_course: "The tutor did not stay on course.",
  one_question: "The tutor did not keep to one question.",
  gave_away_answer: "The tutor gave away the answer.",
  vocabulary_too_hard: "The tutor's words were too hard.",
  missed_frustration: "The tutor missed the child's frustration.",
  abrupt_return: "The tutor returned to the lesson abruptly.",
  talked_down: "The tutor talked down to the child.",
  factual_error: "The tutor's reply had a factual error.",
};

const FAULT_TITLES: Record<string, string> = {
  ignored_question: "ignored the child's question",
  repeated_itself: "repeated itself",
  stuck: "stayed on the step",
  too_long: "too long",
  generic_praise: "generic praise",
  missed_boredom: "missed boredom",
  false_pass: "false pass",
  stay_on_course: "left the step",
  one_question: "more than one question",
  gave_away_answer: "gave away the answer",
  vocabulary_too_hard: "words too hard",
  missed_frustration: "missed frustration",
};

type Moment = {
  key: string;
  run_id: string;
  chat_id: string;
  turn: number;
  tag: string;
  title: string;
  cause: string;
  block_type: string;
  block_title: string;
  substep: string;
  child: string;
  tutor: string;
  prompt: string;
  fromNudge: boolean;
  nudges: StuckNudge[];
};

function momentKey(runId: string, chatId: string, turn: number, tag: string): string {
  return `${runId}|${chatId}|${turn}|${tag}`;
}

function storedTurn(examples: ExampleTurn[], runId: string, chatId: string, turn: number): ExampleTurn | undefined {
  return examples.find((item) => {
    if (runId && item.run_id && item.run_id !== runId) return false;
    if (chatId && item.chat_id && item.chat_id !== chatId) return false;
    return Number(item.turn) === turn;
  });
}

function faultSentence(tag: string, fromNudge: boolean): string {
  if (fromNudge) return "The child nudged and the step did not move.";
  return FAULTS[tag] || `The turn was marked ${tag.replaceAll("_", " ")}.`;
}

function faultTitle(tag: string, fromNudge: boolean): string {
  if (fromNudge) return "nudge with no movement";
  return FAULT_TITLES[tag] || tag.replaceAll("_", " ");
}

function lineHome(symbol: string, quote: string): string {
  const text = quote.trim();
  if (symbol.startsWith("_GOAL_") || /^Goal (start|question|answer)\b/i.test(text) || text.startsWith("Ready check:")) {
    return "Topic / Goal";
  }
  if (symbol.startsWith("_EXPLANATION")) return "Explanatory Walkthrough";
  return "";
}

function mergeMoment(map: Map<string, Moment>, moment: Moment) {
  const prev = map.get(moment.key);
  if (!prev) {
    map.set(moment.key, moment);
    return;
  }
  if (!prev.child && moment.child) prev.child = moment.child;
  if (!prev.tutor && moment.tutor) prev.tutor = moment.tutor;
  if (!prev.prompt && moment.prompt) prev.prompt = moment.prompt;
  if (!prev.block_type && moment.block_type) prev.block_type = moment.block_type;
  if (!prev.block_title && moment.block_title) prev.block_title = moment.block_title;
  if (!prev.substep && moment.substep) prev.substep = moment.substep;
  if (moment.fromNudge) {
    prev.fromNudge = true;
    const seen = new Set(prev.nudges.map((nudge) => nudgeKey(nudge, prev.run_id)));
    for (const nudge of moment.nudges) {
      const key = nudgeKey(nudge, prev.run_id);
      if (seen.has(key)) continue;
      seen.add(key);
      prev.nudges.push(nudge);
    }
  }
}

function momentFromTurn(
  finding: DraftFinding,
  turnNo: number,
  chatId: string,
  stored: ExampleTurn | undefined,
  child: string,
  tutor: string,
  fromNudge: boolean,
  nudges: StuckNudge[],
): Moment | null {
  const spokenChild = fold(child);
  const spokenTutor = fold(tutor);
  if (!spokenChild && !spokenTutor) return null;
  const runId = stored?.run_id || finding.run_id || "";
  const tag = String(finding.tag || "finding");
  const block = namedBlock(stored?.block_label) || namedBlock(finding.block_label);
  return {
    key: momentKey(runId, chatId || stored?.chat_id || "", turnNo, tag),
    run_id: runId,
    chat_id: chatId || stored?.chat_id || "",
    turn: turnNo,
    tag,
    title: finding.title || tag,
    cause: finding.cause_class || "prompt",
    block_type: block,
    block_title: fold(stored?.block_title || ""),
    substep: fold(stored?.substep || ""),
    child: spokenChild,
    tutor: spokenTutor,
    prompt: stored?.tutor_prompt || "",
    fromNudge,
    nudges,
  };
}

function draftFlatCards(materials: DraftMaterials): DraftCard[] {
  const findings = findingsOf(materials);
  const examples = materials.examples || [];
  const builder = materials.builder || [];
  const moments = new Map<string, Moment>();
  for (const finding of findings) {
    const runId = finding.run_id || "";
    for (const listed of finding.examples || []) {
      const turnNo = Number(listed.turn);
      if (Number.isNaN(turnNo)) continue;
      const chatId = listed.chat_id || "";
      const stored = storedTurn(examples, listed.run_id || runId, chatId, turnNo);
      const moment = momentFromTurn(finding, turnNo, chatId, stored, stored?.child_text || "", stored?.tutor_reply || "", false, []);
      if (moment) mergeMoment(moments, moment);
    }
    if (String(finding.tag || "") !== "stuck") continue;
    for (const nudge of finding.nudges || []) {
      const turnNo = Number(nudge.turn);
      if (Number.isNaN(turnNo)) continue;
      const chatId = "";
      const stored = storedTurn(examples, nudge.run_id || runId, chatId, turnNo);
      const carried: StuckNudge = { ...nudge, run_id: nudge.run_id || runId };
      const moment = momentFromTurn(
        finding,
        turnNo,
        stored?.chat_id || chatId,
        stored
          ? {
              ...stored,
              block_label: stored.block_label || nudge.block_type,
              substep: stored.substep || nudge.substep,
            }
          : {
              run_id: nudge.run_id || runId,
              turn: turnNo,
              block_label: nudge.block_type,
              substep: nudge.substep,
              block_id: nudge.block_id,
            },
        stored?.child_text || nudge.asked || "",
        stored?.tutor_reply || nudge.answered || "",
        true,
        [carried],
      );
      if (moment) mergeMoment(moments, moment);
    }
  }
  const ordered = [...moments.values()].sort((a, b) => a.run_id.localeCompare(b.run_id) || a.turn - b.turn || a.tag.localeCompare(b.tag));
  return ordered.map((moment) => observationCard(moment, builder));
}

function observationCard(moment: Moment, builder: BuilderExcerpt[]): DraftCard {
  const picked = moment.prompt ? pickQuote(moment.fromNudge ? "stuck" : moment.tag, builder, [moment.prompt]) : null;
  const quote = picked && appearsIn(moment.prompt, picked.current) ? quoteFromPrompt(moment.prompt, picked.current) || picked.current : "";
  const home = picked && quote ? lineHome(picked.excerpt.symbol, quote) : "";
  const mismatch =
    home && moment.block_type && fold(home).toLowerCase() !== fold(moment.block_type).toLowerCase()
      ? `This line is for ${home}. The turn was on ${moment.block_type}. Those block types do not match.`
      : "";
  const fault = faultSentence(moment.tag, moment.fromNudge);
  const block = moment.block_type || "an unknown block";
  const title = `Turn ${moment.turn}: ${faultTitle(moment.tag, moment.fromNudge)}`;
  const nudgeLines = nudgeSentences(moment.nudges, block);
  return {
    title: title.slice(0, 200),
    cause_class: moment.cause || "prompt",
    place: `${block}${moment.substep ? ` · ${moment.substep}` : ""} · turn ${moment.turn}`,
    kind: "setting",
    prompt_direction: "same",
    risk: "This is an observation from the stored turn. It does not change the live tutor prompt.",
    confidence: "high",
    block_type: block,
    proposed: { text: "", shorter: "" },
    evidence: {
      summary: fault,
      fault,
      block_type: block,
      block_title: moment.block_title,
      substep: moment.substep,
      section: picked && quote ? picked.excerpt.section : "",
      function: picked && quote ? picked.excerpt.function : "",
      symbol: picked && quote ? picked.excerpt.symbol : "",
      current: quote,
      mismatch,
      child_text: moment.child,
      tutor_reply: moment.tutor,
      turn: moment.turn,
      run_id: moment.run_id,
      nudges: nudgeLines.length ? moment.nudges : undefined,
      sources: [
        {
          run_id: moment.run_id,
          turn: moment.turn,
          block_type: block,
          chat_id: moment.chat_id,
        },
      ],
      findings: [{ tag: moment.tag, title: moment.title }],
    },
  };
}

export function draftPromptCards(materials: DraftMaterials): DraftCard[] {
  return draftFlatCards(flattenMaterials(materials));
}

export function prepareDraft(materials: DraftMaterials): { materials: DraftMaterials; cards: DraftCard[] } {
  const flat = flattenMaterials(materials);
  return { materials: flat, cards: draftFlatCards(flat) };
}

export function applyModelReplacements(cards: DraftCard[], modelCards: ModelDraft[]): DraftCard[] {
  return cards.map((card) => {
    const current = fold(card.evidence.current || "");
    const match = modelCards.find((item) => {
      if (fold(item.current_quote || "") !== current) return false;
      const replacement = (item.replacement || "").trim();
      return Boolean(replacement) && fold(replacement).length < current.length;
    });
    if (!match) return card;
    const replacement = (match.replacement || "").trim();
    const shorter = (match.shorter || "").trim();
    return {
      ...card,
      proposed: { text: replacement, shorter: shorter || card.proposed.shorter },
      evidence: {
        ...card.evidence,
        replacement,
        shorter: shorter || card.evidence.shorter,
        summary: match.evidence_summary?.trim() || card.evidence.summary,
      },
    };
  });
}

export function drafterPrompt(materials: DraftMaterials, cards: DraftCard[]): string {
  const stored = (materials.examples || [])
    .slice(0, 4)
    .map((example, index) => {
      const sections = ["This turn", "How to teach", "What to return"]
        .map((name) => (example.sections?.[name] ? `${name}\n${example.sections[name]}` : ""))
        .filter(Boolean)
        .join("\n\n");
      return `Example ${index + 1} turn ${example.turn ?? ""} chat ${example.chat_id ?? ""}\nChild: ${example.child_text || ""}\n${sections || example.tutor_prompt || ""}`;
    })
    .join("\n\n");
  const quoted = cards
    .map(
      (card, index) =>
        `${index}. section ${card.evidence.section}; function ${card.evidence.function}; current_quote: ${card.evidence.current}`,
    )
    .join("\n");
  return [
    "These are observations from stored turns. Do not rewrite them into prompt lines.",
    "The harness does not change the live tutor prompt and does not edit kc_prompt.py.",
    `Observations:\n${quoted}`,
    `Stored turns:\n${stored}`,
  ].join("\n\n");
}

export type SummaryCard = {
  title?: string;
  evidence?: {
    block_type?: string;
    block_title?: string;
    substep?: string;
    section?: string;
    function?: string;
    symbol?: string;
    current?: string;
    sources?: DraftSource[];
    nudges?: StuckNudge[];
    findings?: { tag?: string; title?: string }[];
    child_text?: string;
    tutor_reply?: string;
    turn?: number;
    run_id?: string;
    fault?: string;
    mismatch?: string;
    summary?: string;
  };
};

function shown(value: string | undefined, fallback: string): string {
  const text = fold(value || "");
  return text || fallback;
}

/** Plain text of the observations already on the page. */
export function recommendationPageSummary(cards: SummaryCard[]): string {
  const runs = uniqueText(cards.map((card) => card.evidence?.run_id || card.evidence?.sources?.[0]?.run_id || ""));
  const blocks = uniqueText(cards.map((card) => card.evidence?.block_type || card.evidence?.sources?.[0]?.block_type || ""));
  const lines = [
    "Harness observations",
    "",
    "The harness does not change the live tutor prompt, and it does not edit apps/api/app/kc_prompt.py.",
    "",
    `Runs: ${runs.length}`,
    ...runs,
    `Block types: ${blocks.join(", ") || "none"}`,
    "",
  ];
  cards.forEach((card, index) => {
    const evidence = card.evidence || {};
    const block = evidence.block_type || evidence.sources?.[0]?.block_type || "an unknown block";
    const run = evidence.run_id || evidence.sources?.[0]?.run_id || "unknown";
    const turn = evidence.turn ?? evidence.sources?.[0]?.turn;
    lines.push(`Observation ${index + 1}: ${card.title || "Observation"}`);
    lines.push(`Run: ${run}`);
    lines.push(`Block type: ${block}`);
    lines.push(`Block title: ${shown(evidence.block_title, "not stored")}`);
    lines.push(`Substep: ${shown(evidence.substep, "not stored")}`);
    lines.push(`Turn: ${turn === undefined || turn === null ? "unknown" : String(turn)}`);
    lines.push(`Child: ${shown(evidence.child_text, "not stored")}`);
    lines.push(`Tutor: ${shown(evidence.tutor_reply, "not stored")}`);
    lines.push(`What was suboptimal: ${evidence.fault || evidence.summary || "The stored turn was marked."}`);
    if (evidence.current) {
      const where = [evidence.section, evidence.function].filter(Boolean).join(", ");
      lines.push(`Line in force${where ? ` (${where})` : ""}: ${evidence.current}`);
      lines.push("This was the line in force on that turn, not a line to change.");
    }
    if (evidence.mismatch) lines.push(evidence.mismatch);
    for (const sentence of nudgeSentences(evidence.nudges || [], block)) {
      lines.push(`Stuck nudge: ${sentence}`);
    }
    lines.push("");
  });
  return lines.join("\n").trim();
}

export function recommendationMarkdown(_runId: string, cards: DraftCard[]): string {
  return recommendationPageSummary(cards);
}

