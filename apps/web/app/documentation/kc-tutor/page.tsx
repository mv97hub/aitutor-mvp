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
          The lesson is a chat. Questions and single-choice answers live in the thread.
          Settings is a button in the side column, separate from the lesson chat.
          It chooses the model from the same list as KC Course Creator. gpt-4.1 is the default.
          deepseek/deepseek-flash-latest calls OpenRouter with OPENROUTER_API_KEY. The OpenAI models stay on OPENAI_API_KEY.
          The same settings surface edits the child fields the prompt already includes: age, reading level, modality, and interests.
          Persona, lexicon, metaphors, sidekick, instructive, struggle window, stay on course, use interests,
          misconception policy, enrichment, and self-explanation stay on Agent customizations.
          The field catalog is <Link href="/documentation/kc-prompt-layers">KC prompt layers</Link>.
        </p>

        <h2>How it works</h2>
        <p>
          Open asks for a child and a ready course. The course list is only courses KC Course Creator has marked ready.
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
            Stretch is a later component whose prerequisites are known. A synthesis component is offered only after 2 conceptual components are known.
          </li>
        </ul>
        <p>
          A card opens that one component. The stage header keeps the title, the recipe name, the step label, and the score once the session is completed.
          A redirect still reads &quot;Next card: &quot; and the title. The tutor&apos;s question is an assistant bubble. A typed answer is a user bubble.
          Enter sends. Two steps are single-choice bubbles in the thread. Every other step is typed in the same thread.
          While a choice is unanswered, the composer says &quot;Choose an answer above&quot; and does not send. After Check, the widget settles on &quot;Your choice&quot;
          and the chosen text is the answer. The model writes the reply and a structured decision. It does not set the type, the edges, or the score.
          The app checks that decision, then writes known, fragile, redirect, the unit close, and the course outro.
          If the selected model is an OpenAI model and OPENAI_API_KEY is unset, the page shows the same missing-key error as the kid tutor.
          If the selected model is deepseek/deepseek-flash-latest and OPENROUTER_API_KEY is unset, the page shows a missing-key error for that key.
          An OpenAI model does not read the OpenRouter key.
        </p>
        <p>
          Each type runs a fixed move sequence. The sequences, the intro, the unit close, the course outro, and every field
          are on <Link href="/documentation/kc-prompt-layers">KC prompt layers</Link>.
          Choice widgets stay only for conceptual predict and the causal flawed claim. Every other move is typed.
          Phrase matching is not the pass rule. A stored wrong move is still a backstop when the model misses it.
          The first hit explains that move and asks it again. A second hit redirects and leaves the unit fragile.
          Known requires the final move with no reveal. Stability still rises to at least 1.0, and each encompassed component gains 0.25.
        </p>
        <p>
          The tutor profile changes how a step is said. It does not change the component type, the links between components, or the score.
        </p>
        <p>
          Debug, on the right, opens a panel beside the lesson. The chat stays usable while the panel is open.
          Variables groups every layer field under seven headings. An empty value stays visible.
          Prompts lists each request and response for this session, oldest first.
        </p>

        <h2>Settings you can change</h2>
        <p>
          This page does not edit the course. The choices on the page are which child, which ready course, which card to open, and Settings.
          Settings sits in the side column. It is not part of the lesson chat.
          The model list is gpt-4o-mini, gpt-4o, gpt-4.1-mini, gpt-4.1, gpt-6.1-sol, and deepseek/deepseek-flash-latest.
          gpt-4.1 is the default. Saving a model keeps it on this page. The next spoken step uses it.
          Age, reading level, modality, and interests save on the child. The next step&apos;s prompt uses the saved values.
          Those fields do not change the component type, the links, or the score.
          Component content is set in KC Creator, including transfer case and counterfactual.
          How the tutor speaks is the shared profile on Agent customizations, grouped by layer.
          The same hover text is the field description on <Link href="/documentation/kc-prompt-layers">KC prompt layers</Link>.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>A course that is still a draft does not appear here.</li>
          <li>With no card open, the page says a card opens one component.</li>
          <li>When every target component is known, the page says so and offers no cards.</li>
          <li>A finished component hides the composer and shows the score in the header.</li>
          <li>The wording of a question comes from the model. The score does not.</li>
        </ul>
      </article>
    </main>
  );
}
