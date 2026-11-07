import Link from "next/link";

import { LAYER_FIELDS, LAYER_HEADINGS, MOVE_SEQUENCES } from "@/lib/kc-layer-fields";

export const metadata = { title: "KC prompt layers · Documentation · AI Tutor" };

export default function KcPromptLayersPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>KC prompt layers</h1>
        <p>
          The KC tutor prompt is seven layers. The model writes the reply. The app sets the type, the edges, the score,
          the unit close, and the course outro. Temperature is 0.4. The same names and the same hover text appear on
          Agent customizations, on KC Tutor settings, on KC Creator, and in the debug Variables panel.
        </p>

        <h2>Moves</h2>
        <p>Every sequence starts with the intro and ends with the unit close. The course outro follows the unit close only on the turn the course is finished.</p>
        <ul>
          {MOVE_SEQUENCES.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>

        <h2>Intro</h2>
        <p>
          Orient is the first turn when an outline is stored. It elaborates that outline and does not open the topics
          or the goals. It does not use the course description. Instructive still sets how much is said before the
          question. A time-boxed course keeps that opening to one sentence.
        </p>

        <h2>Unit close</h2>
        <p>
          The unit close is in the same reply that ends the component. A known unit names the component and what the
          child can now do. A fragile unit says the unit is paused and still needs another look, and names the patch
          when there is one. It does not call a fragile unit finished work. Levels 1 and 2, and every time-boxed course,
          use one or two sentences. Levels 3 to 5 restate the idea in the child&apos;s words, then the status line.
        </p>

        <h2>Course outro</h2>
        <p>
          The course outro is appended after the unit close only when every target component is known. It names the
          course and recaps the ideas. If any target is unknown or fragile, there is no course outro, and the unit close
          points at the next card.
        </p>

        {LAYER_HEADINGS.map((heading) => (
          <section key={heading}>
            <h2>{heading}</h2>
            {LAYER_FIELDS.filter((field) => field.layer === heading).map((field) => (
              <section key={field.name}>
                <h3>{field.name}</h3>
                <p>{field.hover}</p>
                <p>{field.role}</p>
                <p>
                  {field.kind}. {field.where}.
                </p>
              </section>
            ))}
          </section>
        ))}

        <h2>How the prompt is written</h2>
        <p>
          The debug Variables panel still groups the stored settings under the seven layers above. The text
          sent to the model does not. That text is seven instruction sections. A setting is written once, as
          the behavior it asks for, in the section where that behavior changes the reply. A stored struggle
          window or enrichment that this turn replaces is not sent. Prerequisite codes and encompass codes
          stay in the panel and stay out of the prompt.
        </p>
        <h3>This turn</h3>
        <p>
          Who is speaking, which move this is, and the one job of the reply. The opening, the unit close, and
          the course outro are here because they change that job.
        </p>
        <h3>What to teach</h3>
        <p>
          Only this step&apos;s field. A topic turn names that topic and its goal. The outline is included on
          Orient and not on a later topic. The course description is not used. A practice step shows the field
          for that step. A withheld fact or rule is said only when a reveal or a passed close allows it.
        </p>
        <h3>Who you are talking to</h3>
        <p>
          One short profile: name, age, reading level, modality, and interests, each with its effect. An early
          reading level means shorter sentences. A visual modality means a described picture only on a move
          that already has cases or steps. Interests are an example only when that switch is on.
        </p>
        <h3>How to teach</h3>
        <p>
          Instructive level, struggle window, enrichment, stay on course, the response to a wrong move,
          support band, and course kind, as the behavior for this turn. Time boxed and curiosity appear as
          the limits they impose. Anti-spoiler, one question, and growth-mindset praise are not printed as
          yes or no. Anti-spoiler is the sentence that says when the core truth may be spoken. When one
          question or growth-mindset praise still changes the reply, that effect is one line here.
        </p>
        <h3>How to sound</h3>
        <p>
          Persona, lexicon, metaphors, and sidekick collapse into one voice paragraph. That voice does not
          change the move, the expected answer, or the score.
        </p>
        <h3>What just happened</h3>
        <p>
          Attempts, the last answer, the hint already given, affect, whether help was requested, the
          off-course count, and the last few messages. This is state. The model is told not to treat it as a
          new rule.
        </p>
        <h3>What to return</h3>
        <p>
          The decision fields and what each value means, kept short and last. The response schema and the
          temperature stay as they are.
        </p>
      </article>
    </main>
  );
}
