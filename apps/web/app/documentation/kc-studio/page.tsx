import Link from "next/link";

export const metadata = { title: "KC Course Creator · Documentation · AI Tutor" };

export default function KcStudioDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>KC Course Creator</h1>
        <p>
          KC Course Creator, at <Link href="/kc-studio">/kc-studio</Link>, is the structure page for a knowledge-component course.
          KC Creator, at <Link href="/kc-creator">/kc-creator</Link>, is where one component is added and updated.
          A blue banner with the Kinder Computers mark sits across the top of both screens, and of KC Tutor.
          The quest course creator does not use that banner.
        </p>

        <h2>How it works</h2>
        <p>
          KC Course Creator defines the component list. The left rail lists courses and links to Manage KC courses.
          New course opens a popup with the name, what the kid should come away able to do, the audience, and the kind.
          Minutes show in that popup only when the kind is Time boxed. Create course saves the course, closes the popup, and selects it.
          The open course has a preferences strip: name, what the kid should come away able to do, audience, kind, and optional minutes.
          Save course writes those fields. Mark ready calls the ready check and still refuses when the course has no components,
          or any target has no type, no core truth, no rubric check, or a prerequisite or encompasses code that does not exist.
          Network stays a view-only picture: target nodes in a grid, patches in a column on the right, a solid line for a prerequisite,
          a dashed line for encompasses, and the edge list under the picture.
        </p>
        <p>
          The structure column lists groups in this order: Factual, Procedural, Conceptual principle, Causal or historical, Synthesis,
          then No type yet. Each row shows the title, the description under the title, the type, and either the gap strings, Marked complete, or Complete.
          The description is a short summary. The outline and the topic-goal pairs are stored beside it and saved when you push.
          Marked complete means the component was marked on KC Creator and still has no gaps. Complete means the gaps are empty and it has not been marked.
          Up and Down reorder the targets. Remove deletes that component. Add a component by title creates a target with no type and no fields.
          Patches are listed as Not a target. A row, including a patch, opens that component on KC Creator. This page does not edit a component&apos;s fields.
        </p>
        <p>
          The chat on this page has a model menu in the composer: gpt-4o-mini, gpt-4o, gpt-4.1-mini, gpt-4.1, gpt-6.1-sol, and ~deepseek/deepseek-flash-latest.
          gpt-4.1 is the default. gpt-6.1-sol is the strongest model this app&apos;s OpenAI client accepts.
          ~deepseek/deepseek-flash-latest is called through OpenRouter.
          The chosen model is sent with the draft. It does not change scoring, edges, or the component types.
          OpenAI models use OPENAI_API_KEY. DeepSeek Flash uses OPENROUTER_API_KEY.
          If the key for the chosen model is missing, the chat shows that missing-key error. The other key is not required for that call.
          Enter and the up arrow both send the message. While the reply is being written, the composer says Writing… and cannot be sent again.
          The draft names the subject from the course name and description, then the major ideas a strong course on that
          subject has to cover, and only then the component list. It does not split the description into titles.
          Kind sets how full the list is. Mastery is the fuller rigorous breakdown. Time boxed fits the minutes.
          Curiosity is a path through the subject. A requested count is honored with distinct components:
          &quot;minimum of 10&quot; means at least ten, and &quot;10 components&quot; means ten.
          A pasted list of titles is used as written. Each component also gets a short summary, an outline, and topic-goal pairs.
          Push draft writes the titles and those fields. It does not fill one component&apos;s type fields.
          Nothing is saved until you push it.
        </p>
        <p>
          <Link href="/manage-kc-courses">Manage KC courses</Link> lists these courses. Delete asks for the same password as Manage courses
          and removes the KC course and its components.
        </p>
        <p>
          KC Creator is the editor. Choose a course from the dropdown, then a component. Targets are listed in course order, then patches.
          Changing the course opens that course’s first component.
          The middle pane is the manual editor: description, title, outline, topic rows, type, the fields for that type, core truth, one rubric line for each topic goal and then the practice checks,
          misconceptions, prerequisites, and encompasses. Save this component writes that component and clears course ready.
          The right-hand chat is about that component only. It opens with the description, then the saved text, and goes into the topic before the fields. Each reply ends with a draft.
          A later message revises that draft. The middle pane keeps the saved component until Push. Push writes the draft for this component only.
          Mark complete sits next to Save. It is available only when that component has no gaps. Saving or pushing clears the mark.
        </p>
        <p>
          The section for the editor itself is <Link href="/documentation/kc-creator">KC Creator</Link>.
        </p>

        <h2>Settings you can change</h2>
        <p>A course, new or saved, has:</p>
        <ul>
          <li>Name, required.</li>
          <li>What the kid should come away able to do.</li>
          <li>Audience: 6-8, 9-11, 12-14, or 15-17. A new course starts at 12-14.</li>
          <li>Kind: Mastery, Time boxed, or Curiosity. A new course starts at Mastery.</li>
          <li>Minutes, optional. A blank value is allowed. A number has to be greater than zero. The new-course popup asks for minutes only when the kind is Time boxed. KC Tutor shows this number only for a time-boxed course.</li>
        </ul>
        <p>
          Component fields are edited on KC Creator, not here. See that section for the type fields, the chat, Push, and Mark complete.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>Open a course before asking for a draft. With no course selected, the page says to choose a course or create one.</li>
          <li>A title-list draft is not stored until Push draft.</li>
          <li>The course list marks each course Ready or Draft.</li>
          <li>Mark ready is what makes the course appear in KC Tutor.</li>
          <li>Network does not edit edges. Prerequisites and encompasses are saved on the component in KC Creator.</li>
          <li>A structure row opens KC Creator for that component. It does not open an editor on this page.</li>
        </ul>
      </article>
    </main>
  );
}
