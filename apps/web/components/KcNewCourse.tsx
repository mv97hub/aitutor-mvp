"use client";

import { useEffect, useState } from "react";

import { createKcCourse } from "@/lib/kc-actions";
import { AUDIENCES, KINDS } from "@/lib/kc";

export function KcNewCourse() {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("mastery");

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  function close() {
    setOpen(false);
  }

  return (
    <>
      <button
        type="button"
        className="button studio-new"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          setKind("mastery");
          setOpen(true);
        }}
      >
        New course
      </button>
      {open ? (
        <div className="kc-modal" role="presentation" onMouseDown={close}>
          <div
            className="kc-modal-card kc-new-course"
            role="dialog"
            aria-modal="true"
            aria-labelledby="kc-new-course-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="kc-new-course-head">
              <h2 id="kc-new-course-title">New course</h2>
              <button type="button" className="ghost" onClick={close}>
                Close
              </button>
            </div>
            <form className="studio-new-form" action={createKcCourse}>
              <label>
                Name
                <input aria-label="New course name" name="title" required autoFocus />
              </label>
              <label>
                What the kid should come away able to do
                <textarea aria-label="New course description" name="description" rows={3} />
              </label>
              <label>
                Syllabus or source text
                <textarea
                  aria-label="Syllabus or source text"
                  name="source_text"
                  rows={6}
                  placeholder="Optional. Paste a unit outline or a numbered topic list."
                />
              </label>
              <label>
                Audience
                <select aria-label="New course audience" name="audience" defaultValue="12-14">
                  {AUDIENCES.map((band) => (
                    <option key={band}>{band}</option>
                  ))}
                </select>
              </label>
              <label>
                Kind
                <select
                  aria-label="New course kind"
                  name="kind"
                  value={kind}
                  onChange={(event) => setKind(event.target.value)}
                >
                  {KINDS.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              {kind === "time_boxed" ? (
                <label>
                  Minutes, optional
                  <input aria-label="New course minutes" name="minutes" inputMode="numeric" />
                </label>
              ) : null}
              <div className="rail-actions">
                <button className="button" type="submit">
                  Create course
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );
}
