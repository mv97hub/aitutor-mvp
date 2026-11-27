import Link from "next/link";

export const metadata = { title: "Harness agent · Documentation · AI Tutor" };

export default function HarnessAgentDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>Harness agent</h1>
        <p>
          Three calls start a test-child run, read it until it is finished or stopped, and download the bundle. They do
          not use the <Link href="/kc-test-children">AI Test Children</Link> page, and they do not use a browser
          session. The run is the same harness: the server loop keeps going after the create call returns.
        </p>
        <p>
          Send <code>Authorization: Bearer &lt;token&gt;</code> on every call. The token is the{" "}
          <code>HARNESS_SERVICE_TOKEN</code> value on the Next.js server. A missing token is 401. If the server has no
          token configured, the call is 503.
        </p>
        <p>
          Each child is run once on every component of each course. A chat still stops at 40 cents on its own.{" "}
          <code>cost_limit</code> is the cap for the whole run, in cents. The recommended concurrency is 4. The runner
          will not go above 8.
        </p>

        <h2>1. Create and start</h2>
        <p>
          <code>POST /api/kc/harness/agent/runs</code>
        </p>
        <p>
          Required fields are <code>courses</code>, <code>child_profiles</code>, <code>tutor_model</code>,{" "}
          <code>child_model</code>, <code>turn_limit</code>, <code>cost_limit</code>, and <code>stuck_limit</code>.
          Optional fields: concurrency, judge_model. Leave concurrency out to use 4. Leave judge_model out to use
          gpt-6.1-sol. A request that omits a required field is rejected, and the detail names the optional fields.
        </p>
        <p>
          <code>courses</code> is a list of ready courses. Each entry is an id, a code, or a title.{" "}
          <code>child_profiles</code> is <code>&quot;starter&quot;</code> or a list of test-child names or numbers, such
          as <code>[&quot;AI_Child1&quot;, 13]</code>. The starter set is created when it is not stored yet.{" "}
          <code>tutor_model</code> and <code>child_model</code> are tutor models. <code>turn_limit</code> is the child
          turns for one chat. <code>cost_limit</code> is a whole number of cents for the run. <code>stuck_limit</code>{" "}
          is how many turns without movement stop a chat. <code>concurrency</code> is a whole number from 1 to 8.
        </p>
        <pre>{`POST /api/kc/harness/agent/runs
Authorization: Bearer <token>
Content-Type: application/json

{
  "courses": ["Costs of Inflation", "River roads"],
  "child_profiles": ["AI_Child1", "AI_Child13"],
  "tutor_model": "gpt-4.1",
  "child_model": "gpt-4.1-mini",
  "turn_limit": 40,
  "cost_limit": 400,
  "stuck_limit": 8,
  "concurrency": 4
}`}</pre>
        <p>A started run returns 201 and the run id. Keep that id for the next two calls.</p>
        <pre>{`{
  "id": "6f1c0b2e-4a7d-4e1a-9c3b-8a0e5d2f7b11"
}`}</pre>
        <p>
          422 means the course or a child could not be used. The detail says which one. If the run is saved but the
          loop does not start, the response is an error and still includes <code>id</code>.
        </p>

        <h2>2. Read until finished or stopped</h2>
        <p>
          <code>{"GET /api/kc/harness/agent/runs/{id}"}</code>
        </p>
        <p>
          Call it again while <code>status</code> is <code>queued</code>, <code>running</code>, or <code>paused</code>.
          Stop when it is <code>finished</code> or <code>stopped</code>. A run that hits the turn limit, the cost
          limit, or the stuck limit is <code>stopped</code>. It is not <code>finished</code>, and it is not{" "}
          <code>completed</code>.
        </p>
        <pre>{`GET /api/kc/harness/agent/runs/6f1c0b2e-4a7d-4e1a-9c3b-8a0e5d2f7b11
Authorization: Bearer <token>`}</pre>
        <p>
          While the run is still going, <code>file</code> is absent. A child that has not finished has an unfinished
          outcome and a blank stop reason.
        </p>
        <pre>{`{
  "id": "6f1c0b2e-4a7d-4e1a-9c3b-8a0e5d2f7b11",
  "status": "running",
  "stop_reason": "",
  "children": [
    {
      "child": "AI_Child1",
      "outcome": "unfinished",
      "block_verdicts": "",
      "stop_reason": "",
      "cost": ""
    }
  ]
}`}</pre>
        <p>
          A finished run includes <code>file</code>. That file is one CSV, with one row per child: outcome, block
          verdicts, stop reason, and cost. Outcome is the component verdict (<code>known</code>, <code>fragile</code>,{" "}
          <code>unassessed</code>) or <code>unfinished</code>. Block verdicts use the same labels as the download.
          Several components for one child stay on that child&apos;s row. Cost is dollars, or blank when the call was
          not priced.
        </p>
        <pre>{`{
  "id": "6f1c0b2e-4a7d-4e1a-9c3b-8a0e5d2f7b11",
  "status": "finished",
  "stop_reason": "",
  "children": [
    {
      "child": "AI_Child1",
      "outcome": "known",
      "block_verdicts": "Recall: passed; Practice: fragile",
      "stop_reason": "completed",
      "cost": "0.18"
    }
  ],
  "file": "child,outcome,block_verdicts,stop_reason,cost\\nAI_Child1,known,Recall: passed; Practice: fragile,completed,0.18\\n"
}`}</pre>
        <p>
          <code>stop_reason</code> on the run is <code>turn_limit</code>, <code>cost_limit</code>, <code>cancelled</code>,
          or another stored reason. <code>cost_limit</code> covers the run cap, a chat&apos;s 40 cent cap, and the Luna
          token ceiling. The child&apos;s own <code>stop_reason</code> stays specific (<code>cap</code>,{" "}
          <code>run_cap</code>, <code>luna_ceiling</code>, <code>turn_limit</code>, <code>completed</code>).
        </p>
        <pre>{`{
  "id": "6f1c0b2e-4a7d-4e1a-9c3b-8a0e5d2f7b11",
  "status": "stopped",
  "stop_reason": "turn_limit",
  "children": [
    {
      "child": "AI_Child1",
      "outcome": "unfinished",
      "block_verdicts": "Recall: passed",
      "stop_reason": "turn_limit",
      "cost": "0.10"
    }
  ],
  "file": "child,outcome,block_verdicts,stop_reason,cost\\nAI_Child1,unfinished,Recall: passed,turn_limit,0.10\\n"
}`}</pre>

        <h2>3. Download the bundle</h2>
        <p>
          <code>{"GET /api/kc/harness/agent/runs/{id}/download"}</code>
        </p>
        <p>
          This is the same markdown file as Download on the Runs tab. One file for the run: every turn, the automatic
          checks, the judge scores, the block outcomes, and the model record. A blank or failed tutor call stays in the
          file. Save it after the read says <code>finished</code> or <code>stopped</code>.
        </p>
        <pre>{`GET /api/kc/harness/agent/runs/6f1c0b2e-4a7d-4e1a-9c3b-8a0e5d2f7b11/download
Authorization: Bearer <token>`}</pre>
        <p>
          The response is <code>text/markdown</code> with{" "}
          <code>Content-Disposition: attachment; filename=&quot;harness-run-&lt;id&gt;.md&quot;</code>. The body starts
          with the run id, the commit, and the stored status, then one section per child.
        </p>
      </article>
    </main>
  );
}
