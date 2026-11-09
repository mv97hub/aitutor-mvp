import Link from "next/link";

import { BLOCK_CONFIG_TITLES } from "@/lib/kc-tutor-config";

export const metadata = { title: "KC Tutor · Documentation · AI Tutor" };

const LEARNER: { type: keyof typeof BLOCK_CONFIG_TITLES; text: string }[] = [
  {
    type: "topic_goal",
    text: "The tutor teaches one topic toward its goal, then asks the learner to say it. A thin fragment can be asked again as a full sentence.",
  },
  {
    type: "mcq",
    text: "A static item uses the four stored options. A dynamic item is written for this learner when the block opens. The app grades the picked index. A wrong option can be explained and retried. The right option can ask for a one-sentence why.",
  },
  {
    type: "case_study",
    text: "The learner meets a scenario, chooses at the decision point, and then states what the cases have in common. A transfer question can follow.",
  },
  {
    type: "socratic",
    text: "The tutor probes with a short dialogue, then asks for the target insight.",
  },
  {
    type: "curiosity",
    text: "The learner ventures a hunch about a hook. A bold guess does not, by itself, mark the component fragile unless that block is set to count toward mastery.",
  },
  {
    type: "worked_example",
    text: "The tutor walks a worked solution, hides one or more steps, and then gives a solo problem.",
  },
  {
    type: "spot_the_flaw",
    text: "The learner finds what is wrong in an artifact and, when the setting asks for it, corrects it.",
  },
  {
    type: "teach_back",
    text: "The learner explains the idea to a confused peer and answers the follow-up questions.",
  },
  {
    type: "retrieval_check",
    text: "The learner recalls the point with little or no cue, and can be asked why it is so.",
  },
];

