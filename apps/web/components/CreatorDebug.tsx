"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { mergePromptTurns, type PromptTurn } from "@/lib/kc-prompt-log";

type DebugContextValue = {
  open: boolean;
  toggle: () => void;
};

const DebugContext = createContext<DebugContextValue | null>(null);

export function CreatorDebugShell({
  className,
  scope,
  turn,
  children,
}: {
  className: string;
  scope: string;
  turn: PromptTurn | null;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<PromptTurn[]>([]);
  const turnId = turn?.id ?? "";

  useEffect(() => {
    const store = typeof window === "undefined" ? null : window.sessionStorage;
    setTurns(mergePromptTurns(scope, turn, store));
  }, [scope, turn, turnId]);

  const value = useMemo<DebugContextValue>(
    () => ({
      open,
      toggle: () => setOpen((current) => !current),
    }),
    [open],
  );

  return (
    <DebugContext.Provider value={value}>
      <main className={`${className}${open ? " is-debug" : ""}`}>
        {children}
        {open ? <CreatorPromptPanel turns={turns} /> : null}
      </main>
    </DebugContext.Provider>
  );
}

export function CreatorDebugButton() {
  const debug = useContext(DebugContext);
  const open = debug?.open ?? false;
  return (
    <button
      type="button"
      className="button kc-debug-launch"
      aria-pressed={open}
      aria-expanded={open}
      aria-controls="kc-creator-debug"
      onClick={() => debug?.toggle()}
    >
      Debug
    </button>
  );
}

function CreatorPromptPanel({ turns }: { turns: PromptTurn[] }) {
  const log = useRef<HTMLDivElement>(null);
  const lastId = turns[turns.length - 1]?.id ?? "";

  useEffect(() => {
    const node = log.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [lastId, turns.length]);

  return (
    <aside className="kc-debug" id="kc-creator-debug" aria-label="Prompts">
      <div className="kc-debug-body" ref={log} role="log" aria-label="Prompts sent">
        <p className="kc-debug-layer">Prompts</p>
        {turns.length === 0 ? <p className="ds-quiet">No prompts yet.</p> : null}
        {turns.map((turn, turnIndex) => (
          <article key={turn.id} className="kc-debug-turn">
            <h3>Turn {turnIndex + 1}</h3>
            {turn.prompts.map((item, index) => (
              <div key={`${turn.id}-${index}`}>
                <h4>{item.label}</h4>
                <h5>Instructions</h5>
                <pre className="prompt-pre">{item.instructions}</pre>
                <h5>Prompt</h5>
                <pre className="prompt-pre">{item.prompt}</pre>
              </div>
            ))}
          </article>
        ))}
      </div>
    </aside>
  );
}
