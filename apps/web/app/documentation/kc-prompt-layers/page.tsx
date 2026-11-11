import Link from "next/link";

import { BLOCK_CLOSE_FLOWS, BlockCloseFlow } from "@/components/docs/BlockCloseFlow";
import { BLOCK_TYPES } from "@/lib/kc-blocks";
import {
  CHALLENGE_APPETITE_OPTIONS,
  COMMUNICATION_TONE_OPTIONS,
  EXPLANATION_STYLE_OPTIONS,
  EXPRESSION_STYLE_OPTIONS,
  GRADE_BAND_OPTIONS,
  HUMOR_AND_WIT_OPTIONS,
  INTEREST_TAG_OPTIONS,
  INTEREST_WEAVING_OPTIONS,
  LEARNING_SUPPORT_OPTIONS,
  METAPHOR_OPTIONS,
  PERSONA_OPTIONS,
  READING_LEVEL_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
  SIDEKICK_OPTIONS,
  VOCABULARY_REGISTER_OPTIONS,
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
    description: "Curated interest categories that give the prompt reliable anchors when Interest weaving is active.",
    effect: "Combined with Specific favorites and woven into examples when Interest weaving is not off.",
  },
  {
    name: "Specific favorites (Interests)",
    options: "Optional short text up to 120 characters (e.g. Minecraft redstone, golden retrievers, soccer goalie)",
    description: "Captures specific kid passions alongside the structured interest tags.",
    effect: "Passed with Interest tags into 'Who you are talking to' so analogies can reference the child's exact favorites when Interest weaving is active.",
  },
];

const LAYER_3_SETTINGS = [
  {
    name: "Persona (persona)",
    options: pairsLine(PERSONA_OPTIONS),
    description: "Tutor archetype framing metaphor (default: coach). Includes socratic_mentor for calm academic guidance without theatrical roleplay.",
    effect: "Sets the framing metaphor in 'How to sound' while Layer 2 communication_tone governs emotional intensity.",
  },
  {
    name: "Vocabulary register (vocabulary_register)",
    options: pairsLine(VOCABULARY_REGISTER_OPTIONS),
    description: "Subject terminology register (default: adaptive_to_child; backward-compatible with legacy lexicon 1..5).",
    effect: "Governs when disciplinary terms are introduced, while Layer 2 exclusively owns sentence length, reading complexity, and paragraph density.",
  },
  {
    name: "Interest weaving (interest_weaving)",
    options: pairsLine(INTEREST_WEAVING_OPTIONS),
    description: "How often to weave the child's Layer 2 interests into hooks and examples (default: subtle_natural; backward-compatible with boolean use_interests).",
    effect: "Subtle natural weaves into a hook or 1 example when natural; frequent thematic frames scenarios around child interests; off uses neutral curriculum examples or the fallback metaphors domain.",
  },
  {
    name: "Fallback analogy domain (metaphors)",
    options: pairsLine(METAPHOR_OPTIONS),
    description: "Fallback analogy domain (default: everyday).",
    effect: "Used when interest_weaving is off, when the child has no Layer 2 interests set, or when personal interests do not fit the concept cleanly.",
  },
  {
    name: "Humor & wit (humor_and_wit)",
    options: pairsLine(HUMOR_AND_WIT_OPTIONS),
    description: "Humor and levity guardrail (default: light_warm).",
    effect: "Allows gentle wit or playful banter on hooks and passes, and automatically suppresses jokes on missed attempts (nudge/scaffold/reveal) or when Layer 2 learning_support is math_or_test_anxiety or communication_tone is calm_and_gentle.",
  },
  {
    name: "Sidekick (sidekick)",
    options: pairsLine(SIDEKICK_OPTIONS),
    description: "Optional sidekick character (default: none).",
    effect: "When enabled, voices at most one short line on hooks or hints and never asks a second competing question.",
  },
];

