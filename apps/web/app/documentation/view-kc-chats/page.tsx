import Link from "next/link";

export const metadata = { title: "View KC chats · Documentation · AI Tutor" };

export default function ViewKcChatsDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>View KC chats</h1>
        <p>
          View KC chats, at <Link href="/viewkcchats">/viewkcchats</Link>, reads component sessions from KC Tutor.
          The page says it does not edit components.
        </p>

        <h2>How it works</h2>
        <p>
          The side list is every KC chat, or the chats for one child. Each row shows the child&apos;s name, the component,
          the course, the status, when it was last updated, the message count, and whether a score is stored.
          Choosing a row opens that chat.
        </p>
        <p>
          The transcript is the stored messages, with the child&apos;s name on their lines and Tutor on the replies.
          Above it, Scores can be shown or hidden. A finished component shows Passed or Not yet, then the stored score out of 100.
          The header says whether the chat is now on a step, or the component is finished.
        </p>
        <p>
          View full prompt to debug opens the system prompt and the messages sent to the model for that turn, with the model name and the time.
          That is the call KC Tutor sent through the app, the same kind of record View chats keeps for a kid-tutor turn.
          Request notes on that call are listed separately as Also sent to the model.
        </p>

        <h2>Settings you can change</h2>
        <p>
          This page does not change a component, the tutor profile, or a child&apos;s settings.
          The only control is the Student filter: Everyone, or one child. That filter changes which chats are listed.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>Until a chat is chosen, the page says to pick a chat and that the transcript opens here.</li>
          <li>An empty list says no chats yet, and to open a learner on KC Tutor.</li>
          <li>Scores start collapsed. None yet means this component session has no score.</li>
          <li>The debug prompt is the call that was stored for that turn. A chat from before this page can have a transcript and no stored prompt.</li>
          <li>Kid-tutor classes stay on View chats. This page does not list them.</li>
        </ul>
      </article>
    </main>
  );
}
