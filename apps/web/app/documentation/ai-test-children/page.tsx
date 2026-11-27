import Link from "next/link";

export const metadata = { title: "AI Test Children · Documentation · AI Tutor" };

export default function AiTestChildrenDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>AI Test Children</h1>
        <p>
          <Link href="/kc-test-children">AI Test Children</Link> starts a test-child run and downloads one file when it
          is done. A test child talks to the real tutor. Scoring happens outside the app, from that file. The page has
          three tabs: Children, New run, and Runs.
        </p>

        <h2>The loop</h2>
        <ol>
          <li>
            <code>POST /kc/harness/runs</code> creates the run. The New run tab sends the children, courses, tutor
            model, child model, caps, turn limit, stuck limit, concurrency, and behavior.
          </li>
          <li>
            <code>POST /api/kc/harness/runs/{"{id}"}/start</code> starts the run and returns. The loop stays on the
            server. Closing the page does not stop it.
          </li>
          <li>
            <code>GET /kc/harness/runs/{"{id}"}</code> is the poll. The Runs tab reads status until the run is finished
            or stopped.
          </li>
          <li>
            <code>GET /kc/harness/runs/{"{id}"}/download</code> is one markdown file for the whole run. It keeps every
            turn, the child and tutor prompts, the token lines, the automatic checks, and the block outcomes.
          </li>
        </ol>
        <p>
          Start, Stop, and Download are on the Runs tab. There is one Download for the run. Each run also shows when it
          ran, in Eastern time, and the values that identify it for the agent create call: run id, course ids, child
          profile ids, tutor model, child model, concurrency, turn limit, cost limit, and stuck limit. A child profile
          id is the child name plus the stored persona id. The agent call sends the name. Course ids go in courses.
          Cost limit is cents. Automatic checks are written when a chat finishes. They do not call a model.
        </p>

        <h2>Children</h2>
        <p>
          The Children tab is where you add, edit, copy, and archive test children. A child has an id, a name, and
          stored traits. What the tutor is told is the same Layer 2 form a parent fills in. How the child behaves is a
          separate set of hidden traits. The tutor is not told those traits.
        </p>
        <p>
          Use Add the starter set for AI_Child1 through AI_Child14. Names are AI_Child plus the next number. Numbers are
          never reused.
        </p>

        <h2>New run</h2>
        <p>
          Choose one or many test children and any ready course. Load fixture courses when you need the course that
          contains every block type. Tutor and child models come from the model list, including GPT-6 Luna and DeepSeek
          Flash. Child behavior is rule-led, free play, or a script of fixed lines.
        </p>
        <p>
          The spending cap defaults to 40 cents per chat. Hitting it ends that chat. A separate run cap starts blank.
          GPT-6 Luna has no published token price, so Luna calls show a blank dollar cost and stop at the token ceiling.
          The turn limit defaults to 40 child turns. The stuck limit defaults to 8. Concurrency is how many chats run at
          once. The runner will not go above 8.
        </p>

        <h2>When a chat stops</h2>
        <ul>
          <li>The component is completed.</li>
          <li>The child quits.</li>
          <li>The turn limit is reached.</li>
          <li>The chat is stuck: no change of block and substep for the stuck limit.</li>
          <li>The chat reaches its spending cap, or the run reaches its cap.</li>
          <li>The tutor route fails twice in a row.</li>
          <li>A safety flag, if you turned on stop on the first flag.</li>
        </ul>
        <p>
          A run that hits a limit is stopped. The download still has the turns that were stored. An agent can start the
          same kind of run without this page. That call is described on{" "}
          <Link href="/documentation/harness-agent">Harness agent</Link>.
        </p>
      </article>
    </main>
  );
}
