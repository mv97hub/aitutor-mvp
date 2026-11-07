import Link from "next/link";

export const metadata = { title: "KC Creator · Documentation · AI Tutor" };

export default function KcCreatorDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>KC Creator</h1>
        <p>
          KC Creator, at <Link href="/kc-creator">/kc-creator</Link>, edits one knowledge component.
          KC Course Creator, at <Link href="/kc-studio">/kc-studio</Link>, owns the course list and the structure.
          This page is the editor: choose a course and a component, change it by hand, or draft it in the chat.
        </p>

        <h2>How it works</h2>
        <p>
          The left pane is a course dropdown. The list under it shows only the components of the selected course:
          targets in course order, then patches. Choosing another course opens that course’s first component.
          The selected row is the component on screen. A patch can be opened here. It is still not a target.
        </p>
        <p>
          The middle pane is the manual editor. Description sits with the other fields and can be edited:
          the outline, topics, and goals saved from the course draft. Save this component writes the fields, including that description, and clears the course ready flag.
          Each enterable field has a short mouse-over tooltip that says what the tutor uses it for.
          Mark complete sits next to Save. It can be used only when the saved component has no gaps: a type, a core truth,
          at least one rubric check, and prerequisite and encompasses codes that exist. There is no extra gap rule.
          Mark complete records that flag. Save and Push clear it, and they clear course ready.
          On KC Course Creator the structure row then says Marked complete, or Complete when the gaps are empty and the flag is off,
          or the gap strings when something is still missing.
        </p>
        <p>
          The right pane is a conversation about this component only. It is stored for the component. It is not a kid-tutor message.
          A model menu sits in the composer: gpt-4o-mini, gpt-4o, gpt-4.1-mini, gpt-4.1, gpt-6.1-sol, and ~deepseek/deepseek-flash-latest. gpt-4.1 is the default.
          The chosen model is sent with each message. It does not change scoring, edges, or which types exist.
          OpenAI models use OPENAI_API_KEY. ~deepseek/deepseek-flash-latest uses OPENROUTER_API_KEY.
          If the key for the chosen model is missing, the chat shows that missing-key error. The other key is not required for that call.
          The first view starts with the description, the brief for this component, and then the saved text: title, type,
          core truth, rubric lines, each wrong move and its component code, prerequisite codes, encompasses codes,
          and the type fields for that type.
          The chat treats that description as the brief. It is an expert curriculum maker for this component and uses the course kind.
          It goes into the topic, then recommends every field that can be entered: the description, the title, the type,
          the fields for that type, the core truth, the rubric checks, the misconceptions, the prerequisites, and the encompasses links.
          A later message revises that draft.
          Enter and the up arrow both send the message. While the reply is being written, the composer says Writing… and cannot be sent again.
          A missing key for the chosen model still shows that model&apos;s missing-key error.
          The middle pane keeps the saved component until Push. Push writes the whole draft, including the description. Other components stay.
          Edges are rewritten only for this component. After Push, the middle pane shows the written fields and the thread says the draft was saved.
        </p>
        <p>
          A first message starts from the description and the course kind, goes into the topic, and then drafts the fields.
          A later message revises that draft. Nothing from the chat is stored on the component until Push.
        </p>
        <p>
          Fast Create All, at the top right, fills every empty component of the selected course with the default draft,
          pushes it, and marks the component complete. Empty means the component has no type. The button walks those
          components in course order. The count beside it is how many of them are done, and it stays until the next press.
          The chat shows Writing… while each draft is in flight. A push that still has a gap stops on that component and
          shows the gap text. A missing OpenAI key shows the missing-key error and stops the run.
        </p>

        <h2>Settings you can change</h2>
        <p>Every component has:</p>
        <ul>
          <li>Description. The outline, the key topics, and the key goals. Save and Push keep it.</li>
          <li>Title.</li>
          <li>Type: Factual, Procedural, Conceptual principle, Causal or historical, or Synthesis.</li>
          <li>Core truth.</li>
          <li>Rubric checks, one to three. More than three is rejected.</li>
          <li>Misconceptions. A filled row needs both a wrong move and a component code.</li>
          <li>Prerequisite of this component, chosen from the other component codes.</li>
          <li>Encompasses, stability bump, chosen from the other component codes.</li>
        </ul>
        <p>The type adds its own fields:</p>
        <ul>
          <li>Factual: Fact, and Retrieval question.</li>
          <li>Procedural: Worked steps, one per line; Blanked step, starting at 0; Solo problem; Solo check.</li>
          <li>Conceptual principle: Case one, Case two, Prediction, and Rule.</li>
          <li>Causal or historical: Decision point, Flawed claim, and Causal chain.</li>
          <li>Synthesis: First component it mixes, Second component it mixes, and Rookie&apos;s faulty plan.</li>
        </ul>

        <h2>What to know when using it</h2>
        <ul>
          <li>Choose a course, then a component. With neither selected, the page says to choose a component.</li>
          <li>Fast Create All fills empty components on the selected course. It skips a component that already has a type.</li>
          <li>The chat draft is not the saved component until Push.</li>
          <li>Push and Save both clear Mark complete and mark the course not ready.</li>
          <li>Mark complete stays unavailable while any gap string would show on the structure row.</li>
          <li>How KC Tutor says a step, and the pass and retry wording, are not set on this page. Those balances live in code until a later admin page holds them.</li>
        </ul>
      </article>
    </main>
  );
}
