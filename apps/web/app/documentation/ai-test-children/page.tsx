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
          <Link href="/kc-test-children">AI Test Children</Link> is a testing page. You define children such as
          AI_Child1, start a run, read the finished chats, and review recommendations. A test child talks to the real
          tutor through the same two routes a child&apos;s browser uses. The live tutor path is not given an extra
          step. The page only adds a second AI on the child&apos;s side of the chat.
        </p>
        <p>
          Profiles for every test child are also listed at{" "}
          <Link href="/kc-test-children/profiles">/kc-test-children/profiles</Link>. The Children tab is where you add,
          edit, copy, and archive.
        </p>

        <h2>Why it exists</h2>
        <p>
          One chat with one child does not tell you whether the tutor is fair, stuck, or too long. A run is many chats:
          several children, several components, several tutor models, repeated a few times. The page shows where the
          tutor is weak, and it turns those numbers into cards a person can accept or reject. Nothing on this page
          rewrites the live prompt by itself.
        </p>

        <h2>Two halves of a child</h2>
        <p>
          What the tutor is told is the same Layer 2 form a parent fills in: age, grade band, reading level, response
          length, expression, explanation style, challenge appetite, tone, learning support, interest tags, and
          favorites. Those fields are written onto a student row, so the tutor reads them exactly as it does for a real
          child.
        </p>
        <p>
          How the child behaves is a separate set of hidden traits. The tutor is not told them. A parent may say
          &quot;on grade&quot; when the child struggles to read. AI_Child10 is set up that way on purpose. The gap shows
          whether the tutor adapts to the child in the chat or only to the form.
        </p>

        <h2>Traits</h2>
        <p>Each trait is a scale from 1 to 5. The editor shows a sentence for the current value.</p>
        <ul>
          <li>Maturity, attention span, curiosity, and how fast boredom builds.</li>
          <li>Prior knowledge and learning rate. A hint raises the chance of a right answer when learning rate is high.</li>
          <li>Actual reading ability and writing style, including short replies and spelling slips.</li>
          <li>Compliance, tangent rate, and what the child does when unsure: guess, say idk, ask for a hint, or ask for the answer.</li>
          <li>Wrong-answer pattern: a stored misconception, a careless slip, a half answer, or the right idea in the wrong words.</li>
          <li>Frustration tolerance, buttons versus typing, agreeing and echoing, boundary testing, and the quit point.</li>
        </ul>
        <p>
          What the child does each turn is chosen by these rules. The child model only writes the words, and only when
          words are needed. A button, a choice, or &quot;idk&quot; does not call a model. The same seed repeats the same
          intents. The tutor&apos;s wording still varies, which is why a comparison uses several iterations.
        </p>

        <h2>Starter set</h2>
        <ul>
          <li>AI_Child1, steady 10-year-old. The baseline.</li>
          <li>AI_Child2, eager 6-year-old. Short sentences and buttons.</li>
          <li>AI_Child3, bored 12-year-old who already knows most of it and presses Got it - move on.</li>
          <li>AI_Child4, distracted 8-year-old with side stories.</li>
          <li>AI_Child5, anxious 11-year-old who says idk and asks for the answer.</li>
          <li>AI_Child6, confident 9-year-old who guesses and uses stored misconceptions.</li>
          <li>AI_Child7, reluctant 15-year-old. Short, low compliance.</li>
          <li>AI_Child8, deep questioner, 13.</li>
          <li>AI_Child9, English learner, 10. Right ideas in imperfect words.</li>
          <li>AI_Child10, struggling reader who was told &quot;on grade&quot;.</li>
          <li>AI_Child11, agreeable echo. Yes, and the tutor&apos;s words back.</li>
          <li>AI_Child12, boundary tester. Mild scripted probes only.</li>
        </ul>
        <p>Names are AI_Child plus the next number. Numbers are never reused. Use Add the starter set on the Children tab.</p>

        <h2>One turn, and when a chat stops</h2>
        <p>
          The runner sits in the open browser tab. It reads the session, asks the tutor to speak if the block is not
          open yet, works out what a real child could do (type, pick a choice, or press a button), asks the child route
          for the move, and sends that text to the tutor answer route. Each turn stores the intent, the child&apos;s
          boredom, frustration, and confusion, and the session before and after.
        </p>
        <p>A chat stops when any of these happen:</p>
        <ul>
          <li>The component is completed.</li>
          <li>
            The child quits. That is a result, not an error. Quitting is the last resort: the child stays when the
            tutor asks whether to move on, or when a continue button is on screen. A quit happens only after boredom
            or frustration has stayed past the quit point, and nothing offers a way to continue.
          </li>
          <li>The turn limit is reached. The default is 40 child turns.</li>
          <li>The chat is stuck: no change of block or substep for 8 child turns.</li>
          <li>The chat reaches its spending cap. The default is 40 cents. That chat ends and its tutor session is closed. Other chats in the run continue.</li>
          <li>A run-wide cap, if you filled one in. That field starts blank.</li>
          <li>The tutor route fails twice in a row.</li>
          <li>A safety flag, if you turned on stop on the first flag.</li>
        </ul>
        <p>
          If you close the tab, the run pauses. Resume picks up queued chats. Turns inside one chat stay in order.
          Several chats run side by side. The default is 3. While a chat is running, the Runs tab and the chat view show
          each tutor message and each child reply as they happen.
        </p>

        <h2>New run settings</h2>
        <p>
          Choose one or many test children, any ready course, and the fixture course that contains all eleven block
          types. Tutor, child, and judge models come from the full model list, including GPT-6 Luna and DeepSeek Flash.
          Defaults: child gpt-4.1-mini, judge gpt-6.1-sol. The tutor model is yours to compare.
        </p>
        <p>
          Child behavior is rule-led, free play, or a script of fixed lines. Rule-led is the one to use when you want
          the checks to know what the child meant. The page warns when the child model and the tutor model are the same.
        </p>
        <p>
          Iterations repeat each combination. Three to five is the useful minimum, because the tutor is not
          deterministic. The screen shows the multiplication and a rough cost before anything starts. After the first
          measured run, treat that estimate as a guess, not a bill.
        </p>

        <h2>One chat, and many chats</h2>
        <p>
          The Chat tab shows the transcript with each child turn labeled by intent, the automatic checks, and the
          judge&apos;s scorecard. Automatic checks cost nothing. They catch a false pass, a false fail, an idk or a yes
          that moved the step, a side question that used an attempt, a button that did not move, a reply that asked a
          question the prompt forbade, a reply that is too long for the child&apos;s setting, leaked words such as
          &quot;Block 2&quot;, repeated praise, safety flags, empty replies, and cost. For a few key instructions the
          check records whether the prompt contained the line and whether the reply obeyed it.
        </p>
        <p>
          The judge is a separate model. It scores teaching, correctness, engagement, side remarks, age fit, pacing,
          feedback, scoring fairness, emotional attunement, safety, getting stuck, natural conversation, closing, and
          whether the test child was realistic. Every score quotes a turn. Chats with low child realism are left out of
          the roll-up. Use the checks to decide and the scores to explain.
        </p>
        <p>
          Results group the run by child, course, component, block type, and tutor model. You can compare two runs
          matched by child, component, model, and seed. A small gap on a few chats is shown as no clear difference. A
          new safety failure, a new stuck chat, or a new route failure that was not in the baseline is worse, whatever
          the averages say.
        </p>

        <h2>Recommendations</h2>
        <p>
          Findings name the block type the issue happened on. Cards are not created when a run finishes. They appear
          after you press Draft cards from this run on the Recommendations tab. A card has a plain title, the block
          type, the evidence, the cause (a setting, a prompt section, a loop rule, or the course content), the proposed
          change, whether the prompt gets shorter or longer, the risk, and a status. Statuses are new, accepted,
          rejected, on trial, shipped, verified, and regressed. Drafting does not change the live tutor.
        </p>
        <p>
          The drafter looks for a line to cut or shorten before it looks for a line to add. A batch that only proposes
          additions is incomplete, and the page adds a shorter option when that happens. Remove or shorten is a normal
          outcome. You review every card. Accept does not change the live profile.
        </p>
        <p>
          Try it, on a settings card, copies the tutor profile into a trial profile and queues the same children,
          components, models, and seeds. Trial profiles stay out of the tutor pickers. Real children stay on their own
          profile. You start the trial run yourself. Wording and loop changes are made on a branch and compared with
          the baseline run. Safety settings are not trialed here, because there is one global safety row.
        </p>
        <p>
          Mark a run as the baseline of a saved suite. A later run of that suite is compared with it and shown red,
          amber, or green.
        </p>

        <h2>Safety probes</h2>
        <p>
          AI_Child12 sends mild scripted probes: a silly or personal question, a small personal detail such as a pet,
          and a try at pulling the tutor off its role. Flags from those chats show on the harness chat. They are kept
          out of the AI Safety review queue.
        </p>

        <h2>Token usage and the spending cap</h2>
        <p>
          Tutor calls for test children are recorded the usual way and show on{" "}
          <Link href="/admin/token-usage">Token usage</Link>. The page defaults to Both, with a Real / Test / Both
          choice, and each child row is marked. Child, judge, and recommendation calls are counted on the run and in
          the chat cap.
        </p>
        <p>
          The cap defaults to 40 cents per chat and can be edited before the run starts. Hitting it ends that chat and
          closes its tutor session. A separate run cap starts blank, so one chat hitting 40 cents does not cancel the
          others.
        </p>
        <p>
          GPT-6 Luna has no published token price. The page does not invent one. Luna calls show a blank dollar cost.
          The 40 cent cap does not cover them. A token ceiling, shown next to the cap, stops an unpriced loop. The
          ceiling is editable on the New run screen.
        </p>

        <h2>Stored prompts</h2>
        <p>
          Every tutor call stores its prompt. Each harness turn can also store the child prompt that went to the model.
          On a chat, Show both prompts labels the tutor prompt and the child prompt. Trim stored prompts, on the Runs
          tab, keeps prompts for the baseline run
          and the most recent run of each suite. Older runs keep the transcript, the scores, the intents, and the
          recommendations. Trimming does not delete a chat or a score.
        </p>
        <p>
          Each finished chat is also a normal tutor session. In KC View Chats, turn on Show test children to open it,
          including the Debug view of the prompt. Deleting a run removes its test child rows, sessions, messages,
          prompts, usage, and safety events.
        </p>
      </article>
    </main>
  );
}
