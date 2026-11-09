import Link from "next/link";

import { BLOCK_TYPES } from "@/lib/kc-blocks";
import {
  CHALLENGE_APPETITE_OPTIONS,
  COMMUNICATION_TONE_OPTIONS,
  EXPLANATION_STYLE_OPTIONS,
  EXPRESSION_STYLE_OPTIONS,
  GRADE_BAND_OPTIONS,
  INTEREST_TAG_OPTIONS,
  LEARNING_SUPPORT_OPTIONS,
  READING_LEVEL_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
} from "@/lib/kc-layer-fields";
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

function pairsLine(options: readonly (readonly [string, string])[]): string {
  return options.map(([id, label]) => `${id} (${label})`).join("; ");
}

const LAYER_2_SETTINGS = [
  {
    name: "Display name",
    options: "Read-only in KC Tutor settings (set when the child is created)",
    description: "The learner's name, used by the tutor to address the child naturally.",
    effect: "Starts 'Who you are talking to' with 'Speak to <Display name>.'",
  },
  {
    name: "Age",
    options: "5 to 18 (default 10)",
    description: "Sets developmental framing, example maturity, and the default grade band.",
    effect: "Calibrates sentence length and example maturity for the learner's age.",
  },
  {
    name: "Grade band",
    options: pairsLine(GRADE_BAND_OPTIONS),
    description: "Developmental stage, auto-derived from age by default and overridable via dropdown.",
    effect: "Frames examples and scaffolding for early elementary, upper elementary, middle school, or high school.",
  },
  {
    name: "Reading level",
    options: pairsLine(READING_LEVEL_OPTIONS),
    description: "Reading and vocabulary level (replaces bare free-text reading level; legacy values map cleanly).",
    effect: "Emerging uses very short sentences and defines new terms right away; early fluent uses one clause at a time; on grade uses natural grade-level flow; advanced uses precise academic terms.",
  },
  {
    name: "Response length",
    options: pairsLine(RESPONSE_LENGTH_OPTIONS),
    description: "Controls how much text the tutor puts in a single turn to manage cognitive load.",
    effect: "Bite-sized limits turns to 1-2 short sentences; balanced uses 2-4 sentences; detailed gives fuller explanations with explicit connections.",
  },
  {
    name: "Expression style",
    options: pairsLine(EXPRESSION_STYLE_OPTIONS),
    description: "Describes what the child's own typing or voice looks like so brief answers are not penalized.",
    effect: "One word or taps validates 1-3 word replies and models a clean sentence back; short phrases keeps follow-ups crisp; conversational invites dialogue; analytical welcomes fuller reasoning and precise pushback.",
  },
  {
    name: "Explanation style",
    options: pairsLine(EXPLANATION_STYLE_OPTIONS),
    description: "Preferred cognitive representation when introducing or hinting at a concept (upgrades legacy modality).",
    effect: "Leads with everyday concrete objects, sequential step-by-step breakdowns, vivid visual-spatial mental pictures, narrative stories and analogies, or underlying patterns and rules.",
  },
  {
    name: "Challenge appetite",
    options: pairsLine(CHALLENGE_APPETITE_OPTIONS),
    description: "How the learner responds to difficulty and uncertainty.",
    effect: "Needs reassurance normalizes mistakes early and lowers stakes; steady keeps normal scaffolding; loves a challenge uses brisk pacing, stretch prompts, and minimal hints.",
  },
  {
    name: "Communication tone",
    options: pairsLine(COMMUNICATION_TONE_OPTIONS),
    description: "The affective warmth and conversational energy that keeps the learner comfortable.",
    effect: "Adjusts replies to be calm and gentle, warm and encouraging, playful and curious, or direct and matter-of-fact.",
  },
  {
    name: "Learning support",
    options: pairsLine(LEARNING_SUPPORT_OPTIONS),
    description: "Optional UDL pacing or language accommodations.",
    effect: "Applies ADHD focus-friendly crisp turns, dyslexia phonics-friendly short lines, ELL idiom-free synonyms, or low-stakes puzzle framing for math/test anxiety.",
  },
  {
    name: "Interest tags",
    options: `0 to 4 multi-select chips: ${INTEREST_TAG_OPTIONS.map(([id, label]) => `${id} (${label})`).join(", ")}`,
    description: "Curated interest categories that give the prompt reliable anchors when Use interests is enabled.",
    effect: "Combined with Specific favorites and woven into examples when Use interests is on, or held back when off.",
  },
  {
    name: "Specific favorites (Interests)",
    options: "Optional short text up to 120 characters (e.g. Minecraft redstone, golden retrievers, soccer goalie)",
    description: "Captures specific kid passions alongside the structured interest tags.",
    effect: "Passed with Interest tags into 'Who you are talking to' so analogies can reference the child's exact favorites when Use interests is on.",
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
          Variables panel keeps the seven headings and shows a row only when this turn reads it. It shows the active
          block only. The text sent to the model is the seven sections at the end of this page.
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

        <h2>Layer 2, child persona settings</h2>
        <p>
          Layer 2 stores who the child is, how they read and express ideas, which explanation representation helps most,
          what challenge and tone keep them engaged, any learning support accommodations, and their curated interest
          tags plus specific favorites. Edit these per child in the <Link href="/kc-tutor">KC Tutor</Link> Settings
          dialog, preview them in the <Link href="/kc-prompt-tester">KC Prompt Tester</Link>, and inspect them live
          under <code>Layer 2, Child</code> in the Debug Variables panel.
        </p>
        <table>
          <thead>
            <tr>
              <th>Setting</th>
              <th>Field options</th>
              <th>Description</th>
              <th>How it changes the prompt &amp; child experience</th>
            </tr>
          </thead>
          <tbody>
            {LAYER_2_SETTINGS.map((row) => (
              <tr key={row.name}>
                <td>
                  <strong>{row.name}</strong>
                </td>
                <td>{row.options}</td>
                <td>{row.description}</td>
                <td>{row.effect}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          Derived session fields under <code>Layer 2, Child</code> in Debug Variables also show{" "}
          <strong>Hint tier already given</strong>, <strong>Component status</strong>, <strong>Last answer</strong>,{" "}
          <strong>Last misconception</strong>, <strong>Minutes used</strong>, and <strong>Support band</strong>.
        </p>

        <h2>Layer 7, block state</h2>
        <p>
          Layers 4, 5, and 6 show orient framing, stay on course, misconception policy, encouragement style, and close
          summary depth, plus only the active block type&apos;s settings. Layer 7 is the block session.
        </p>
        <ul>
          <li>The active block&apos;s substep is listed with that block. Attempts count the tries on this block.</li>
          <li>Eliminated choices are the wrong multiple-choice options already picked.</li>
          <li>Finished blocks list each completed block, its outcome, and how many tries it took.</li>
          <li>Close component is yes when this turn may finish the component. Close course is yes when this turn may finish the course.</li>
        </ul>

        <h2>How the prompt is written</h2>
        <p>
          When a block&apos;s last substep passes, the app records that block, advances to the next one, and builds one
          reply that affirms the finished block and opens the next. If the next block is a dynamic multiple choice, the
          decision includes the generated item. Only the last block&apos;s final substep adds the unit close.
        </p>
        <section>
          <h3>This turn</h3>
          <p>
            Who is speaking, which block and substep this is, and the one job of the reply. The opening, the unit close,
            and the course outro are here only when they change that job. The unit close is the last block. The course
            outro follows only when every target is known.
          </p>
        </section>
        <section>
          <h3>What to teach</h3>
          <p>
            Only the active block and its current substep. Later blocks are not included, so the reply cannot jump ahead
            or close the component early. A withheld answer is said only when a reveal or a passed close allows it.
          </p>
        </section>
        <section>
          <h3>Who you are talking to</h3>
          <p>
            One learner profile built from Layer 2: display name, age, grade band, reading level, response length,
            expression style, explanation style, challenge appetite, communication tone, learning support, and interest
            tags plus specific favorites. Each setting is stated as a direct behavioral instruction. Interests are used
            as an example only when Use interests is on.
          </p>
        </section>
        <section>
          <h3>How to teach</h3>
          <p>
            The overarching rules, plus only the active block type&apos;s configuration. A multiple-choice turn uses that
            type&apos;s retry count, wrong-answer depth, and whether a correct retry must explain why. A Socratic turn
            uses that type&apos;s dialogue depth and challenge. Settings for the other eight types are not printed.
          </p>
        </section>
        <section>
          <h3>How to sound</h3>
          <p>
            Persona, lexicon, metaphors, and sidekick collapse into one voice paragraph. That voice does not change the
            block, the expected answer, or the score.
          </p>
        </section>
        <section>
          <h3>What just happened</h3>
          <p>
            Attempts on this block, the last answer, the hint already given, affect, whether help was requested, and the
            last few messages. This is state. The model is told not to treat it as a new rule.
          </p>
        </section>
        <section>
          <h3>What to return</h3>
          <p>
            A structured decision: reply, decision, substep_passed, block_complete, generated_mcq when the next block is
            a dynamic multiple choice, misconception, hint_tier, affect, and confidence. The unit close also returns
            score_justification, what_was_strong, and what_to_work_on.
          </p>
        </section>
      </article>
    </main>
  );
}
