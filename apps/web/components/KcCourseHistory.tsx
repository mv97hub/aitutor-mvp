"use client";

import { useId, useState } from "react";

export function KcCourseHistory({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <section className="kc-history kc-history-fold">
      <div className="kc-history-row">
        <h3>Course history</h3>
        <button
          type="button"
          className="ghost kc-history-toggle"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Hide log" : "Show log"}
        </button>
      </div>
      <pre id={panelId} aria-label="Course history" hidden={!open}>{text.trim() ? text : "No history yet."}</pre>
    </section>
  );
}
