import Link from "next/link";

export const metadata = { title: "Parent portal · Documentation · AI Tutor" };

export default function ParentPortalDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>Parent portal</h1>
        <p>
          The parent portal, at <Link href="/parent">/parent</Link>, lets a parent read their children&apos;s tutor chats,
          see Detailed Progress, and ask for a short summary with talking points.
        </p>
        <p>
          <strong>There is no login yet.</strong> Anyone who can open the page can choose any parent, the same as the
          child pages today. Linking a child to a parent only decides what that parent&apos;s pages show. It is not a
          security boundary. Add a real login before families use it.
        </p>

        <h2>How it works</h2>
        <ul>
          <li>
            <strong>Landing.</strong> Pick a parent card, or add a parent by name. A new parent, or one with no children,
            opens Settings first.
          </li>
          <li>
            <strong>Settings.</strong> A checklist of every child. Tick the children this parent follows and save. A child
            can have more than one parent, and a parent can follow more than one child.
          </li>
          <li>
            <strong>Dashboard.</strong> Choose one of your children, then Chats or Progress.
          </li>
          <li>
            <strong>Chats.</strong> The same transcript as <Link href="/admin/kc-chats">KC View Chats</Link>, without the
            prompt and debug buttons. The server does not send prompts to a parent page at all.
          </li>
          <li>
            <strong>Progress.</strong> The Detailed Progress page for that child. Its links stay in the parent area, and the
            link into the child&apos;s tutor is hidden.
          </li>
        </ul>

        <h2>Summary and talking points</h2>
        <p>
          On a chat, Generate summary and talking points writes a short, plain note for the parent: what the child worked
          on, where they got stuck, and a few things to say or ask. It uses the default KC model and needs the same API key
          as the tutor. The note appears in a small panel above the transcript. It is made when you click, and it is not
          saved. Click again for a fresh note.
        </p>

        <h2>What to know when using it</h2>
        <ul>
          <li>A parent can only open chats and progress for a linked child. Another child is refused.</li>
          <li>Safety tags and the safety review stay in the admin KC View Chats.</li>
          <li>An empty chat list means the child has not worked with the tutor yet.</li>
        </ul>
      </article>
    </main>
  );
}
