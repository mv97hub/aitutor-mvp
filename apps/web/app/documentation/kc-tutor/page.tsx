import Link from "next/link";

export const metadata = { title: "KC Tutor · Documentation · AI Tutor" };

export default function KcTutorDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>KC Tutor</h1>
        <p>
          KC Tutor, at <Link href="/kc-tutor">/kc-tutor</Link>, practices one component at a time.
          The header says it uses the same child and the same tutor settings as the lesson page.
        </p>

        <h2>How it works</h2>
        <p>
          Open asks for a child and a ready course. The course list is only courses KC Studio has marked ready.
          The ring counts target components that are known, out of all target components. A segment is known, fragile, or not started.
          The caption says how many are known, and adds &quot;some fragile&quot; when any segment is fragile.
          A time-boxed course also shows its minutes. Mastery and curiosity do not.
        </p>
        <p>Up to three cards offer the next work:</p>
        <ul>
          <li>Fastest path is the next target component whose prerequisites are known.</li>
          <li>
            Foundation patch is a component that is not a target, when a target is waiting on it.
            If the last answer matched a misconception, this card is the component that is actually broken.
          </li>
          <li>
            Stretch is a later component whose prerequisites are known. A synthesis component waits until two conceptual components are known.
          </li>
        </ul>
        <p>
          A card opens that one component. The lesson shows the title, the recipe, and the current step.
          The child types an answer and presses Send. The recipe comes from the component type:
        </p>
        <ul>
          <li>Factual uses retrieval: one retrieval question. An answer that lines up with the fact finishes it, and the tutor confirms the fact. An empty fact is checked against the core truth.</li>
          <li>Procedural uses a worked example, then one faded step, then a solo solve. The faded step is checked against the blanked step. The solo solve is checked against the solo check, or the core truth when that field is empty.</li>
          <li>Conceptual principle uses two cases to predict, then the contrast, then the rule. The rule step is checked against the rule, or the core truth when that field is empty.</li>
          <li>Causal or historical uses a decision point, a flawed claim to mark, then a short defense. Marking the claim accepts an answer that calls it wrong, flawed, false, not true, or no. The defense is checked against the causal chain, or the core truth when that field is empty.</li>
          <li>Synthesis has a rookie state a faulty plan that mixes two earlier components. The child corrects it, and the answer is checked against the core truth.</li>
        </ul>
        <p>
          Steps that ask the child to look or predict, before the checked step, accept an answer with at least two letters or digits.
          A miss stays on the same step. The reply includes the core truth and asks for that step again.
          An answer that matches a stored wrong move marks the component fragile, scores 0, finishes the session, and names the broken component.
          The page then says which card is next. A component that is finished on its last step is marked known and scores 100.
          An encompasses link from that component adds a small stability bump to the component it encompasses, and can move that one from not started to fragile.
        </p>
        <p>
          The tutor profile changes how a step is said. It does not change the component type, the links between components, or the score.
        </p>

        <h2>Settings you can change</h2>
        <p>
          This page does not edit the course. The choices are which child, which ready course, and which card to open.
          Component content is set in KC Studio. How the tutor speaks is the shared profile on Agent customizations.
          The children are the same children as on the home page.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>A course that is still a draft in KC Studio does not appear here.</li>
          <li>With no card open, the page says a card opens one component.</li>
          <li>When every target component is known, the page says so and offers no cards.</li>
          <li>A finished component hides the answer box and shows the score.</li>
          <li>Home in the header returns to the kid tutor.</li>
        </ul>
      </article>
    </main>
  );
}
