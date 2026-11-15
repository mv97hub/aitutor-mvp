"use client";

import { useEffect, useState } from "react";

import { defaultSelectedRunIds, recommendationPageSummary, skippedRunMessage, type DraftMaterials } from "@/lib/harness-draft";
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
    nudges?: { turn?: number; asked?: string; answered?: string; block_type?: string; block_id?: string; substep?: string; run_id?: string }[];
    sources?: { run_id?: string; turn?: number; block_type?: string }[];
    findings?: { tag?: string; title?: string }[];
    block_title?: string;
    substep?: string;
    child_text?: string;
    tutor_reply?: string;
    turn?: number;
    run_id?: string;
    fault?: string;
    mismatch?: string;
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
        body: JSON.stringify({ runs: contexts }),
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
        body: JSON.stringify({ run_id: saveId, replace: true, observations: true, cards: drafted.cards }),
      });
      setViewId(saveId);
      onSelectRun(saveId);
      await load(saveId);
      const named = skippedRunMessage(failures);
      if (named) setError(named);
      setNote("Drafted observations from the selected runs.");
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
          <button type="button" className="harness-draft" disabled={chosen.length === 0 || busy} onClick={() => void draft()}>
            {busy ? "Drafting…" : "Draft from selected"}
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
        Nothing here changes the live tutor prompt, and this page does not edit the prompt builder. Draft from selected writes one observation per turn and fault from the stored transcript. A stored prompt line is quoted as the line that was in force. Accept does not change the live tutor. Try it copies the tutor profile into a hidden trial profile and queues the same slice. You start that run yourself.
      </p>
      {error ? <p className="banner">{error}</p> : null}
      {note ? <p className="help">{note}</p> : null}
      {recent.length === 0 ? (
        <p className="harness-empty">No runs yet. Start a run, then draft cards from the runs you check.</p>
      ) : cards.length === 0 ? (
        <p className="harness-empty">
          No observations yet. The newest runs start checked. Press Draft from selected. The button shows Drafting… while the request runs. One set of observations covers every checked run. Finishing a run does not create them. Drafting does not change the live tutor.
        </p>
      ) : (
        <p className="help">These observations are one set for the selected runs. Accept does not change the live tutor.</p>
      )}
      {summary ? (
        <div className="harness-summary">
          <div className="harness-actions">
            <h3>Observations</h3>
            <button type="button" onClick={() => void copySummary()}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre>{summary}</pre>
        </div>
      ) : null}
      {cards.map((card) => {
        const evidence = card.evidence || {};
        const run = evidence.run_id || evidence.sources?.[0]?.run_id || "unknown";
        const turn = evidence.turn ?? evidence.sources?.[0]?.turn;
        return (
          <article key={card.id} className="harness-card">
            <h3>{card.title}</h3>
            <p>Run: {run}</p>
            <p>Block type: {evidence.block_type || "an unknown block"}</p>
            <p>Block title: {evidence.block_title || "not stored"}</p>
            <p>Substep: {evidence.substep || "not stored"}</p>
            <p>Turn: {turn ?? "unknown"}</p>
            <p>Check: {evidence.findings?.[0]?.tag || "not stored"}</p>
            <p>Child: {evidence.child_text || "not stored"}</p>
            <p>Tutor: {evidence.tutor_reply || "not stored"}</p>
            <p>What was suboptimal: {evidence.fault || evidence.summary || "The stored turn was marked."}</p>
            {evidence.current ? (
              <>
                <p>
                  Line in force
                  {evidence.section || evidence.function
                    ? ` (${[evidence.section, evidence.function].filter(Boolean).join(", ")})`
                    : ""}
                  . This was the line in force on that turn, not a line to change.
                </p>
                <blockquote>{evidence.current}</blockquote>
              </>
            ) : null}
            {evidence.mismatch ? <p>{evidence.mismatch}</p> : null}
            {evidence.nudges && evidence.nudges.length > 0 ? (
              <ul>
                {evidence.nudges.map((nudge, index) => (
                  <li key={`${nudge.turn ?? index}`}>
                    Turn {nudge.turn} on {nudge.block_type || evidence.block_type || "an unknown block"}
                    {nudge.block_id || nudge.substep ? ` (${[nudge.block_id, nudge.substep].filter(Boolean).join(" / ")})` : ""}: the child asked “{nudge.asked}”. The tutor answered “{nudge.answered}”. The step did not move.
                  </li>
                ))}
              </ul>
            ) : null}
            <p>
              {card.status} · {card.confidence}
            </p>
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
