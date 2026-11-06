import Link from "next/link";

export const metadata = { title: "Kid tutor · Documentation · AI Tutor" };

export default function KidTutorDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>Kid tutor</h1>
        <p>
          The home page, at <Link href="/">/</Link>, is the kid tutor.
        </p>

        <h2>How it works</h2>
        <p>
          A person picks a child, or adds one, then opens a class. A class is one quest from a course in the catalog.
          Starting a class always opens a new session for that quest. Choosing a class already in the list returns to that session.
        </p>
        <p>
          A new class begins on the first learning goal. The tutor works that goal until the answer meets its success criterion.
          A goal scores 100 when it meets the criterion and 0 when it does not. A passing result moves the class to the next goal.
          After the goals, the close starts, one question at a time. A multiple-choice question is a card: pick one option and press Check.
          A single-choice question is typed in the message box. The score stored for a close question is how many close questions
          have been answered correctly so far. A quest with no close questions finishes when the last goal passes.
          A finished quest stays in the class list.
        </p>
        <p>
          Misses are counted. The shared tutor profile sets how many misses to allow before a worked answer can move the step on.
          That count is the struggle window: one, two, or three. The profile also decides how much the tutor explains before asking,
          whether the answer stays hidden until that window ends, and whether examples may use the child&apos;s interests.
        </p>
        <p>
          A new class with no messages yet sends the first line for the child: &quot;Hi! I&apos;m ready to learn.&quot;
          Later messages are what the child types. Enter sends. Shift+Enter starts a new line. A message can be up to 2,000 characters.
          While a choice card is open, the message box waits. If a reply does not finish within 60 seconds, the page stops it and offers Try again.
          When a reply includes a triangle, the page draws it.
        </p>

        <h2>Settings you can change</h2>
        <p>Adding a child asks for two fields:</p>
        <ul>
          <li>Name, required, up to 120 characters.</li>
          <li>Age, a whole number from 4 to 18.</li>
        </ul>
        <p>
          Age fills a starting reading level and modality. Ages 4 to 8 start as early-reader and hands-on.
          Ages 9 to 11 start as middle-grade and story. Ages 12 to 14 start as grade-level and visual.
          Ages 15 to 18 start as high-school and verbal. Interests start empty.
        </p>
        <p>Settings, after a child is chosen, saves three fields on that child:</p>
        <ul>
          <li>Reading level, up to 80 characters.</li>
          <li>Modality, up to 80 characters.</li>
          <li>Interests, a comma-separated list.</li>
        </ul>
        <p>
          Name and age are shown in that dialog and are not edited there. When a class is open, the dialog also shows the course
          description under Enduring understanding. That text is not edited on this page.
        </p>
        <p>
          A new class asks for a catalog course and then a quest. How the tutor speaks is not set here. Persona, reading voice,
          metaphors, sidekick, how instructive, and the tutor checkboxes live on Agent customizations, and that one profile is used for every child.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>The landing links go to Administration, KC Course Creator, KC Creator, and KC Tutor.</li>
          <li>Switch child returns to the picker. The child&apos;s classes stay in the list.</li>
          <li>New class leaves other classes in the list.</li>
          <li>If the catalog is empty, the course menu says &quot;No courses yet.&quot; Import a course on Admin first.</li>
          <li>Interests show up inside examples only when Use student interests is on in the shared tutor profile.</li>
          <li>The message box says &quot;Choose an answer above&quot; while a choice card is waiting.</li>
        </ul>
      </article>
    </main>
  );
}
