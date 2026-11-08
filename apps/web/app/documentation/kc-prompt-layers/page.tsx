import Link from "next/link";

import { BLOCK_TYPES } from "@/lib/kc-blocks";
import {
  BLOCK_CONFIG_FIELDS,
  BLOCK_CONFIG_TITLES,
  OVERARCHING_FIELDS,
  type ConfigField,
} from "@/lib/kc-tutor-config";

export const metadata = { title: "KC prompt layers · Documentation · AI Tutor" };

function optionLine(field: ConfigField): string {
  if (field.kind === "enum") return field.options.map(([, label]) => label).join(", ");
  if (field.kind === "int") return `${field.min} to ${field.max}`;
  return "On or off";
}

const ASSEMBLER = [
  {
    title: "This turn",
    text: "Who is speaking, which block and substep this is, and the one job of the reply. The opening, the unit close, and the course outro are here only when they change that job. The unit close is the last block. The course outro follows only when every target is known.",
  },
  {
    title: "What to teach",
    text: "Only the active block and its current substep. Later blocks are not included, so the reply cannot jump ahead or close the component early. A withheld answer is said only when a reveal or a passed close allows it.",
  },
  {
    title: "Who you are talking to",
    text: "One short profile: name, age, reading level, modality, and interests, each with its effect. An early reading level means shorter sentences. Interests are an example only when that switch is on.",
  },
  {
    title: "How to teach",
    text: "The overarching rules, plus only the active block type's configuration. A multiple-choice turn uses that type's retry count, wrong-answer depth, and whether a correct retry must explain why. A Socratic turn uses that type's dialogue depth and challenge. Settings for the other eight types are not printed.",
  },
  {
    title: "How to sound",
    text: "Persona, lexicon, metaphors, and sidekick collapse into one voice paragraph. That voice does not change the block, the expected answer, or the score.",
  },
  {
    title: "What just happened",
    text: "Attempts on this block, the last answer, the hint already given, affect, whether help was requested, and the last few messages. This is state. The model is told not to treat it as a new rule.",
  },
  {
    title: "What to return",
    text: "A structured decision: reply, decision, substep_passed, block_complete, generated_mcq when the next block is a dynamic multiple choice, misconception, hint_tier, affect, and confidence. The unit close also returns score_justification, what_was_strong, and what_to_work_on.",
  },
];

export default function KcPromptLayersPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>KC prompt layers</h1>
        <p>
          The tutor prompt is built for the active block only. The model writes the reply. The app sets the blocks, the
          edges, the score, the unit close, and the course outro. The same overarching settings and the nine block-type
          settings are edited on <Link href="/admin/agent-customizations">Agent customizations</Link>. The debug
          Variables panel still groups stored values under seven layer headings. The text sent to the model is the seven
          sections at the end of this page.
        </p>

        <h2>Overarching tutor configurations</h2>
        <p>These apply on every block.</p>
        <ul>
          {OVERARCHING_FIELDS.map((field) => (
            <li key={field.key}>
              <strong>{field.label}.</strong> {field.help} Choices: {optionLine(field)}.
            </li>
          ))}
        </ul>
        <p>
          Voice and persona stay beside those settings: persona, lexicon, metaphors, sidekick, and use interests.
        </p>

        <h2>Per-block-type configurations</h2>
        {BLOCK_TYPES.map((type) => (
          <section key={type}>
            <h3>{BLOCK_CONFIG_TITLES[type]}</h3>
            <ul>
              {BLOCK_CONFIG_FIELDS[type].map((field) => (
                <li key={field.key}>
                  <strong>{field.label}.</strong> {field.help} {optionLine(field)}.
                </li>
              ))}
            </ul>
          </section>
        ))}

        <h2>Layer 1, the active block</h2>
        <p>
          A component stores an ordered list of blocks. Each block is an id, a type, and that type&apos;s fields. Every
          field, whether it is required or optional, and how the tutor uses it, is the{" "}
          <Link href="/documentation/kc-creator#field-catalog">field catalog</Link> on KC Creator. Outline, core truth,
          misconceptions, and the rubric derived from blocks are in that catalog too. The prompt receives the active
          block&apos;s type, its index, its fields, and the current substep. It does not receive the later blocks.
        </p>

        <h2>Layer 7, block state</h2>
        <ul>
          <li>The session step is the active block index, starting at 0.</li>
          <li>The active substep names the part of a multi-part block, and where that part sits, such as Substep 2 of 2.</li>
          <li>Dialogue turns count the exchanges already used on a Socratic or curiosity block.</li>
          <li>Eliminated indexes are the wrong multiple-choice options already picked.</li>
          <li>Block results store each finished block&apos;s outcome and attempts. The outcomes are known, fragile, and engaged.</li>
          <li>Completed blocks, the total, and the percentage include partial credit for the active substep. A finished component is 100 percent.</li>
        </ul>

        <h2>How the prompt is written</h2>
        <p>
          When a block&apos;s last substep passes, the app records that block, advances to the next one, and builds one
          reply that affirms the finished block and opens the next. If the next block is a dynamic multiple choice, the
          decision includes the generated item. Only the last block&apos;s final substep adds the unit close.
        </p>
        {ASSEMBLER.map((section) => (
          <section key={section.title}>
            <h3>{section.title}</h3>
            <p>{section.text}</p>
          </section>
        ))}
      </article>
    </main>
  );
}
