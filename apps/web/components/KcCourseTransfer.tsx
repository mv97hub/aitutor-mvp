"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type Preview = {
  title: string;
  partial: boolean;
  component_count: number;
  block_count: number;
  units: { title: string; components: number; blocks: number }[];
  standards: { code: string; text: string }[];
};

/** Import, export, and the external prompt. One button, not a third mode. */
export function KcCourseTransfer({
  courseId,
  title,
  audience,
  curriculum,
}: {
  courseId: string;
  title: string;
  audience: string;
  curriculum: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [grade, setGrade] = useState("");
  const [syllabus, setSyllabus] = useState(curriculum);
  const [notes, setNotes] = useState("");
  const [prompt, setPrompt] = useState("");
  const [raw, setRaw] = useState("");
  const [mode, setMode] = useState<"merge" | "replace">("merge");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  async function post(body: Record<string, unknown>) {
    const response = await fetch("/api/kc/course-file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ course_id: courseId, ...body }),
    });
    const payload = (await response.json()) as { error?: string };
    if (!response.ok) throw new Error(payload.error || "That did not work.");
    return payload;
  }

  async function download() {
    setBusy(true);
    setError(null);
    try {
      const file = await post({ action: "export" });
      const blob = new Blob([JSON.stringify(file, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${title.replace(/\s+/g, "-").toLowerCase() || "course"}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The export failed.");
    } finally {
      setBusy(false);
    }
  }

  async function buildPrompt() {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const result = (await post({
        action: "prompt",
        title,
        grade,
        audience,
        curriculum: syllabus,
        block_notes: notes,
      })) as { prompt?: string };
      const text = result.prompt || "";
      setPrompt(text);
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        setCopied(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "The prompt was not built.");
    } finally {
      setBusy(false);
    }
  }

  async function readFile(file: File | undefined) {
    if (!file) return;
    setRaw(await file.text());
    setPreview(null);
  }

  async function look() {
    setBusy(true);
    setError(null);
    setPreview(null);
    try {
      const document = JSON.parse(raw) as unknown;
      const result = (await post({ action: "preview", document })) as Preview;
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That file could not be read.");
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    setBusy(true);
    setError(null);
    try {
      const document = JSON.parse(raw) as unknown;
      await post({ action: "import", document, mode });
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That file did not import.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button className="ghost" type="button" onClick={() => setOpen(true)}>
        Import / Export
      </button>
      {open ? (
        <div className="kc-modal" role="presentation">
          <div className="kc-modal-card" role="dialog" aria-modal="true" aria-label="Import or export">
            <div className="kc-actions">
              <h2>Import / Export</h2>
              <button className="ghost" type="button" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>
            {error ? (
              <div className="banner" role="alert">
                <p>{error}</p>
              </div>
            ) : null}
            <div className="kc-pipeline-actions">
              <button className="button" type="button" disabled={busy} onClick={() => void download()}>
                Export course JSON
              </button>
            </div>
            <section className="kc-questions" aria-label="External prompt">
              <h3>Copy prompt for an external model</h3>
              <label>
                Grade or year
                <input aria-label="External prompt grade" value={grade} onChange={(event) => setGrade(event.target.value)} />
              </label>
              <label>
                Curriculum or syllabus
                <textarea
                  aria-label="External prompt curriculum"
                  rows={6}
                  value={syllabus}
                  onChange={(event) => setSyllabus(event.target.value)}
                />
              </label>
              <label>
                Block preferences
                <textarea
                  aria-label="Block preferences"
                  rows={2}
                  value={notes}
                  placeholder="Every component includes an explanation, a worked example, a topic goal, and two MCQs."
                  onChange={(event) => setNotes(event.target.value)}
                />
              </label>
              <button className="ghost" type="button" disabled={busy} onClick={() => void buildPrompt()}>
                {copied ? "Copied" : "Copy prompt for external LLM"}
              </button>
              {prompt ? (
                <textarea aria-label="External prompt" readOnly rows={8} value={prompt} />
              ) : null}
            </section>
            <section className="kc-questions" aria-label="Import course">
              <h3>Import</h3>
              <label>
                Course JSON
                <textarea
                  aria-label="Course JSON"
                  rows={6}
                  value={raw}
                  onChange={(event) => {
                    setRaw(event.target.value);
                    setPreview(null);
                  }}
                />
              </label>
              <label>
                JSON file
                <input
                  aria-label="Course JSON file"
                  type="file"
                  accept="application/json,.json"
                  onChange={(event) => void readFile(event.target.files?.[0])}
                />
              </label>
              <label>
                When the course already has work
                <select aria-label="Import mode" value={mode} onChange={(event) => setMode(event.target.value as "merge" | "replace")}>
                  <option value="merge">Merge</option>
                  <option value="replace">Replace</option>
                </select>
              </label>
              <div className="kc-pipeline-actions">
                <button className="ghost" type="button" disabled={busy || !raw.trim()} onClick={() => void look()}>
                  Preview
                </button>
                <button className="button" type="button" disabled={busy || !preview} onClick={() => void commit()}>
                  Import course
                </button>
              </div>
              {preview ? (
                <div aria-label="Import preview">
                  <p>
                    {preview.component_count} components, {preview.block_count} blocks
                    {preview.standards.length ? `, ${preview.standards.length} statements` : ""}.
                    {preview.partial ? " This file is one unit and will merge." : ""}
                  </p>
                  <ul>
                    {preview.units.map((unit) => (
                      <li key={unit.title}>
                        {unit.title}: {unit.components} components, {unit.blocks} blocks
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
          </div>
        </div>
      ) : null}
    </>
  );
}
