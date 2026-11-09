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
          list as KC Course Creator. gpt-4.1 is the default. The same settings surface edits the child fields the
          prompt already includes: age, reading level, modality, and interests. How a block is taught stays on{" "}
          <Link href="/admin/agent-customizations">Agent customizations</Link>. The field catalog is{" "}
          <Link href="/documentation/kc-prompt-layers">KC prompt layers</Link>.
        </p>
        <p>
          The child menu lists Add New Child first. Choosing it opens a dialog for a name, an age, a reading level, a
          modality, and interests. Save creates the child, closes the dialog, and selects that child.
        </p>

        <h2>How it works</h2>
        <p>
          Open asks for a child and a ready course. The course list is only courses KC Course Creator has marked ready.
          The ring counts target components that are known, out of all target components. A segment is known, fragile,
          or not started. A time-boxed course also shows its minutes. Mastery and curiosity do not.
        </p>
        <p>
          Start Course Over clears the selected child&apos;s progress on the open course and starts that course again
          from the first component. TEST KC Selection lists the components of the current course and opens one without
          waiting for the card order.
        </p>
        <p>Up to three cards offer the next work:</p>
        <ul>
          <li>Fastest path is the next target component whose prerequisites are known.</li>
          <li>Foundation patch is a component that is not a target, when a target is waiting on it.</li>
          <li>Stretch is a later component whose prerequisites are known.</li>
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
          is reserved for the last block. The course outro follows only when every target component is known.
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
          gpt-4.1-mini, gpt-4.1, gpt-6.1-sol, and ~deepseek/deepseek-flash-latest. Age, reading level, modality, and
          interests save on the child. Component blocks are set in KC Creator. How the tutor speaks, and how each block
          type is taught, is the shared profile on Agent customizations.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>Add New Child is the first option in the child menu. Save selects the new child.</li>
          <li>Start Course Over clears this child&apos;s progress on the open course and begins that course again.</li>
          <li>TEST KC Selection jumps to any component of the current course.</li>
          <li>A course that is still a draft does not appear here.</li>
          <li>With no card open, the page says a card opens one component.</li>
          <li>When every target component is known, the page says so and offers no cards.</li>
          <li>A finished component hides the composer and shows the score in the header.</li>
          <li>The wording of a question comes from the model. The score does not. A multiple-choice grade is the picked index.</li>
        </ul>
      </article>
    </main>
  );
}
