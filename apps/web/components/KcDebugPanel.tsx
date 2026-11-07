"use client";

import { useEffect, useRef, useState } from "react";

import type { KcDebugTurn } from "@/lib/kc-debug";
import type { KcDebugVariable } from "@/lib/kc";

function when(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function messageRole(message: unknown) {
  if (message && typeof message === "object" && "role" in message && typeof message.role === "string") {
    return message.role;
  }
  return "message";
}

function messageBody(message: unknown) {
  const content =
    message && typeof message === "object" && "content" in message
      ? (message as { content: unknown }).content
      : message;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "text" in part && typeof part.text === "string") return part.text;
        return JSON.stringify(part, null, 2);
      })
      .join("\n");
  }
  return JSON.stringify(content, null, 2);
}

function isRequestNote(message: unknown) {
  return messageRole(message) === "request";
}

export function KcDebugPanel({
  variables,
  turns,
}: {
  variables: KcDebugVariable[];
  turns: KcDebugTurn[];
}) {
  const [tab, setTab] = useState<"variables" | "prompts">("variables");
  const log = useRef<HTMLDivElement>(null);
  const lastId = turns[turns.length - 1]?.id ?? "";

  useEffect(() => {
    const node = log.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [lastId, tab]);

  return (
    <aside className="kc-debug" id="kc-debug-panel" aria-label="Debug">
      <div className="kc-debug-switch" role="group" aria-label="Debug views">
        <button type="button" aria-pressed={tab === "variables"} onClick={() => setTab("variables")}>
          Variables
        </button>
        <button type="button" aria-pressed={tab === "prompts"} onClick={() => setTab("prompts")}>
          Prompts
        </button>
      </div>
      {tab === "variables" ? (
        <div className="kc-debug-body">
          <dl className="kc-debug-vars">
            {variables.map((item) => (
              <div key={item.name}>
                <dt>{item.name}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : (
        <div className="kc-debug-body" ref={log} role="log" aria-label="Model calls">
          {turns.length === 0 ? <p className="ds-quiet">No model calls yet.</p> : null}
          {turns.map((turn) => {
            const messages = turn.messages.filter((message) => !isRequestNote(message));
            const notes = turn.messages.filter(isRequestNote);
            return (
              <article key={turn.id} className="kc-debug-turn">
                <h3>Turn {turn.seq}</h3>
                <p className="meta">
                  {turn.model || "Model"}
                  {turn.created_at ? ` · ${when(turn.created_at)}` : ""}
                </p>
                <h4>Request</h4>
                <h5>System prompt</h5>
                <pre className="prompt-pre">{turn.system_prompt}</pre>
                <h5>Messages sent to the model</h5>
                {messages.length === 0 ? <p className="ds-quiet">No messages were attached to this call.</p> : null}
                <ol className="prompt-messages">
                  {messages.map((message, index) => (
                    <li key={`${turn.id}-${index}`}>
                      <strong>{messageRole(message)}</strong>
                      <pre className="prompt-pre">{messageBody(message)}</pre>
                    </li>
                  ))}
                </ol>
                {notes.map((message, index) => (
                  <div key={`${turn.id}-request-${index}`}>
                    <h5>Also sent to the model</h5>
                    <pre className="prompt-pre">{messageBody(message)}</pre>
                  </div>
                ))}
                <h4>Response</h4>
                <pre className="prompt-pre">{turn.response}</pre>
              </article>
            );
          })}
        </div>
      )}
    </aside>
  );
}
