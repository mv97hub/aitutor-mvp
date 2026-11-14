"use client";

import { useEffect, useState } from "react";

import { HARNESS_MODELS } from "@/lib/harness";
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
  const [model, setModel] = useState("gpt-6.1-sol");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const listed = runs.some((run) => run.id === runId);
  const activeId = (listed ? runId : "") || runs[0]?.id || "";

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
        const next = body as RunRow[];
        setRuns(next);
        const ids = next.map((run) => run.id);
        if (next[0]?.id && (!runId || !ids.includes(runId))) onSelectRun(next[0].id);
      })
      .catch((err) => {
        if (!stop) setError(err instanceof Error ? err.message : "Could not load runs.");
      });
    return () => {
      stop = true;
    };
  }, [runId, onSelectRun]);

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : "Could not load recommendations."));
  }, [activeId]);

  async function draft() {
    if (!activeId || busy) return;
    setBusy(true);
    setError("");
    setNote("");
    try {
      const context = await api<Record<string, unknown>>(`/kc/harness/runs/${activeId}/draft-context`);
      const response = await fetch("/api/kc/harness/recommend", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ model, run_id: activeId, ...context }),
      });
      if (!response.ok) throw new Error(await response.text());
      const drafted = await response.json();
      await api("/kc/harness/recommendations", {
        method: "POST",
        body: JSON.stringify({ run_id: activeId, cards: drafted.cards }),
      });
      await load(activeId);
      setNote(
        drafted.drafter && drafted.drafter !== "prompt-builder"
          ? "Drafted from the stored prompt and the prompt builder. The model rewrote the shorter lines."
          : "Drafted from the stored prompt and the prompt builder.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not draft cards.");
    } finally {
      setBusy(false);
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
          <select
            aria-label="Run"
            value={activeId}
            onChange={(event) => onSelectRun(event.target.value)}
            disabled={runs.length === 0 && !activeId}
          >
            {!activeId ? <option value="">No runs yet</option> : null}
            {activeId && !runs.some((run) => run.id === activeId) ? (
              <option value={activeId}>selected · {activeId.slice(0, 8)}</option>
            ) : null}
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {run.status || "run"} · {(run.created_at || "").slice(0, 16).replace("T", " ")} · {run.id.slice(0, 8)}
              </option>
            ))}
          </select>
          <select aria-label="Drafter model" value={model} onChange={(event) => setModel(event.target.value)}>
            {HARNESS_MODELS.map((item) => (
              <option key={item} value={item}>
                {kcModelLabel(item)}
              </option>
            ))}
          </select>
          <button type="button" className="harness-draft" disabled={!activeId || busy} onClick={() => void draft()}>
            {busy ? "Drafting cards…" : "Draft cards from this run"}
          </button>
          <button type="button" disabled={!activeId || busy} onClick={() => void saveSuite()}>
            Save as suite
          </button>
          <button type="button" disabled={!activeId || busy} onClick={() => void markBaseline()}>
            Mark baseline
          </button>
        </div>
      </header>
      <p className="help">
        Nothing here changes the live prompt. Each card names the prompt-builder section and function, quotes the current sentences from the stored tutor prompt, and gives a replacement, including a shorter or removed line. Accepting a setting does not apply it. Try it copies the tutor profile into a hidden trial profile and queues the same slice. You start that run yourself.
      </p>
      {error ? <p className="banner">{error}</p> : null}
      {note ? <p className="help">{note}</p> : null}
      {!activeId ? (
        <p className="harness-empty">No runs yet. Start a run, then draft cards for it.</p>
      ) : cards.length === 0 ? (
        <p className="harness-empty">
          No cards yet for this run. Press Draft cards from this run. The button stays on the newest run when you open this tab, and it shows Drafting cards… while the request runs. Finishing a run does not create cards. Drafting does not change the live tutor.
        </p>
      ) : (
        <p className="help">These cards are saved on this run. Accept does not change the live tutor.</p>
      )}
      {cards.map((card) => {
        const evidence = card.evidence || {};
        const replacement = evidence.replacement || card.proposed?.text || "";
        const shorter = evidence.shorter || card.proposed?.shorter || "";
        return (
          <article key={card.id} className="harness-card">
            <h3>{card.title}</h3>
            <p>Block type: {evidence.block_type || "an unknown block"}</p>
            <p>
              Section: {evidence.section || "—"}. Function: {evidence.function || "—"}
              {evidence.symbol && evidence.symbol !== evidence.function ? ` (${evidence.symbol})` : ""}
            </p>
            <p>
              {card.kind} · prompt gets {card.prompt_direction} · {card.status} · {card.confidence}
            </p>
            <p>{evidence.summary}</p>
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
