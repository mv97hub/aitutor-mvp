/** Turn harness findings plus stored prompts into review cards.

The cards quote sentences that are already in the stored tutor prompt and name
the prompt-builder section and function that wrote them. Nothing here edits
kc_prompt.py or applies a setting.
*/

import fs from "node:fs";
import path from "node:path";

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
  examples?: { chat_id?: string; turn?: number; block?: string; child?: string }[];
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
  block_label?: string;
  tutor_prompt?: string;
  sections?: Record<string, string>;
};

export type DraftMaterials = {
  run_id?: string;
  findings?: DraftFinding[] | { findings?: DraftFinding[] };
  examples?: ExampleTurn[];
  builder?: BuilderExcerpt[];
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

const TAG_PREFER: Record<string, RegExp> = {
  stuck: /more deeply|why it matters|do not ask any question/,
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

function sentences(text: string): string[] {
  return fold(text)
    .split(/(?<=[.!?])\s+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 20);
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

function blockFromPrompt(prompt: string): string {
  const match = prompt.match(/Block \d+ of \d+: ([^.\n]+)/);
  return match?.[1]?.trim() || "";
}

function findingBlock(finding: DraftFinding, prompts: string[]): string {
  const named = (finding.block_label || "").trim();
  const fromExample = (finding.examples || []).find((item) => item.block && item.block !== "an unknown block")?.block;
  if (named && named !== "an unknown block") return named;
  if (fromExample) return fromExample;
  for (const prompt of prompts) {
    const label = prompt ? blockFromPrompt(prompt) : "";
    if (label) return label;
  }
  return named || "an unknown block";
}

function promptsFor(finding: DraftFinding, examples: ExampleTurn[]): string[] {
  const wanted = new Set((finding.examples || []).map((item) => Number(item.turn)).filter((turn) => !Number.isNaN(turn)));
  const chats = new Set((finding.examples || []).map((item) => item.chat_id).filter(Boolean));
  const prompts = examples
    .filter((example) => {
      if (!example.tutor_prompt) return false;
      if (chats.size === 0) return true;
      if (example.chat_id && !chats.has(example.chat_id)) return false;
      if (wanted.size === 0) return true;
      const turn = Number(example.turn);
      return wanted.has(turn) || wanted.has(turn - 1);
    })
    .map((example) => example.tutor_prompt || "");
  if (prompts.length > 0) return prompts;
  return examples.map((example) => example.tutor_prompt || "").filter(Boolean);
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
  if (tag === "stuck" && text.includes("more deeply")) score += 400;
  return score;
}

function pickQuote(
  tag: string,
  excerpts: BuilderExcerpt[],
  prompts: string[],
): { excerpt: BuilderExcerpt; current: string } | null {
  const symbols = TAG_SYMBOLS[tag] || excerpts.map((item) => item.symbol);
  const pool = excerpts.filter((item) => symbols.includes(item.symbol));
  let best: { excerpt: BuilderExcerpt; current: string; score: number } | null = null;
  for (const excerpt of pool) {
    for (const literal of literalsOf(excerpt)) {
      for (const prompt of prompts) {
        const current = quoteFromPrompt(prompt, literal);
        if (!current) continue;
        const score = scoreLiteral(tag, literal);
        if (!best || score > best.score) best = { excerpt, current, score };
      }
    }
  }
  return best ? { excerpt: best.excerpt, current: best.current } : null;
}

function propose(tag: string, current: string): { replacement: string; shorter: string; kind: DraftCard["kind"] } {
  const text = current.toLowerCase();
  if (tag === "repeated_itself" || /nudge|those hints|missed answers/.test(text)) {
    return {
      replacement: "On a goal-start turn, do not climb the hint ladder and do not repeat the last explanation. Answer once.",
      shorter: "Remove this sentence.",
      kind: "remove",
    };
  }
  if (tag === "one_question") {
    if (text.includes("side remark") || text.includes("question they typed")) {
      return {
        replacement: "Answer the side remark in one sentence, then one line back to the lesson. Ask no question. One question waits until the learner moves on.",
        shorter: "Answer in one sentence. Ask no question.",
        kind: "reword",
      };
    }
    return {
      replacement: "Explain this topic in two or three sentences, then stop. Ask no question. One question waits until the learner moves on.",
      shorter: "Ask no question.",
      kind: "reword",
    };
  }
  if (tag === "stay_on_course") {
    return {
      replacement: "Stay on course: answer in one sentence, then one line back to this block. Do not ask a question.",
      shorter: "Stay on course: one sentence, then back to this block.",
      kind: "reword",
    };
  }
  if (tag === "ignored_question") {
    return {
      replacement: "Answer the question they typed in one sentence, then one line back to the lesson.",
      shorter: "Answer their question in one sentence.",
      kind: "reword",
    };
  }
  if (/side remark/.test(text)) {
    return {
      replacement: "Answer the side remark in one sentence, then one line back to the lesson. Do not start a new explanation. Do not ask a question.",
      shorter: "One sentence on the side remark, then stop.",
      kind: "reword",
    };
  }
  return {
    replacement: "Explain this topic in two or three sentences, then stop. The learner leaves this step with Got it - move on. Ask no question.",
    shorter: "Explain this topic in two sentences, then stop.",
    kind: "reword",
  };
}

function sectionText(example: ExampleTurn, name: string): string {
  return example.sections?.[name] || "";
}

function duplicateSentence(examples: ExampleTurn[]): { prompt: string; sentence: string } | null {
  for (const example of examples) {
    const turn = sectionText(example, "This turn") || example.tutor_prompt || "";
    const teach = sectionText(example, "How to teach");
    if (!turn || !teach) continue;
    const turnFold = fold(turn).toLowerCase();
    for (const sentence of sentences(teach)) {
      if (sentence.length < 40) continue;
      if (turnFold.includes(fold(sentence).toLowerCase())) {
        return { prompt: example.tutor_prompt || teach, sentence: quoteFromPrompt(example.tutor_prompt || teach, sentence) || sentence };
      }
    }
  }
  return null;
}

function cardFrom(input: {
  block: string;
  finding: DraftFinding;
  excerpt: BuilderExcerpt;
  current: string;
  replacement: string;
  shorter: string;
  kind: DraftCard["kind"];
  title: string;
}): DraftCard {
  const place = `${input.excerpt.section} — ${input.excerpt.function}${
    input.excerpt.symbol !== input.excerpt.function ? ` (${input.excerpt.symbol})` : ""
  }`;
  const findingTitle = input.finding.title || input.finding.tag || "Finding";
  const nudges = input.finding.tag === "stuck" ? input.finding.nudges || [] : [];
  const nudgeLines = nudgeSentences(nudges, input.block);
  const summary = [
    findingTitle.endsWith(".") ? findingTitle : `${findingTitle}.`,
    `${input.excerpt.section} is written by ${input.excerpt.function} in kc_prompt.py.`,
    input.excerpt.symbol !== input.excerpt.function ? `The sentence is ${input.excerpt.symbol}.` : "",
    "The current sentences are quoted from the stored tutor prompt. The replacement is shorter. Nothing here changes the live tutor.",
    ...nudgeLines,
  ]
    .filter(Boolean)
    .join(" ");
  return {
    title: input.title.slice(0, 180),
    cause_class: input.finding.cause_class || "prompt",
    place,
    kind: input.kind,
    prompt_direction: "shorter",
    risk: "A shorter line can drop a reminder the tutor was using. Read the quote before editing the prompt builder.",
    confidence: "high",
    block_type: input.block,
    proposed: { text: input.replacement, shorter: input.shorter },
    evidence: {
      summary,
      block_type: input.block,
      section: input.excerpt.section,
      function: input.excerpt.function,
      symbol: input.excerpt.symbol,
      current: input.current,
      replacement: input.replacement,
      shorter: input.shorter,
      nudges: nudgeLines.length ? nudges : undefined,
    },
  };
}

export function draftPromptCards(materials: DraftMaterials): DraftCard[] {
  const findings = findingsOf(materials);
  const examples = materials.examples || [];
  const builder = materials.builder || [];
  const cards: DraftCard[] = [];
  for (const finding of findings) {
    const prompts = promptsFor(finding, examples);
    const picked = pickQuote(String(finding.tag || ""), builder, prompts);
    if (!picked) continue;
    const block = findingBlock(finding, prompts);
    const next = propose(String(finding.tag || ""), picked.current);
    const verb = next.kind === "remove" ? "Remove a line in" : "Shorten";
    const label = String(finding.tag || "finding").replaceAll("_", " ");
    cards.push(
      cardFrom({
        block,
        finding,
        excerpt: picked.excerpt,
        current: picked.current,
        replacement: next.replacement,
        shorter: next.shorter,
        kind: next.kind,
        title: `${block}: ${verb} ${picked.excerpt.section} for ${label} (${picked.excerpt.function})`,
      }),
    );
  }
  const duplicate = duplicateSentence(examples);
  const teach = builder.find((item) => item.function === "_how_to_teach" && item.section === "How to teach");
  if (duplicate && teach && duplicate.sentence) {
    const block = examples.map((item) => item.block_label).find((label) => label && label !== "an unknown block") || findingBlock({}, [duplicate.prompt]);
    cards.push(
      cardFrom({
        block,
        finding: {
          title: "The same sentence is in This turn and How to teach",
          cause_class: "prompt",
          tag: "duplicate",
        },
        excerpt: teach,
        current: duplicate.sentence,
        replacement: "Remove this sentence. This turn already says it.",
        shorter: "Remove this sentence.",
        kind: "remove",
        title: `${block}: Remove the repeated line in How to teach (_how_to_teach)`,
      }),
    );
  }
  return cards;
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
  const excerpts = (materials.builder || [])
    .filter((item) => cards.some((card) => card.evidence.symbol === item.symbol || card.evidence.function === item.function))
    .map((item) => `### ${item.section} · ${item.function} · ${item.symbol}\n${item.source}`)
    .join("\n\n");
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
    "Rewrite the replacement for each card. A person reviews every card. Do not edit the live prompt builder.",
    "current_quote is an exact sentence from the stored tutor prompt. Repeat it unchanged.",
    "replacement replaces those sentences. shorter is a shorter sentence, or Remove this sentence, when cutting the line fixes the finding.",
    "Prefer the shorter or removed line over adding a new paragraph.",
    `Cards:\n${quoted}`,
    `Prompt builder source:\n${excerpts}`,
    `Stored prompts for the example turns:\n${stored}`,
  ].join("\n\n");
}

export function recommendationMarkdown(runId: string, cards: DraftCard[]): string {
  const lines = [
    "# Harness prompt recommendations",
    "",
    `Run: \`${runId || "unknown"}\``,
    "",
    "These cards are prompt-tuning instructions for a later Cursor run. Drafting does not change the live tutor and does not edit `apps/api/app/kc_prompt.py`. Apply a card only when a person asks.",
    "",
  ];
  cards.forEach((card, index) => {
    lines.push(`## ${index + 1}. ${card.title}`);
    lines.push("");
    lines.push(`- Block type: ${card.evidence.block_type || "an unknown block"}`);
    lines.push(`- Section: ${card.evidence.section || ""}`);
    lines.push(`- Function: \`${card.evidence.function || ""}\`${card.evidence.symbol && card.evidence.symbol !== card.evidence.function ? ` (\`${card.evidence.symbol}\`)` : ""}`);
    lines.push(`- Kind: ${card.kind}, prompt gets ${card.prompt_direction}`);
    lines.push(`- Place: ${card.place || ""}`);
    lines.push("");
    lines.push(card.evidence.summary || "");
    lines.push("");
    if (card.evidence.nudges && card.evidence.nudges.length > 0) {
      lines.push("### Nudges");
      lines.push("");
      for (const sentence of nudgeSentences(card.evidence.nudges, card.evidence.block_type || "")) {
        lines.push(`- ${sentence}`);
      }
      lines.push("");
    }
    lines.push("### Current sentences");
    lines.push("");
    lines.push(`> ${card.evidence.current || ""}`);
    lines.push("");
    lines.push("### Replacement");
    lines.push("");
    lines.push(card.evidence.replacement || card.proposed.text || "");
    lines.push("");
    lines.push("### Shorter or removed");
    lines.push("");
    lines.push(card.evidence.shorter || card.proposed.shorter || "");
    lines.push("");
  });
  return lines.join("\n");
}

export function writeRecommendationDoc(markdown: string): boolean {
  try {
    const dir = path.dirname(RECOMMENDATION_DOC);
    if (!fs.existsSync(dir)) return false;
    fs.writeFileSync(RECOMMENDATION_DOC, markdown);
    return true;
  } catch {
    return false;
  }
}
