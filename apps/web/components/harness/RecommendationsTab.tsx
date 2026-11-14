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
  evidence: { summary?: string };
  proposed: { text?: string };
  trial_profile_id?: string | null;
};

export function RecommendationsTab({ runId }: { runId: string }) {
  const [cards, setCards] = useState<Card[]>([]);
  const [model, setModel] = useState("gpt-6.1-sol");
  const [error, setError] = useState("");

  async function load() {
    const query = runId ? `?run_id=${runId}` : "";
    setCards(await api<Card[]>(`/kc/harness/recommendations${query}`));
  }

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : "Could not load recommendations."));
  }, [runId]);

  async function draft() {
    setError("");
    try {
      const findings = await api(`/kc/harness/runs/${runId}/findings`);
      const response = await fetch("/api/kc/harness/recommend", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ model, findings }),
      });
      if (!response.ok) throw new Error(await response.text());
      const drafted = await response.json();
      await api("/kc/harness/recommendations", {
        method: "POST",
        body: JSON.stringify({ run_id: runId, cards: drafted.cards }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not draft cards.");
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
    await api("/kc/harness/suites", { method: "POST", body: JSON.stringify({ name, run_id: runId }) });
  }

  async function markBaseline() {
    const suiteId = window.prompt("Suite id");
    if (!suiteId) return;
    await api(`/kc/harness/suites/${suiteId}/baseline`, { method: "POST", body: JSON.stringify({ run_id: runId }) });
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
          <button type="button" disabled={!runId} onClick={() => void draft()}>
            Draft cards
          </button>
          <button type="button" disabled={!runId} onClick={() => void saveSuite()}>
            Save as suite
          </button>
          <button type="button" disabled={!runId} onClick={() => void markBaseline()}>
            Mark baseline
          </button>
        </div>
      </header>
      <p className="help">
        Nothing here changes the live prompt. A card can propose a removal or shorter wording. Accepting a setting does not apply it. Try it copies the tutor profile into a hidden trial profile and queues the same slice. You start that run yourself.
      </p>
      {error ? <p className="banner">{error}</p> : null}
      {cards.map((card) => (
        <article key={card.id} className="harness-card">
          <h3>{card.title}</h3>
          <p>
            {card.kind} · prompt gets {card.prompt_direction} · {card.status} · {card.confidence}
          </p>
          <p>{card.evidence?.summary}</p>
          <p>
            <strong>{card.cause_class}.</strong> {card.place}
          </p>
          <p>{card.proposed?.text}</p>
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
      ))}
    </section>
  );
}
