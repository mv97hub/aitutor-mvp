"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { BrandMark } from "@/components/BrandMark";
import { api } from "@/lib/api";
import type { StudioCourse, StudioSummary } from "@/lib/studio";

export function ManageCourses() {
  const [courses, setCourses] = useState<StudioSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<"delete" | "copy" | null>(null);
  const [password, setPassword] = useState("");
  const [copyName, setCopyName] = useState("");
  const [dialogError, setDialogError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await api<StudioSummary[]>("/studio/courses");
        if (!cancelled) setCourses(rows);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "The studio service is not reachable.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = courses.find((row) => row.id === selectedId) ?? null;

  function closeDialog() {
    setDialog(null);
    setDialogError(null);
    setPassword("");
    setCopyName("");
  }

  async function refresh(nextSelected: string | null) {
    const rows = await api<StudioSummary[]>("/studio/courses");
    setCourses(rows);
    setSelectedId(nextSelected);
  }

  async function submitDelete(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setDialogError(null);
    try {
      await api(`/studio/courses/${selected.id}/delete`, {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      await refresh(null);
      closeDialog();
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : "The password is wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function submitCopy(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setDialogError(null);
    try {
      const created = await api<StudioCourse>(`/studio/courses/${selected.id}/copy`, {
        method: "POST",
        body: JSON.stringify({ title: copyName.trim() }),
      });
      await refresh(created.id);
      closeDialog();
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : "Could not copy that course.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="ds-shell studio-shell">
      <aside className="ds-side">
        <div className="ds-logo">
          <BrandMark />
        </div>
        <p className="ds-learner">Manage courses</p>
        <Link href="/create-course" className="studio-manage-link">Create course</Link>
      </aside>
      <section className="studio-manage">
        <h1>Manage courses</h1>
        {selected ? (
          <div className="studio-manage-actions">
            <p>
              <span className="studio-code">{selected.code}</span>
              {selected.title}
            </p>
            <button
              type="button"
              className="danger"
              disabled={busy}
              onClick={() => {
                setPassword("");
                setDialogError(null);
                setDialog("delete");
              }}
            >
              Delete
            </button>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => {
                setCopyName("");
                setDialogError(null);
                setDialog("copy");
              }}
            >
              Copy
            </button>
          </div>
        ) : (
          <p className="ds-quiet">Choose a course.</p>
        )}
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <ul className="studio-manage-list" aria-label="Studio courses">
          {courses.length === 0 ? <li className="ds-quiet">No saved courses</li> : null}
          {courses.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                className={`ds-row${row.id === selectedId ? " is-on" : ""}`}
                aria-current={row.id === selectedId ? "true" : undefined}
                onClick={() => setSelectedId(row.id)}
              >
                <strong>{row.title}</strong>
                <small>{row.code}</small>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {dialog === "delete" && selected ? (
        <div className="prompt-backdrop" role="presentation" onMouseDown={closeDialog}>
          <div
            className="prompt-dialog settings-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="manage-delete-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <h2 id="manage-delete-title">Delete {selected.title}</h2>
                <p>This removes the studio course and its creation chat.</p>
              </div>
              <button type="button" className="ghost" onClick={closeDialog}>Close</button>
            </header>
            <form className="prompt-body" onSubmit={(event) => void submitDelete(event)}>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  autoComplete="off"
                  autoFocus
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              {dialogError ? (
                <div className="banner" role="alert">
                  <p>{dialogError}</p>
                </div>
              ) : null}
              <div className="rail-actions">
                <button className="danger" type="submit" disabled={busy}>Delete</button>
                <button type="button" className="ghost" onClick={closeDialog}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
      {dialog === "copy" && selected ? (
        <div className="prompt-backdrop" role="presentation" onMouseDown={closeDialog}>
          <div
            className="prompt-dialog settings-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="manage-copy-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <h2 id="manage-copy-title">Copy {selected.title}</h2>
                <p>The new course gets a new code and this name. The creation chat stays behind.</p>
              </div>
              <button type="button" className="ghost" onClick={closeDialog}>Close</button>
            </header>
            <form className="prompt-body" onSubmit={(event) => void submitCopy(event)}>
              <label>
                New name
                <input
                  value={copyName}
                  maxLength={240}
                  required
                  autoFocus
                  onChange={(event) => setCopyName(event.target.value)}
                />
              </label>
              {dialogError ? (
                <div className="banner" role="alert">
                  <p>{dialogError}</p>
                </div>
              ) : null}
              <div className="rail-actions">
                <button className="button" type="submit" disabled={busy}>Copy</button>
                <button type="button" className="ghost" onClick={closeDialog}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </main>
  );
}
