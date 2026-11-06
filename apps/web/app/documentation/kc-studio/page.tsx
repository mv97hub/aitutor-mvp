import Link from "next/link";

export const metadata = { title: "KC Studio · Documentation · AI Tutor" };

export default function KcStudioDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>KC Studio</h1>
        <p>
          KC Studio, at <Link href="/kc-studio">/kc-studio</Link>, builds the courses KC Tutor can open.
          The page says: course first, then one component. The chat only drafts.
        </p>

        <h2>How it works</h2>
        <p>
          A course is a list of components, grouped by type. Each component is one thing the child should learn.
          The structure list shows what is still missing on a component, or Complete. Up and Down change the order. Remove deletes that component.
          A component can also be added by typing a title.
        </p>
        <p>
          The chat asks for a draft. On the course, that draft is a list of component titles, and nothing is stored until Push draft.
          On one component, the draft replaces that component only, and Push draft is the write.
          Saving a component by hand also writes it. Editing a component on a course that was ready marks the course not ready again.
        </p>
        <p>
          Mark ready checks the target components. It refuses when the course has no components, or a target component has no type,
          no core truth, no rubric check, or a prerequisite or encompasses code that does not exist. The button then reads Ready.
          KC Tutor only lists courses that are ready.
        </p>
        <p>
          Network is a view of the components and the edges between them. The page says it is view only. Patches sit at the edge.
          A patch is a component that is not a target. The structure list marks those as Not a target.
        </p>

        <h2>Settings you can change</h2>
        <p>A course, new or saved, has:</p>
        <ul>
          <li>Name, required.</li>
          <li>What the kid should come away able to do.</li>
          <li>Audience: 6-8, 9-11, 12-14, or 15-17. A new course starts at 12-14.</li>
          <li>Kind: Mastery, Time boxed, or Curiosity. A new course starts at Mastery.</li>
          <li>Minutes, optional. A blank value is allowed. A number has to be greater than zero. KC Tutor shows this number only for a time-boxed course.</li>
        </ul>
        <p>Every component has:</p>
        <ul>
          <li>Title.</li>
          <li>Type: Factual, Procedural, Conceptual principle, Causal or historical, or Synthesis.</li>
          <li>Core truth.</li>
          <li>Rubric checks, one to three.</li>
          <li>Misconceptions. Each row is a wrong move and the component code that is actually broken.</li>
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
          <li>Open a course before asking for a draft. With no course selected, the page says to choose a course or create one.</li>
          <li>A draft in the chat is not stored until Push draft, and a component draft does not write until that button.</li>
          <li>The course list marks each course Ready or Draft.</li>
          <li>Mark ready is what makes the course appear in KC Tutor.</li>
          <li>Network does not edit edges. Prerequisites and encompasses are saved on the component.</li>
        </ul>
      </article>
    </main>
  );
}
