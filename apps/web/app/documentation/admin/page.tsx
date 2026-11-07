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
        <p>Agent customizations is the profile a person can change:</p>
        <ul>
          <li>
            How instructive, from 1 to 5. 1 is Socratic: one short question, and almost no explanation until they try.
            2 is Mostly questions: one short question, and a real explanation after two misses.
            3 is Balanced: a short explanation, then one question.
            4 is Mostly instructive: the fact and why it matters, then one question, with the longer explanation on the first miss.
            5 is Instructive: a fuller lesson first, and stuck students get the longer explanation sooner.
          </li>
          <li>
            Persona: Curious co-explorer, Tactical coach, Debate moderator, or Patient explainer.
          </li>
          <li>
            Reading voice: Early concrete, Middle-grade vivid, Precise visual, or Analytical high-school.
            It follows the persona unless a different voice is picked. Curious co-explorer uses Middle-grade vivid,
            Tactical coach uses Precise visual, Debate moderator uses Analytical high-school, and Patient explainer uses Early concrete.
          </li>
          <li>Metaphor set: Playground and sports, Buildings and machines, Policy and cause-and-effect, or None (plain language only).</li>
          <li>
            Sidekick: Bumbling partner, Rookie who trusts a picture, Pundit who skips the chain, or Off.
            The page says this is used only on teach-back.
          </li>
          <li>
            Struggle window: Short (1 miss), Standard (2), or Long (3). After that many misses, the tutor states the worked answer and explains why.
          </li>
          <li>Anti-spoiler. On hides the answer until the struggle window. Off confirms a correct idea as soon as they attempt it.</li>
          <li>One question. On never stacks a second question.</li>
          <li>Use student interests. On puts hobbies inside examples. Off keeps examples on the subject.</li>
          <li>
            Stay on the course. On stays with this course, unit, and quest, including closely related ideas.
            A different subject gets a short acknowledgment, then the tutor returns to the course. Off lets the tutor follow a tangent.
          </li>
          <li>Growth-mindset praise only. The page says this is on by default. Turning it off allows praise for a correct result.</li>
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
