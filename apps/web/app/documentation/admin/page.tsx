import Link from "next/link";

export const metadata = { title: "Admin · Documentation · AI Tutor" };

export default function AdminDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>Admin</h1>
        <p>
          Admin is the lesson desk at <Link href="/admin">/admin</Link>, plus{" "}
          <Link href="/admin/agent-customizations">Agent customizations</Link>. The bar also links to{" "}
          <Link href="/viewchats">View chats</Link> and <Link href="/viewkcchats">View KC chats</Link>.
        </p>

        <h2>How it works</h2>
        <p>
          The lesson desk lists courses in the kid catalog. Choosing one opens its tree: each quest, the learning goal and
          success criterion for each goal, and the close. A close is summarized as no questions, single choice, multiple choice,
          or mixed. Multiple-choice options are listed, and the correct one is marked. The tree is for reading. This page does not edit quests.
        </p>
        <p>
          Import course copies a saved Create course draft into the catalog. The Create course original stays.
          Remove course takes a course out of the catalog and keeps the kid chats for that course.
        </p>
        <p>
          Agent customizations holds one tutor profile. Saving it changes how the kid tutor and KC Tutor speak, for every child.
          The page says that name, age, reading level, modality, and interests stay on the child.
        </p>

        <h2>Settings you can change</h2>
        <p>
          The lesson desk has no course-content fields. Import and remove are the actions, and the tree is a view.
          A course header shows its code, title, description, quest count, goals per quest, the stored quiz minutes, and the age band.
        </p>
        <p>
          Agent customizations groups the shared profile by layer. The field text is the same as{" "}
          <Link href="/documentation/kc-prompt-layers">KC prompt layers</Link>.
        </p>
        <ul>
          <li>Layer 3, Voice: persona, reading voice, metaphor set, sidekick, and use interests.</li>
          <li>
            Layer 4, Guidance: how instructive from 1 to 5, struggle window, stay on course, misconception policy, and enrichment.
            The struggle window labels are Minimum (1 try), Standard (2 tries), and Wide (3 tries). The stored values stay short, standard, and long.
          </li>
          <li>
            Anti-spoiler, one question, and growth-mindset praise are shown disabled and labeled Deprecated. Their stored values stay as they are.
          </li>
          <li>Layer 6, Metacognition: self-explanation.</li>
        </ul>

        <h2>What to know when using it</h2>
        <ul>
          <li>A child can start a class only from a course that has been imported here.</li>
          <li>An empty catalog says to import a Create course draft.</li>
          <li>Import says there are no saved drafts when Create course has none.</li>
          <li>Saving the profile says it applies to every student.</li>
          <li>The sidebar link Kid session returns to the home page.</li>
        </ul>
      </article>
    </main>
  );
}
