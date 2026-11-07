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
          Persona, lexicon, metaphors, sidekick, and the rest of the tutor profile stay on Agent customizations.
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
          and the chosen text is the answer. The model says the current step. It does not set the type, the edges, or the score.
          Pass, fail, fragile, known, and redirect stay with the scorer.
          If the selected model is an OpenAI model and OPENAI_API_KEY is unset, the page shows the same missing-key error as the kid tutor.
          If the selected model is deepseek/deepseek-flash-latest and OPENROUTER_API_KEY is unset, the page shows a missing-key error for that key.
          An OpenAI model does not read the OpenRouter key.
        </p>
        <p>The five types:</p>
        <ul>
          <li>
            Factual, recipe retrieval. Labels: Retrieval question, then Short confirmation. The known step is the retrieval question, so Short confirmation is the pass line, not another question.
            The retrieval question is typed. The check is a phrase match on the fact, or on the core truth when the fact is empty.
            An empty question is asked as &quot;What is the fact?&quot; A pass says &quot;Yes.&quot; and the fact or the core truth, and the session scores 100.
          </li>
          <li>
            Procedural, recipe worked-example. Labels: Worked example, Faded step, Solo solve. All three are typed.
            The worked example shows the steps and asks &quot;What did this example do?&quot; Any answer of at least 2 characters passes.
            The faded step shows the steps with a blank on the stored blanked step and says &quot;Fill the blank step.&quot; The check is that step&apos;s text.
            An index outside the list expects nothing and fails the phrase check. Solo solve asks the solo problem, or &quot;Solve it on your own.&quot; when that field is empty.
            The check is the solo check, or the core truth when the solo check is empty. A pass says &quot;That holds.&quot; and the core truth.
          </li>
          <li>
            Conceptual principle, recipe contrasting-cases. Labels: Predict two cases, See the contrast, State the rule.
            Predict two cases is a single choice. The prompt is the prediction. The two choices are case one and case two. Either choice passes when the text is at least 2 characters. There is no correct-case flag.
            See the contrast is typed. The tutor repeats both cases and asks &quot;What is different?&quot; Any answer of at least 2 characters passes.
            State the rule is typed. The check is a phrase match on the rule, or on the core truth when the rule is empty. A pass says &quot;That holds.&quot; and the core truth.
          </li>
          <li>
            Causal or historical, recipe decision-point. Labels: Decision point, Flawed claim, Short defense.
            Decision point is typed. The tutor says the decision point and &quot;What is at stake?&quot; Any answer of at least 2 characters passes.
            Flawed claim is a single choice. The prompt is &quot;Mark this claim:&quot; and the flawed claim. One choice is a mark the scorer already accepts, and its label contains one of: wrong, flawed, false, not true, no. The other choice is that the claim holds, and its label does not contain those phrases. A misconception match still runs first, on the choice text.
            Short defense is typed. The tutor says &quot;Defend the causal chain.&quot; The check is the causal chain, or the core truth when the chain is empty. A pass says &quot;That holds.&quot; and the core truth.
          </li>
          <li>
            Synthesis, recipe rookie-correction. Labels: Faulty plan, then Correct the plan. The known step is the faulty plan, so Correct the plan is the pass line.
            The card is offered only when prerequisites are known and at least 2 conceptual components on the course are known.
            Faulty plan is typed. The tutor says a rookie mixes the two component codes and states the faulty plan, then &quot;Correct the plan.&quot;
            When the mixes are empty, the joined text is &quot;two earlier components&quot;. The check is a phrase match on the core truth.
            A pass says &quot;Yes. The plan that holds is:&quot; and the core truth, and the session scores 100.
          </li>
        </ul>
        <p>
          A misconception hit finishes the session: status fragile, score 0, and a redirect to the broken component.
          The reply names the wrong move and that component&apos;s title and core truth, then &quot;The next card opens that component.&quot;
          A miss stays on the same step. The reply is &quot;Not yet.&quot;, the core truth, and &quot;That explanation is the one retry. Answer this same step again.&quot;
          Attempts increment and the loop does not stop. A pass on the final step marks the component known, with stability at least 1.0 and score 100.
          Each encompassed component gains 0.25 stability. An encompassed component that was not started becomes fragile.
        </p>
        <p>
          The tutor profile changes how a step is said. It does not change the component type, the links between components, or the score.
        </p>

        <h2>Settings you can change</h2>
        <p>
          This page does not edit the course. The choices on the page are which child, which ready course, which card to open, and Settings.
          Settings sits in the side column. It is not part of the lesson chat.
          The model list is gpt-4o-mini, gpt-4o, gpt-4.1-mini, gpt-4.1, gpt-6.1-sol, and deepseek/deepseek-flash-latest.
          gpt-4.1 is the default. Saving a model keeps it on this page. The next spoken step uses it.
          Age, reading level, modality, and interests save on the child. The next step&apos;s prompt uses the saved values.
          Those fields do not change the component type, the links, or the score.
          Component content is set in KC Creator. How the tutor speaks — persona, lexicon, metaphors, sidekick, the instructive slider,
          stay on course, and use interests — is the shared profile on Agent customizations. Those are not copied onto this list.
        </p>
        <p>
          The balances below are configuration. They are values in code, not controls on this page. A later admin page will hold them.
          That page is not described here.
        </p>
        <ul>
          <li>Step labels and their order, for each type.</li>
          <li>The step index that marks the component known. Factual and synthesis use the first step, so the second label is the pass line.</li>
          <li>Recipe name and the one-line recipe description.</li>
          <li>Open-step pass: when a step has no expected phrase, the normalized answer must be at least 2 characters.</li>
          <li>
            Phrase match. A phrase of 4 characters or fewer matches only as a whole word. A longer phrase matches when the answer contains it.
            The answer matches when it sits inside the phrase and is at least 8 characters. If the phrase has digits, the answer&apos;s digits include them and the answer has at most 8 words.
            If the answer has at least 3 words longer than 3 characters and every one of them is in the phrase, it matches.
            Otherwise the share of phrase words longer than 3 characters that appear in the answer must reach 0.6, rounded up.
          </li>
          <li>
            Wrong-move match. A negated answer (not, never, no, isnt, doesnt, dont, cannot, cant) does not match a wrong move that is not negated.
            The wrong move as a substring matches. Otherwise every word of a wrong move of at least 2 words must appear in order.
          </li>
          <li>The misconception finish: fragile, score 0, redirect to the broken component, and the reply that names the wrong move, the title, the core truth, and the next card.</li>
          <li>A final pass: known, stability at least 1.0, score 100. Each encompassed component gains 0.25 stability, and an unknown one becomes fragile.</li>
          <li>A miss stays on the same step. The retry wording is the one retry. The struggle window is in the prompt and is not a second KC setting.</li>
          <li>Pass lines: factual &quot;Yes.&quot; and the fact or core truth; synthesis &quot;Yes. The plan that holds is:&quot; and the core truth; the other three types &quot;That holds.&quot; and the core truth.</li>
          <li>Prompt sentences that stay fixed: one step this turn, do not ask a later step, one question at the end when the step asks something, and settings do not change the type, the edges, or the score.</li>
          <li>Card labels Fastest path, Foundation patch, and Stretch; at most 3 cards; a synthesis card only after 2 conceptual components are known.</li>
          <li>Factual: the retrieval question, the fact, the empty-question fallback &quot;What is the fact?&quot;, and the pass line.</li>
          <li>Procedural: the step list, the blanked index and its default 0, the blank marker, the lead-in sentences, the solo problem, the solo check, and the empty solo fallback.</li>
          <li>Conceptual: case one, case two, the prediction prompt, the contrast lead-in and &quot;What is different?&quot;, the rule, and &quot;State the rule.&quot;</li>
          <li>Causal: the decision-point text, &quot;What is at stake?&quot;, &quot;Defend the causal chain.&quot;, the flawed claim, the mark lead-in, the five passing phrases, and the two choice labels.</li>
          <li>Synthesis: the two mix codes, the joiner &quot; and &quot;, the empty-mix fallback &quot;two earlier components&quot;, the faulty plan, the rookie lead-in, &quot;Correct the plan.&quot;, the pass line, and the offer count of 2 known conceptual components.</li>
        </ul>

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
