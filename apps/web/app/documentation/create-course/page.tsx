import Link from "next/link";

export const metadata = { title: "Create course · Documentation · AI Tutor" };

export default function CreateCourseDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>Create course</h1>
        <p>
          Create course, at <Link href="/create-course">/create-course</Link>, builds a draft the lesson desk can later import.
          The kid catalog does not change until that import.
        </p>

        <h2>How it works</h2>
        <p>
          A new course is created when its preferences are saved. The description in that form is what the quests follow.
          The course then moves through four stages: Quests, Goals/Success Criteria, Close, and Ready.
          The stage strip can reopen an earlier stage. A later stage stays disabled until the course reaches it.
        </p>
        <p>
          The chat drafts the current stage. The tree changes when Push draft to Tree is used. Undo last write is available after a write that can be undone.
          Gaps &amp; Issues lists what is still missing for this stage. Mark Complete stays unavailable until the stage can advance.
          On the Ready stage that button is Final Submit. After it succeeds, the course is marked Submitted.
        </p>
        <p>
          On Quests, a quest title can be added, edited, or deleted. On Goals/Success Criteria, each goal has a learning goal and a success criterion,
          and goals can be added or deleted. On Close, each question is edited on its own. The course tree shows the quests, goals, and close questions for the stage that is open.
        </p>
        <p>
          <Link href="/manage-courses">Manage courses</Link> lists these drafts. Copy asks for a new name. The copy gets a new code, and the creation chat stays behind.
          Delete asks for a password and removes the studio course and its creation chat.
        </p>

        <h2>Settings you can change</h2>
        <p>New course and Edit preferences use the same fields. Code and name stay fixed after the course is created.</p>
        <ul>
          <li>Code, required, up to 16 characters.</li>
          <li>Name, required, up to 240 characters.</li>
          <li>Course description, up to 240 characters. The empty-state text says this is what the quests follow.</li>
          <li>Number of quests, from 1 to 200. A new course starts at 10.</li>
          <li>Goals per quest, from 1 to 200. A new course starts at 3.</li>
          <li>Detail: Survey, Standard, or Go deep. A new course starts at Standard.</li>
          <li>
            Minimum time before the closing quiz: 2, 5, or 10 minutes. A new course starts at 5.
            The number is saved on the course and shown in Admin. The kid tutor does not use it to time a class.
          </li>
          <li>Close default: One question or Several questions. The preferences note says a quest can still use a different close.</li>
          <li>Answer style: Multiple choice, Single choice, or Mixed. A new course starts at Single choice.</li>
          <li>Audience: Ages 6-8, 9-11, 12-14, or 15-17. A new course starts at 9-11.</li>
          <li>Framework to honor, up to 80 characters. The field placeholder is None. Leaving it empty saves none.</li>
        </ul>
        <p>Each close question, edited on the Close stage, is one of:</p>
        <ul>
          <li>Single choice. The kid types the answer.</li>
          <li>Multiple choice. Four options, and one is marked Correct. The kid picks one.</li>
          <li>No questions.</li>
        </ul>
        <p>
          Model is a separate control. The dialog says this choice is only for Create course and does not change the kid tutor.
          The menu lists the models the server offers. Before that list loads, it shows gpt-4o-mini, gpt-4o, gpt-4.1-mini, and deepseek/deepseek-flash-latest.
          gpt-4o-mini stays the default. deepseek/deepseek-flash-latest uses OPENROUTER_API_KEY. The OpenAI models keep using OPENAI_API_KEY.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>The course is a draft until Admin imports it. Import copies it. This original stays here.</li>
          <li>Push draft to Tree is how a chat draft becomes part of the tree. Asking alone does not write the tree.</li>
          <li>If the stage has no draft ready to push, the page says to ask for the change on this stage.</li>
          <li>Code and name cannot be edited later. The other preferences can.</li>
          <li>A saved course can be reopened from the course list on this page.</li>
        </ul>
      </article>
    </main>
  );
}
