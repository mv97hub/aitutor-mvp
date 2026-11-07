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
          The intro is the first turn of a component. It says what the piece is, why it sits in the course, and what the
          child will do, then asks one question. It does not give the core truth. Instructive sets the shape. 1 opens on
          the question. 3 names the goal, then asks. 5 teaches a little more first. An interest is the example only when
          use interests is on. A time-boxed course keeps the intro to one sentence.
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
      </article>
    </main>
  );
}
