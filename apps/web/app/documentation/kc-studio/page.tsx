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
          KC Course Creator, at <Link href="/kc-studio">/kc-studio</Link>, is the structure page for a
          knowledge-component course. KC Creator, at <Link href="/kc-creator">/kc-creator</Link>, is where one
          component&apos;s ordered blocks are edited. A blue banner with the Kinder Computers mark sits across the top
          of both screens, and of KC Tutor.
        </p>

        <h2>How it works</h2>
        <p>
          The left rail lists courses and links to Manage KC courses. New course opens a popup with the name, what the
          kid should come away able to do, the audience, and the kind. Minutes show in that popup only when the kind is
          Time boxed. The open course has a preferences strip: name, what the kid should come away able to do,
          audience, kind, and optional minutes. Save course writes those fields. Mark ready calls the ready check.
          Network stays a view-only picture: target nodes, patches, a solid line for a prerequisite, a dashed line for
          encompasses, and the edge list under the picture.
        </p>
        <p>
          AI Block Scope sits in the banner. It is the same multi-select as on KC Creator: how many of the ten block
          types the course AI may recommend, Select All, and Topic + MCQ Only. The choice is saved on the course. The
          next structure draft uses it, so recommended blocks stay inside that scope.
        </p>
        <p>
          The structure column lists each target. A row shows the title, the full description, and ordered block chips
          for the recommended sequence. The chips come from the stored recommendation, from the blocks already on the
          component, or from the Recommended blocks sentence in the description. The row also shows the gap strings,
          Marked complete, or Complete. Up and Down reorder the targets. Remove deletes that component. Patches are
          listed as Not a target and show the same description and chips. A row opens that component on KC Creator.
          This page does not edit a component&apos;s block fields.
        </p>
        <p>
          The chat drafts the component list. Kind sets how full the list is. Mastery is the fuller rigorous breakdown.
          Time boxed fits the minutes. Curiosity is a path through the subject. A requested count is honored. Each
          component gets a short summary that includes the recommended block sequence, an outline, topic-goal pairs, and
          the recommended blocks themselves. The draft preview shows that description and the same ordered chips. Push
          draft writes the list. Nothing is saved until you push it. Newly pushed components keep that recommended
          sequence in the description so the structure cards and KC Creator both show it.
        </p>
        <p>
          <Link href="/manage-kc-courses">Manage KC courses</Link> lists these courses. Delete asks for the same
          password as Manage courses and removes the KC course and its components.
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
          <li>Minutes, optional. A blank value is allowed. A number has to be greater than zero. The new-course popup asks for minutes only when the kind is Time boxed.</li>
          <li>AI Block Scope. At least one of the ten block types. An empty stored list means Topic / Goal.</li>
        </ul>
        <p>
          Component blocks are edited on KC Creator, not here. Readiness on a structure row is still the gap strings,
          Marked complete, or Complete.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>Open a course before asking for a draft. With no course selected, the page says to choose a course or create one.</li>
          <li>A draft is not stored until Push draft.</li>
          <li>The course list marks each course Ready or Draft.</li>
          <li>Mark ready is what makes the course appear in KC Tutor.</li>
          <li>Network does not edit edges. Prerequisites and encompasses are saved on the component in KC Creator.</li>
          <li>A structure row opens KC Creator for that component. It does not open an editor on this page.</li>
        </ul>
      </article>
    </main>
  );
}
