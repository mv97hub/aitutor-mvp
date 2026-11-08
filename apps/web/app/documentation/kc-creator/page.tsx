import Link from "next/link";

import { BLOCK_CONFIG_TITLES } from "@/lib/kc-tutor-config";

export const metadata = { title: "KC Creator · Documentation · AI Tutor" };

const BLOCK_FIELDS: { type: keyof typeof BLOCK_CONFIG_TITLES; fields: string }[] = [
  {
    type: "topic_goal",
    fields: "Topic, goal, reveal after recall, contrast note, common mix-up, and why it matters.",
  },
  {
    type: "mcq",
    fields:
      "Static or dynamic. Static stores the question, four options, the correct option, why it is correct, and why each other option is wrong. Dynamic stores a generation prompt and guidance for those explanations.",
  },
  {
    type: "case_study",
    fields:
      "Scenario, decision point, decision options, the best option, why it is best, why the others fall short, a follow-up question, and what transfers.",
  },
  {
    type: "socratic",
    fields: "Opening question, probe if shallow, probe if close, target insight, and max exchanges.",
  },
  {
    type: "curiosity",
    fields: "Hook question, expected hunch, reveal, why it is surprising, and the bridge to the goal.",
  },
  {
    type: "worked_example",
    fields: "Problem, steps as an action and a reason, the faded step, solo problem, and solo check.",
  },
  {
    type: "spot_the_flaw",
    fields: "Artifact, flaw location, why it is wrong, the fix, and a transfer question.",
  },
  {
    type: "teach_back",
    fields: "Prompt, lines the explanation must include, a rubric note, and a follow-up if the explanation is thin.",
  },
  {
    type: "retrieval_check",
    fields: "Prompt, acceptable points, and a partial-credit note.",
  },
];

export default function KcCreatorDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>KC Creator</h1>
        <p>
          KC Creator, at <Link href="/kc-creator">/kc-creator</Link>, edits one knowledge component as an ordered list of
          blocks. KC Course Creator, at <Link href="/kc-studio">/kc-studio</Link>, owns the course list and the
          structure. This page is the editor: choose a course and a component, change the blocks by hand, or draft them
          in the chat.
        </p>

        <h2>How it works</h2>
        <p>
          The left pane is a course dropdown. The list under it shows the components of the selected course: targets in
          course order, then patches. A component that already has blocks shows a short block summary, such as 1
          Curiosity · 2 Topics. Choosing another course opens that course&apos;s first component. A patch can be opened
          here. It is still not a target.
        </p>
        <p>
          The middle pane is the manual editor. Description is a short summary. When the component has a recommended
          sequence, that sentence stays in the description and the editor also lists it above the canvas. Outline and
          the topic rows stay beside the blocks. Save this component writes the fields, including the ordered blocks,
          and clears the course ready flag. Mark complete sits next to Save. It can be used only when the saved
          component has no gaps. Mark complete records that flag. Save and Push clear it, and they clear course ready.
        </p>
        <p>
          The block canvas is the ordered lesson. Each card is one block: its place in the sequence, its type, and the
          fields for that type. Up and Down move a card. Duplicate copies it under the original. Collapse hides the
          fields. Delete removes the card. Add block, above the list and between cards, inserts any of the nine types.
          Changing a card&apos;s type starts that type&apos;s empty fields and keeps the card&apos;s place.
        </p>
        <p>
          AI Block Scope sits at the top right, beside Fast Create All. It is a multi-select of the nine block types,
          labeled with how many are on, or All 9 blocks when every type is on. Select All checks every type. Topic +
          MCQ Only leaves Topic / Goal and Multiple choice. Clearing the last checked type leaves Topic / Goal. The
          choice is saved on the course and is sent with the component chat, so the draft stays inside that scope. The
          canvas can still hold any type you add by hand.
        </p>
        <p>
          The right pane is a conversation about this component only. It is stored for the component. It is not a
          kid-tutor message. A model menu sits in the composer. gpt-4.1 is the default. The chosen model is sent with
          each message. It does not change scoring or edges. If the key for the chosen model is missing, the chat shows
          that missing-key error. The reply recommends an ordered blocks sequence inside the AI Block Scope. The middle
          pane keeps the saved component until Push. Push writes the whole draft, including the blocks. Other components
          stay.
        </p>
        <p>
          Fast Create All fills every empty component of the selected course, pushes the draft, and marks the component
          complete. Empty means the component has no blocks. A component that has not been given a block list yet is
          empty when it also has no older type. The button walks those components in course order and uses the same AI
          Block Scope. The count beside it is how many of them are done. A push that still has a gap stops on that
          component and shows the gap text.
        </p>

        <h2>Settings you can change</h2>
        <p>Every component has:</p>
        <ul>
          <li>Description. A short summary. Save and Push keep it, including the recommended-blocks sentence.</li>
          <li>Title.</li>
          <li>Outline. The opening of the component can elaborate it.</li>
          <li>Topics. Each row is a topic and its goal. Add and remove rows.</li>
          <li>Blocks, in the order the tutor will walk them.</li>
          <li>Core truth.</li>
          <li>Rubric checks, one to three. More than three is rejected.</li>
          <li>Misconceptions. A filled row needs both a wrong move and a component code.</li>
          <li>Prerequisite of this component, chosen from the other component codes.</li>
          <li>Encompasses, stability bump, chosen from the other component codes.</li>
        </ul>
        <p>Each block type stores its own fields:</p>
        <ul>
          {BLOCK_FIELDS.map((item) => (
            <li key={item.type}>
              {BLOCK_CONFIG_TITLES[item.type]}: {item.fields}
            </li>
          ))}
        </ul>

        <h2>What to know when using it</h2>
        <ul>
          <li>Choose a course, then a component. With neither selected, the page says to choose a component.</li>
          <li>Fast Create All fills components that have no blocks. It skips a component that already has one.</li>
          <li>AI Block Scope limits what the chat and Fast Create All recommend. It does not delete blocks already on the canvas.</li>
          <li>The chat draft is not the saved component until Push.</li>
          <li>Push and Save both clear Mark complete and mark the course not ready.</li>
          <li>Mark complete stays unavailable while any gap string would show on the structure row.</li>
          <li>
            How the tutor says a block is set on <Link href="/admin/agent-customizations">Agent customizations</Link>,
            not on this page. The catalog is <Link href="/documentation/kc-prompt-layers">KC prompt layers</Link>.
          </li>
        </ul>
      </article>
    </main>
  );
}