const OWNERSHIP_MATRIX = [
  {
    dimension: "Sentence Length, Reading Complexity & Accessibility Layout",
    owner: "Layer 2 (reading_level, response_length, learning_support)",
    contract: "Exclusively owned by Layer 2. Never overridden by Layer 3.",
  },
  {
    dimension: "Technical Vocabulary Introduction",
    owner: "Layer 3 (vocabulary_register)",
    contract: "Controls whether disciplinary terms are introduced upfront with a gloss (academic_precision), after plain-language intuition (everyday_conversational), or matched to the child (adaptive_to_child).",
  },
  {
    dimension: "Representation Format of Explanations",
    owner: "Layer 2 (explanation_style)",
    contract: "Whenever Layer 4 triggers an explanation, scaffold, or reveal, it is formatted in the child's Layer 2 explanation_style.",
  },
  {
    dimension: "Analogy Topic Selection",
    owner: "Layer 2 (interest_tags / interests) + Layer 3 (interest_weaving + metaphors)",
    contract: "Layer 2 provides the child's personal interests; Layer 3 interest_weaving decides how often to weave them in; Layer 3 metaphors provides the fallback analogy domain.",
  },
  {
    dimension: "Emotional Warmth vs. Character Framing vs. Praise Rule",
    owner: "Layer 2 (communication_tone, challenge_appetite) + Layer 3 (persona, humor_and_wit, sidekick) + Layer 4 (encouragement_style)",
    contract: "Layer 2 owns emotional warmth and softens first-miss transitions for needs_reassurance; Layer 3 owns the character archetype and light levity on hooks/passes; Layer 4 owns the pedagogical feedback rule on task attempts.",
  },
  {
    dimension: "Teaching Timing, Hint Escalation, Retry Caps & Block Mechanics",
    owner: "Layer 4 (kc_tutor_config.overarching + kc_tutor_config.blocks)",
    contract: "Owned exclusively by Layer 4. Legacy duplicate sliders (instructive, struggle_window, enrichment, anti_spoiler, one_question, growth_praise) are retired from the UI and Debug panel.",
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
          edges, the score, the unit close, and the course outro. Layer 3 (Voice &amp; Persona), the 8 Layer 4
          overarching teaching policies, and the 10 block-type settings are edited on{" "}
          <Link href="/admin/agent-customizations">AI Tutor Configuration</Link>. The debug Variables panel keeps the
          seven headings and shows a row only when this turn reads it. It shows the active block only, along with Layer
          2 child persona settings, Layer 3 voice and effective rules, and Layer 4 overarching + active block configs.
          The text sent to the model is the seven sections at the end of this page.
        </p>

        <h2>Cross-Layer Ownership Matrix</h2>
        <p>
          Every aspect of the tutor&apos;s behavior has a single authoritative layer so settings never collide:
        </p>
        <table>
          <thead>
            <tr>
              <th>Behavioral dimension</th>
              <th>Owning layer &amp; settings</th>
              <th>Precedence contract</th>
            </tr>
          </thead>
          <tbody>
            {OWNERSHIP_MATRIX.map((row) => (
              <tr key={row.dimension}>
                <td>
                  <strong>{row.dimension}</strong>
                </td>
                <td>{row.owner}</td>
                <td>{row.contract}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h2>Layer 3, voice &amp; persona (6 orthogonal settings)</h2>
        <p>
          Edited on <Link href="/admin/agent-customizations">AI Tutor Configuration</Link> under{" "}
          <strong>Voice &amp; Persona (Layer 3)</strong> and inspected live in Debug Variables together with{" "}
          <code>Effective analogy source</code>, <code>Effective vocabulary rule</code>, and{" "}
          <code>Effective humor rule</code>.
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
            {LAYER_3_SETTINGS.map((row) => (
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

        <h2>Layer 4, overarching teaching policies (8 dropdowns)</h2>
        <p>These eight overarching policies apply across every block while the tutor walks a knowledge component:</p>
        <ul>
          {OVERARCHING_FIELDS.map((field) => (
            <li key={field.key}>
              <strong>
                {field.label} (<code>{field.key}</code>).
              </strong>{" "}
              {field.help} Choices: {optionLine(field)}.
            </li>
          ))}
        </ul>

        <h2>Layer 4, per-block-type configurations ({BLOCK_TYPES.length} block types)</h2>
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

        <h2>Block close flows</h2>
        <p>
          Every non-explanation block ends on summary_check. The prompt for that step asks for a short summary and a
          choice to keep talking or close. If the attempt limit was reached, the prompt says the block is not complete
          and forbids congratulations. A later reply that shows the goal can still complete the block. The closing
          reply does not open the next block.
        </p>
        {BLOCK_CLOSE_FLOWS.map((flow) => (
          <BlockCloseFlow key={flow.title} {...flow} />
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
          Layers 4, 5, and 6 show all 8 overarching teaching policies (including any effective <code>time_boxed</code>{" "}
          course override), the active block config, and the 9-block config summary. Layer 7 is the block session.
        </p>
        <ul>
          <li>The active block&apos;s substep and turn kind are listed with that block. Attempts and max retries track progress on this block.</li>
          <li>Eliminated choices are the wrong multiple-choice options already picked.</li>
          <li>Finished blocks list each completed block, its outcome, and how many tries it took.</li>
          <li>Close component is yes when this turn may finish the component. Close course is yes when this turn may finish the course.</li>
        </ul>

        <h2>How the prompt is written</h2>
        <p>
          summary_check is the last substep. When the learner closes it, the app records the block and advances. The
          closing reply affirms or, if the block is still incomplete, closes without congratulations. It does not open
          the next block. The next block&apos;s opening is a separate speech. If that next block is a dynamic multiple
          choice, the opening includes the generated item. Only the last block&apos;s summary check adds the unit close.
        </p>
        <section>
          <h3>This turn</h3>
          <p>
            Who is speaking, which block, substep, and turn kind this is, and the one job of the reply. Includes the
            opening orientation, instructional stance or scaffolding escalation for the turn, humor suppression
            guardrails on misses, encouragement style on feedback turns, the unit close, and the course outro when
            every target is known or fragile. A fragile result stays fragile.
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
            tags plus specific favorites. Each setting is stated as a direct behavioral instruction.
          </p>
        </section>
        <section>
          <h3>How to teach</h3>
          <p>
            The 8 overarching pedagogical rules (including representation harmony with Layer 2{" "}
            <code>explanation_style</code>, <code>instructional_stance</code>, <code>scaffolding_escalation</code>,{" "}
            <code>stay_on_course</code>, <code>misconception_policy</code>, <code>prerequisite_support_policy</code>,
            and <code>encouragement_style</code>), plus only the active block type&apos;s configuration. Settings for
            the other eight types are not printed.
          </p>
        </section>
        <section>
          <h3>How to sound</h3>
          <p>
            Persona, vocabulary register (with explicit Layer 2 reading/length ownership), interest weaving, fallback
            metaphors domain, humor &amp; wit (with automatic suppression on misses and anxiety/calm profiles), and
            sidekick rules. That voice does not change the block, the expected answer, or the score.
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
