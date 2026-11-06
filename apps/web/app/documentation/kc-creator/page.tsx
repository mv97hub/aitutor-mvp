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
          The left pane lists courses, then the components on the open course. Targets come first, in course order, then patches.
          The selected row is the component on screen. A patch can be opened here. It is still not a target.
        </p>
        <p>
          The middle pane is the manual editor. Save this component writes the fields and clears the course ready flag.
          Mark complete sits next to Save. It can be used only when the saved component has no gaps: a type, a core truth,
          at least one rubric check, and prerequisite and encompasses codes that exist. There is no extra gap rule.
          Mark complete records that flag. Save and Push clear it, and they clear course ready.
          On KC Course Creator the structure row then says Marked complete, or Complete when the gaps are empty and the flag is off,
          or the gap strings when something is still missing.
        </p>
        <p>
          The right pane is a conversation about this component only. It is stored for the component. It is not a kid-tutor message.
          The first view shows the saved text: title, type, core truth, rubric lines, each wrong move and its component code,
          prerequisite codes, encompasses codes, and the type fields for that type.
          Each reply talks about those fields and ends with a draft of this component. A later message revises that draft.
          The middle pane keeps the saved component until Push. Push writes the draft. Other components stay.
          Edges are rewritten only for this component. After Push, the middle pane shows the written fields and the thread says the draft was saved.
        </p>
        <p>
          A first message drafts the component from the course. A later message revises the draft already in the thread.
          A line such as &quot;Core truth: …&quot;, &quot;Type: causal&quot;, or &quot;Fact: …&quot; sets that field.
          &quot;make it causal&quot; switches the type. A plain sentence, with no labeled field, replaces the core truth.
          Nothing from the chat is stored on the component until Push.
        </p>

        <h2>Settings you can change</h2>
        <p>Every component has:</p>
        <ul>
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
          <li>The chat draft is not the saved component until Push.</li>
          <li>Push and Save both clear Mark complete and mark the course not ready.</li>
          <li>Mark complete stays unavailable while any gap string would show on the structure row.</li>
          <li>How KC Tutor says a step, and the pass and retry wording, are not set on this page. Those balances live in code until a later admin page holds them.</li>
        </ul>
      </article>
    </main>
  );
}
