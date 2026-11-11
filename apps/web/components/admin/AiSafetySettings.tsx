"use client";

import { useEffect, useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { api } from "@/lib/api";
import {
  BLOCKED_TOPIC_OPTIONS,
  SAFETY_FIELDS,
  SAFETY_GROUPS,
  type AiSafetyResponse,
  type AiSafetySettings,
  type SafetyField,
} from "@/lib/ai-safety";

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function AiSafetySettings() {
  const [draft, setDraft] = useState<AiSafetySettings | null>(null);
  const [preview, setPreview] = useState("");
  const [saved, setSaved] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api<AiSafetyResponse>("/ai-safety")
      .then((body) => {
        if (cancelled) return;
        setDraft(body.settings);
        setPreview(body.safety_text);
        setSaved(JSON.stringify(body.settings));
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!draft) return;
    const current = JSON.stringify(draft);
    if (current === saved) return;
    const handle = window.setTimeout(() => {
      api<AiSafetyResponse>("/ai-safety/preview", {
        method: "POST",
        body: JSON.stringify(draft),
      })
        .then((body) => setPreview(body.safety_text))
        .catch((err) => setError(messageOf(err)));
    }, 200);
    return () => window.clearTimeout(handle);
  }, [draft, saved]);

  function apply(body: AiSafetyResponse, note: string) {
    setDraft(body.settings);
    setPreview(body.safety_text);
    setSaved(JSON.stringify(body.settings));
    setNotice(note);
    setError(null);
  }

  async function onSave() {
    if (!draft) return;
    setBusy(true);
    setNotice(null);
    try {
      const body = await api<AiSafetyResponse>("/ai-safety", {
        method: "PUT",
        body: JSON.stringify(draft),
      });
      apply(body, "Saved. Every tutor uses these rules.");
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function onReset() {
    setBusy(true);
    setNotice(null);
    try {
      const body = await api<AiSafetyResponse>("/ai-safety/reset", { method: "POST" });
      apply(body, "Reset to safe defaults.");
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  function setKey<K extends keyof AiSafetySettings>(key: K, value: AiSafetySettings[K]) {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
    setNotice(null);
  }

  return (
    <AdminFrame current="ai-safety">
      <article className="editor agent-config-editor">
        <p className="eyebrow">Administration</p>
        <h2>AI Safety</h2>
        <p className="help">
          One set of rules for every tutor and every child. They override persona, child preferences, humor, and block
          rules.
        </p>
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        {notice ? <p className="help">{notice}</p> : null}
        <div className="ai-safety-actions">
          <button className="button" type="button" onClick={() => void onSave()} disabled={!draft || busy}>
            Save
          </button>
          <button className="button ghost" type="button" onClick={() => void onReset()} disabled={!draft || busy}>
            Reset to safe defaults
          </button>
        </div>
        {!draft ? <p className="help">Loading safety settings.</p> : null}
        {draft
          ? SAFETY_GROUPS.map((group) => (
              <section key={group} className="agent-config-card" aria-label={group}>
                <h3>{group}</h3>
                {SAFETY_FIELDS.filter((field) => field.group === group).map((field) => (
                  <SafetyControl
                    key={field.key}
                    field={field}
                    draft={draft}
                    onChange={(value) => setKey(field.key, value as never)}
                    onHelpline={(value) => setKey("helpline", value)}
                  />
                ))}
              </section>
            ))
          : null}
        <section className="agent-config-card" aria-label="Safety preview">
          <h3>Safety text</h3>
          <p className="help">The exact Safety section the tutor receives. It updates as the settings change.</p>
          <pre className="ai-safety-preview" aria-label="Safety preview">
            {preview || "The Safety text appears here."}
          </pre>
        </section>
      </article>
    </AdminFrame>
  );
}

function SafetyControl({
  field,
  draft,
  onChange,
  onHelpline,
}: {
  field: SafetyField;
  draft: AiSafetySettings;
  onChange: (value: string | boolean | string[]) => void;
  onHelpline: (value: string) => void;
}) {
  if (field.kind === "topics") {
    const selected = draft.blocked_topics;
    return (
      <div className="kc-chip-group" role="group" aria-label={field.label} title={field.hover}>
        <span className="kc-prompt-name">{field.label}</span>
        {BLOCKED_TOPIC_OPTIONS.map(([id, label]) => {
          const active = selected.includes(id);
          return (
            <button
              key={id}
              type="button"
              className={`kc-chip${active ? " is-active" : ""}`}
              aria-pressed={active}
              title={field.hover}
              onClick={() =>
                onChange(active ? selected.filter((item) => item !== id) : [...selected, id])
              }
            >
              {label}
            </button>
          );
        })}
      </div>
    );
  }
  if (field.kind === "message") {
    return (
      <div>
        <label title={field.hover}>
          {field.label}
          <textarea
            aria-label={field.label}
            title={field.hover}
            value={draft.trusted_adult_message}
            maxLength={400}
            onChange={(event) => onChange(event.target.value)}
          />
        </label>
        <label title="Optional local helpline. Leave blank until you have one.">
          Helpline
          <input
            aria-label="Helpline"
            title="Optional local helpline. Leave blank until you have one."
            value={draft.helpline}
            maxLength={200}
            onChange={(event) => onHelpline(event.target.value)}
          />
        </label>
      </div>
    );
  }
  if (field.kind === "bool") {
    const checked = Boolean(draft[field.key]);
    return (
      <label title={field.hover}>
        {field.label}
        <select
          aria-label={field.label}
          title={field.hover}
          value={checked ? "on" : "off"}
          onChange={(event) => onChange(event.target.value === "on")}
        >
          <option value="on">On</option>
          <option value="off">Off</option>
        </select>
      </label>
    );
  }
  const value = String(draft[field.key]);
  return (
    <label title={field.hover}>
      {field.label}
      <select
        aria-label={field.label}
        title={field.hover}
        value={field.kind === "locked" ? field.options?.[0][0] : value}
        disabled={field.kind === "locked"}
        onChange={(event) => onChange(event.target.value)}
      >
        {(field.options ?? []).map(([id, label]) => (
          <option key={id} value={id}>
            {label}
          </option>
        ))}
      </select>
    </label>
  );
}
