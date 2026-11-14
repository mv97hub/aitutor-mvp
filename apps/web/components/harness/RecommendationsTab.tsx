"use client";

import { useEffect, useState } from "react";

import { HARNESS_MODELS } from "@/lib/harness";
import { defaultSelectedRunIds, recommendationPageSummary, skippedRunMessage, type DraftMaterials } from "@/lib/harness-draft";
import { kcModelLabel } from "@/lib/kc-models";
import { api } from "@/lib/api";

type Card = {
  id: string;
  title: string;
  kind: string;
  prompt_direction: string;
  cause_class: string;
  place: string;
  risk: string;
  confidence: string;
  status: string;
  evidence: {
    summary?: string;
    block_type?: string;
    section?: string;
    function?: string;
    symbol?: string;
    current?: string;
    replacement?: string;
    shorter?: string;
    nudges?: { turn?: number; asked?: string; answered?: string; block_type?: string; block_id?: string; substep?: string; run_id?: string }[];
    sources?: { run_id?: string; turn?: number; block_type?: string }[];
    findings?: { tag?: string; title?: string }[];
  };
  proposed: { text?: string; shorter?: string };
  trial_profile_id?: string | null;
};

type RunRow = { id: string; status?: string; created_at?: string };

export function RecommendationsTab({
  runId,
  onSelectRun,
}: {
  runId: string;
  onSelectRun: (runId: string) => void;
}) {
  const [cards, setCards] = useState<Card[]>([]);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [picked, setPicked] = useState<string[] | null>(null);
  const [viewId, setViewId] = useState("");
  const [model, setModel] = useState("gpt-6.1-sol");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const recent = runs.slice(0, 8);
  const chosen = (picked ?? defaultSelectedRunIds(recent.map((run) => run.id))).filter((id) => recent.some((run) => run.id === id));
  const activeId = viewId || recent[0]?.id || "";
  const summary = cards.length > 0 ? recommendationPageSummary(cards) : "";

  async function load(id = activeId) {
    if (!id) {
      setCards([]);
      return;
    }
    const body = await api<unknown>(`/kc/harness/recommendations?run_id=${id}`);
    setCards(Array.isArray(body) ? (body as Card[]) : []);
    if (!Array.isArray(body)) setError("Recommendations did not come back as a list.");
  }

  useEffect(() => {
    let stop = false;
    void api<unknown>("/kc/harness/runs")
      .then((body) => {
        if (stop || !Array.isArray(body)) return;
        setRuns(body as RunRow[]);
      })
      .catch((err) => {
        if (!stop) setError(err instanceof Error ? err.message : "Could not load runs.");
      });
    return () => {
      stop = true;
    };
  }, []);

  useEffect(() => {
    const first = runs[0]?.id;
    if (!first || viewId) return;
    setViewId(first);
    if (!runId || !runs.some((run) => run.id === runId)) onSelectRun(first);
  }, [runs, viewId, runId, onSelectRun]);

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : "Could not load recommendations."));
  }, [activeId]);

  useEffect(() => {
    setCopied(false);
  }, [summary]);

  function toggleRun(id: string) {
    const current = picked ?? defaultSelectedRunIds(recent.map((run) => run.id));
    setPicked(current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  async function draft() {
    if (chosen.length === 0 || busy) return;
    setBusy(true);
    setError("");
    setNote("");
    const contexts: DraftMaterials[] = [];
    const failures: { runId: string; message: string }[] = [];
    try {
      for (const id of chosen) {
        try {
          const context = await api<DraftMaterials>(`/kc/harness/runs/${id}/draft-context`);
          contexts.push({ ...context, run_id: context.run_id || id });
        } catch (err) {
          failures.push({ runId: id, message: err instanceof Error ? err.message : "Could not read this run." });
        }
      }
      if (contexts.length === 0) {
        throw new Error(skippedRunMessage(failures) || "Select a run to draft.");
      }
      const response = await fetch("/api/kc/harness/recommend", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ model, runs: contexts }),
      });
      if (!response.ok) {
        const text = (await response.text()) || "Could not draft cards.";
        const named = skippedRunMessage(failures);
        throw new Error(named ? `${text} ${named}` : text);
      }
      const drafted = await response.json();
      const saveId = String(contexts[0]?.run_id || chosen[0]);
      await api("/kc/harness/recommendations", {
        method: "POST",
        body: JSON.stringify({ run_id: saveId, replace: true, cards: drafted.cards }),
      });
      setViewId(saveId);
      onSelectRun(saveId);
      await load(saveId);
      const named = skippedRunMessage(failures);
      if (named) setError(named);
      setNote(
        drafted.drafter && drafted.drafter !== "prompt-builder"
          ? "Drafted one set of cards from the selected runs. The model rewrote the shorter lines."
          : "Drafted one set of cards from the selected runs.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not draft cards.");
    } finally {
      setBusy(false);
    }
  }

  async function copySummary() {
    if (!summary) return;
    try {
      await navigator.clipboard.writeText(summary);
      setCopied(true);
    } catch (err) {
      setCopied(false);
      setError(err instanceof Error ? err.message : "Could not copy the summary.");
    }
  }

  async function setStatus(card: Card, status: string) {
    await api(`/kc/harness/recommendations/${card.id}`, { method: "PATCH", body: JSON.stringify({ status }) });
    await load();
  }

  async function tryIt(card: Card) {
    setError("");
    try {
      const trial = await api<{ plan: Record<string, unknown>; trial_profile_id: string }>(
        `/kc/harness/recommendations/${card.id}/trial`,
        { method: "POST" },
      );
      if (trial.plan && Object.keys(trial.plan).length > 0) {
        await api("/kc/harness/runs", { method: "POST", body: JSON.stringify(trial.plan) });
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not prepare a trial. Wording changes are tried on a branch, not from this page.");
    }
  }

  async function saveSuite() {
    const name = window.prompt("Suite name");
    if (!name) return;
    await api("/kc/harness/suites", { method: "POST", body: JSON.stringify({ name, run_id: activeId }) });
  }

  async function markBaseline() {
    const suiteId = window.prompt("Suite id");
    if (!suiteId) return;
    await api(`/kc/harness/suites/${suiteId}/baseline`, { method: "POST", body: JSON.stringify({ run_id: activeId }) });
  }

  return (
    <section className="harness-panel">
      <header className="harness-panel-head">
        <h2>Recommendations</h2>
        <div className="harness-actions">
          <select aria-label="Drafter model" value={model} onChange={(event) => setModel(event.target.value)}>
            {HARNESS_MODELS.map((item) => (
              <option key={item} value={item}>
                {kcModelLabel(item)}
              </option>
            ))}
          </select>
          <button type="button" className="harness-draft" disabled={chosen.length === 0 || busy} onClick={() => void draft()}>
            {busy ? "Drafting cards…" : "Draft from selected"}
          </button>
          <button type="button" disabled={!activeId || busy} onClick={() => void saveSuite()}>
            Save as suite
          </button>
          <button type="button" disabled={!activeId || busy} onClick={() => void markBaseline()}>
            Mark baseline
          </button>
        </div>
      </header>
      {recent.length > 0 ? (
        <fieldset>
          <legend>Recent runs</legend>
          <ul className="harness-run-picks">
            {recent.map((run) => (
              <li key={run.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={chosen.includes(run.id)}
                    onChange={() => toggleRun(run.id)}
                  />
                  <span>
                    {run.status || "run"} · {(run.created_at || "").slice(0, 16).replace("T", " ")} · {run.id}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
      ) : null}
      <p className="help">
        Nothing here changes the live prompt. Each card names the prompt-builder section and function, quotes the current sentences from the stored tutor prompt, and gives a replacement, including a shorter or removed line. Accepting a setting does not apply it. Try it copies the tutor profile into a hidden trial profile and queues the same slice. You start that run yourself.
      </p>
      {error ? <p className="banner">{error}</p> : null}
      {note ? <p className="help">{note}</p> : null}
      {recent.length === 0 ? (
        <p className="harness-empty">No runs yet. Start a run, then draft cards from the runs you check.</p>
      ) : cards.length === 0 ? (
        <p className="harness-empty">
          No cards yet. The newest runs start checked. Press Draft from selected. The button shows Drafting cards… while the request runs. One set of cards covers every checked run. Finishing a run does not create cards. Drafting does not change the live tutor.
        </p>
      ) : (
        <p className="help">These cards are one set for the selected runs. Accept does not change the live tutor.</p>
      )}
      {summary ? (
        <div className="harness-summary">
          <div className="harness-actions">
            <h3>Draft summary</h3>
            <button type="button" onClick={() => void copySummary()}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre>{summary}</pre>
        </div>
      ) : null}
      {cards.map((card) => {
        const evidence = card.evidence || {};
        const replacement = evidence.replacement || card.proposed?.text || "";
        const shorter = evidence.shorter || card.proposed?.shorter || "";
        return (
          <article key={card.id} className="harness-card">
            <h3>{card.title}</h3>
            <p>Block type: {evidence.block_type || "an unknown block"}</p>
            {evidence.findings && evidence.findings.length > 0 ? (
              <p>Findings: {evidence.findings.map((finding) => finding.title || finding.tag).filter(Boolean).join("; ")}</p>
            ) : null}
            {evidence.sources && evidence.sources.length > 0 ? (
              <ul>
                {evidence.sources.map((source, index) => (
                  <li key={`${source.run_id ?? "run"}-${source.turn ?? index}`}>
                    Run {source.run_id || "unknown"} · turn {source.turn ?? "—"} · {source.block_type || evidence.block_type || "an unknown block"}
                  </li>
                ))}
              </ul>
            ) : null}
            <p>
              Section: {evidence.section || "—"}. Function: {evidence.function || "—"}
              {evidence.symbol && evidence.symbol !== evidence.function ? ` (${evidence.symbol})` : ""}
            </p>
            <p>
              {card.kind} · prompt gets {card.prompt_direction} · {card.status} · {card.confidence}
            </p>
            <p>{evidence.summary}</p>
            {evidence.nudges && evidence.nudges.length > 0 ? (
              <ul>
                {evidence.nudges.map((nudge, index) => (
                  <li key={`${nudge.turn ?? index}`}>
                    {nudge.run_id ? `Run ${nudge.run_id}. ` : ""}Turn {nudge.turn} on {nudge.block_type || evidence.block_type || "an unknown block"}
                    {nudge.block_id || nudge.substep ? ` (${[nudge.block_id, nudge.substep].filter(Boolean).join(" / ")})` : ""}: the child asked “{nudge.asked}”. The tutor answered “{nudge.answered}”. The block did not move.
                  </li>
                ))}
              </ul>
            ) : null}
            <p>
              <strong>Current sentences</strong>
            </p>
            <blockquote>{evidence.current || "The stored prompt had no sentence for this card."}</blockquote>
            <p>
              <strong>Replacement.</strong> {replacement}
            </p>
            {shorter ? (
              <p>
                <strong>Shorter or removed.</strong> {shorter}
              </p>
            ) : null}
            <p>
              <strong>{card.cause_class}.</strong> {card.place}
            </p>
            <p>Risk: {card.risk}</p>
            <div className="harness-actions">
              <button type="button" onClick={() => void setStatus(card, "accepted")}>
                Accept
              </button>
              <button type="button" onClick={() => void setStatus(card, "rejected")}>
                Reject
              </button>
              <button type="button" onClick={() => void tryIt(card)}>
                Try it
              </button>
            </div>
          </article>
        );
      })}
    </section>
  );
}
