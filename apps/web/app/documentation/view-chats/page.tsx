import Link from "next/link";

export const metadata = { title: "View chats · Documentation · AI Tutor" };

export default function ViewChatsDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>View chats</h1>
        <p>
          View chats, at <Link href="/viewchats">/viewchats</Link>, reads classes from the kid tutor. The page says it does not edit blocks.
        </p>

        <h2>How it works</h2>
        <p>
          The side list is every class, or the classes for one child. Each row shows the child&apos;s name, the quest, the status,
          when it was last updated, the message count, and the score count. Choosing a row opens that class.
        </p>
        <p>
          The transcript is the stored messages, with the child&apos;s name on their lines and Tutor on the replies.
          Above it, Scores can be shown or hidden. Each row is Passed or Not yet, then the stored score shown out of 100.
          A goal score is 100 or 0. A close score is how many close questions have been answered correctly so far, and the page still prints that count out of 100.
          The row says whether it was a goal or the close. A goal score includes the goal number.
          A score can also show its hint tier, the feedback, and a misconception when one was stored.
          The header says whether the class is now on a goal, now on the close, or the quest is finished.
        </p>
        <p>
          View full prompt to debug opens the system prompt and the messages sent to the model for that turn, with the model name and the time.
          Request notes on that call are listed separately as Also sent to the model.
        </p>

        <h2>Settings you can change</h2>
        <p>
          This page does not change course content, the tutor profile, or a child&apos;s settings.
          The only control is the Student filter: Everyone, or one child. That filter changes which classes are listed.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>Until a class is chosen, the page says to pick a class and that the transcript opens here.</li>
          <li>An empty list says no classes yet, and to open a learner on the kid page.</li>
          <li>Removing a course from the catalog keeps these chats.</li>
          <li>Scores start collapsed. None yet means no scores are stored.</li>
          <li>The debug prompt is the call that was stored for that turn. It is not a way to edit the lesson.</li>
        </ul>
      </article>
    </main>
  );
}