export default function KcTutorDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>KC Tutor</h1>
        <p>
          KC Tutor, at <Link href="/kc-tutor">/kc-tutor</Link>, practices one component at a time by walking that
          component&apos;s blocks in order. The lesson is a chat. Questions and on-screen choices live in the thread.
          Settings is a button in the side column, separate from the lesson chat. It chooses the model from the same
          list as KC Course Creator. gpt-4.1 is the default. The same settings dialog edits the child&apos;s Layer 2
          persona settings: age, grade band, reading level, response length, expression style, explanation style,
          challenge appetite, communication tone, learning support, up to four interest tags, and specific favorites.
          How a block is taught stays on{" "}
          <Link href="/admin/agent-customizations">Agent customizations</Link>. The field catalog is{" "}
          <Link href="/documentation/kc-prompt-layers">KC prompt layers</Link>.
        </p>
        <p>
          The child menu lists Add New Child first. Choosing it opens a dialog for the child&apos;s name and Layer 2
          persona settings. Save creates the child, closes the dialog, and selects that child.
        </p>

        <h2>How it works</h2>
        <p>
          Open asks for a child and a ready course. The course list is only courses KC Course Creator has marked ready.
          The ring paints a known target in the completed color and a fragile target amber. Under the wheel, completed
          includes fragile, and fragile is counted on its own. A segment is known, fragile, or not started. A
          time-boxed course also shows its minutes. Mastery and curiosity do not.
        </p>
        <p>
          Start Course Over clears the selected child&apos;s progress on the open course and starts that course again
          from the first component. TEST KC Selection lists the components of the current course and opens one without
          waiting for the card order.
        </p>
        <p>Up to three cards offer the next work:</p>
        <ul>
          <li>Fastest path is the next target component whose prerequisites are known or fragile.</li>
          <li>Foundation patch is a component that is not a target, when a target is waiting on it.</li>
          <li>Stretch is a later component whose prerequisites are known or fragile.</li>
        </ul>
        <p>
          A card opens that one component. The stage header shows the block progress banner when the session includes
          it: completed blocks out of the total, the percentage, a fill bar, and one pill per block. A finished block
          shows its outcome and attempt count when you hover the pill. The active block shows its type and, when the
          block has more than one part, the active substep, such as Contrast &amp; Rule · Substep 2 of 2. The header
          still names the component. A redirect still reads &quot;Next card: &quot; and the title.
        </p>
        <p>
          The tutor asks about the active block only. A multiple-choice block and a case-study choice use the choice
          widget. Every other block is typed in the same thread. While a choice is unanswered, the composer says
          &quot;Choose an answer above&quot; and does not send. The model writes the reply and a structured decision.
          The app checks that decision. A block can finish known, fragile, or engaged. Known means every counting block
          passed. A required reveal finishes the component as fragile. A curiosity block counts only when that setting
          is on. Course progress marks that finished component completed. In progress is only an open session whose
          last block has not finished. A fragile result can still point at the broken component. Known still raises
          stability, and each encompassed component gains 0.25.
        </p>
        <p>What the learner does on each block:</p>
        <ul>
          {LEARNER.map((item) => (
            <li key={item.type}>
              {BLOCK_CONFIG_TITLES[item.type]}: {item.text}
            </li>
          ))}
        </ul>
        <p>
          When the learner finishes a block, the same reply can affirm that block and open the next one. The unit close
          is reserved for the last block. The course outro follows when every target component is known or fragile.
          Fragile is not rewritten to known.
        </p>
        <p>
          Debug, on the right, opens a panel beside the lesson. Variables keeps the seven headings. A row is shown only
          when this turn reads it, and an empty value stays. The first heading shows the active block only: its index,
          its type, its substep, whether a choice is on screen, and that block&apos;s fields. Prompts lists each request
          and response for this session, oldest first.
        </p>

        <h2>Settings you can change</h2>
        <p>
          This page does not edit the course. The choices on the page are which child, which ready course, Start Course
          Over, which card to open, TEST KC Selection, and Settings. The model list is gpt-4o-mini, gpt-4o,
          gpt-4.1-mini, gpt-4.1, gpt-6.1-sol, and ~deepseek/deepseek-flash-latest. Component blocks are set in KC
          Creator. How the tutor speaks, and how each block type is taught, is the shared profile on Agent
          customizations.
        </p>
        <p>
          Each child stores a Layer 2 persona profile (edited in Settings and visible under <code>Layer 2, Child</code>{" "}
          in Debug Variables):
        </p>
        <ul>
          <li>
            <strong>Display name</strong> (read-only in Settings, set on creation): The learner&apos;s name addressed by
            the tutor.
          </li>
          <li>
            <strong>Age</strong> (5 to 18, default 10): Sets developmental framing and auto-derives the default grade
            band.
          </li>
          <li>
            <strong>Grade band</strong> (<code>early_elementary</code>, <code>upper_elementary</code>,{" "}
            <code>middle_school</code>, <code>high_school</code>): Calibrates example maturity and conceptual framing.
          </li>
          <li>
            <strong>Reading level</strong> (<code>emerging</code>, <code>early_fluent</code>, <code>on_grade</code>,{" "}
            <code>advanced</code>): Adjusts vocabulary and sentence structure, defining new terms right away for
            emerging readers.
          </li>
          <li>
            <strong>Response length</strong> (<code>bite_sized</code>, <code>balanced</code>, <code>detailed</code>):
            Controls whether turns stay at 1-2 short sentences, 2-4 sentences, or fuller explanations.
          </li>
          <li>
            <strong>Expression style</strong> (<code>one_word_or_taps</code>, <code>short_phrases</code>,{" "}
            <code>conversational</code>, <code>analytical</code>): Tells the tutor what the child&apos;s own typing
            looks like so brief replies are validated and modeled back without penalty.
          </li>
          <li>
            <strong>Explanation style</strong> (<code>concrete_examples</code>, <code>step_by_step</code>,{" "}
            <code>visual_spatial</code>, <code>story_and_analogy</code>, <code>pattern_and_rule</code>): Chooses the
            representation the tutor leads with (replacing the legacy <code>modality</code> field).
          </li>
          <li>
            <strong>Challenge appetite</strong> (<code>needs_reassurance</code>, <code>steady</code>,{" "}
            <code>loves_a_challenge</code>): Tunes how mistakes are normalized and how quickly stretch prompts appear.
          </li>
          <li>
            <strong>Communication tone</strong> (<code>calm_and_gentle</code>, <code>warm_and_encouraging</code>,{" "}
            <code>playful_and_curious</code>, <code>direct_and_matter_of_fact</code>): Sets the warmth and energy of
            tutor feedback.
          </li>
          <li>
            <strong>Learning support</strong> (<code>none</code>, <code>adhd_focus_friendly</code>,{" "}
            <code>dyslexia_reading_friendly</code>, <code>ell_language_support</code>,{" "}
            <code>math_or_test_anxiety</code>): Adds targeted UDL pacing, phonics-friendly lines, idiom explanations, or
            low-stakes puzzle framing.
          </li>
          <li>
            <strong>Interest tags</strong> (up to 4 chips from <code>sports_and_games</code>, <code>video_games</code>,{" "}
            <code>animals_and_nature</code>, <code>space_and_science</code>, <code>art_and_design</code>,{" "}
            <code>music_and_dance</code>, <code>building_and_coding</code>, <code>cooking_and_food</code>,{" "}
            <code>cars_and_trains</code>, <code>stories_and_comics</code>) and <strong>Specific favorites</strong> (up
            to 120 characters): Anchors examples and analogies when Use interests is enabled on Agent customizations.
          </li>
        </ul>

        <h2>What to know when using it</h2>
        <ul>
          <li>Add New Child is the first option in the child menu. Save selects the new child.</li>
          <li>Start Course Over clears this child&apos;s progress on the open course and begins that course again.</li>
          <li>TEST KC Selection jumps to any component of the current course.</li>
          <li>A course that is still a draft does not appear here.</li>
          <li>With no card open, the page says a card opens one component.</li>
          <li>When every target component is known or fragile, the page offers the next course. It says every target is known only when none are fragile.</li>
          <li>A finished component hides the composer and shows the score in the header.</li>
          <li>The wording of a question comes from the model. The score does not. A multiple-choice grade is the picked index.</li>
        </ul>
      </article>
    </main>
  );
}
