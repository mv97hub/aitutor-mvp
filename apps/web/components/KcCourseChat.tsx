"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { useCreatorDebug } from "@/components/CreatorDebug";
import type { KcPipeline } from "@/lib/kc";
import { promptTurnId } from "@/lib/kc-prompt-log";

type ChatMessage = { role: "user" | "assistant"; content: string };

type Proposal = {
  reply: string;
  changes: string[];
  proposal: unknown;
  instructions: string;
  prompt: string;
};

/** Ad-hoc edits for the course the wizard already made. Nothing changes until Apply. */
export function KcCourseChat({
  courseId,
  model,
  pipeline,
}: {
  courseId: string;
  model: string;
  pipeline: KcPipeline;
}) {
  const debug = useCreatorDebug();
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Proposal | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || busy) return;
    const history = [...messages, { role: "user" as const, content }];
    setMessages(history);
    setDraft("");
    setPending(null);
    setError(null);
    setBusy(true);
    try {
      const response = await fetch("/api/kc/course-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "chat", course_id: courseId, model, messages: history }),
      });
      const body = (await response.json()) as Proposal & { error?: string };
      if (body.instructions && body.prompt) {
        debug?.record({
          id: promptTurnId([courseId, "Course chat", body.instructions, body.prompt]),
          prompts: [{ label: "Course chat", instructions: body.instructions, prompt: body.prompt }],
        });
      }
      if (!response.ok) throw new Error(body.error || "The chat did not answer.");
      setMessages([...history, { role: "assistant", content: body.reply }]);
      setPending(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The chat did not answer.");
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    if (!pending || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/kc/course-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "chat-apply", course_id: courseId, proposal: pending.proposal }),
      });
      const body = (await response.json()) as { error?: string };
      if (!response.ok) throw new Error(body.error || "The change was not applied.");
      setPending(null);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The change was not applied.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="kc-chat">
      <section aria-label="This course">
        <p className="kc-brief">
          <strong>Brief. </strong>
          {pipeline.brief || "No brief yet."}
        </p>
        <p className="ds-quiet">
          {pipeline.standards.length
            ? `${pipeline.standards.length} curriculum statements.`
            : "No curriculum statements yet."}
        </p>
        {pipeline.blueprint ? (
          <ol aria-label="Blueprint units">
            {pipeline.blueprint.units.map((unit) => (
              <li key={`${unit.title}-${unit.components.map((item) => item.code).join(",")}`}>
                <strong>{unit.title}</strong>
                <span className="ds-quiet"> {unit.components.map((item) => item.title).join(", ")}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="ds-quiet">No blueprint yet. Ask for one.</p>
        )}
      </section>
      <div className="kc-chat-log" aria-label="Course chat">
        {messages.map((message, index) => (
          <p key={`${message.role}-${index}`} className={message.role === "user" ? "kc-chat-user" : "kc-chat-editor"}>
            <strong>{message.role === "user" ? "You. " : "Editor. "}</strong>
            {message.content}
          </p>
        ))}
        {busy ? <p className="ds-typing">Working…</p> : null}
      </div>
      {error ? (
        <div className="banner" role="alert">
          <p>{error}</p>
        </div>
      ) : null}
      {pending ? (
        <section className="kc-confirm" aria-label="Proposed change">
          <p>{pending.reply}</p>
          {pending.changes.length ? (
            <ul>
              {pending.changes.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : (
            <p className="ds-quiet">Nothing in the course would change.</p>
          )}
          <div className="kc-pipeline-actions">
            <button className="button" type="button" disabled={busy || pending.changes.length === 0} onClick={() => void apply()}>
              Apply
            </button>
            <button className="ghost" type="button" disabled={busy} onClick={() => setPending(null)}>
              Decline
            </button>
          </div>
        </section>
      ) : null}
      <form className="kc-questions" onSubmit={(event) => void send(event)}>
        <label>
          Change to propose
          <textarea
            aria-label="Course chat message"
            rows={3}
            value={draft}
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="For example: delete unit 2"
          />
        </label>
        <button className="button" type="submit" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
