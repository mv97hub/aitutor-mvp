"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export function RunSummary({ runId, text }: { runId?: string; text?: string }) {
  const [loaded, setLoaded] = useState(text || "");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (text) {
      setLoaded(text);
      return;
    }
    if (!runId) return;
    let stop = false;
    api<{ summary?: { text?: string } }>(`/kc/harness/runs/${runId}/report`)
      .then((report) => {
        if (!stop) setLoaded(report.summary?.text || "");
      })
      .catch(() => {
        if (!stop) setLoaded("");
      });
    return () => {
      stop = true;
    };
  }, [runId, text]);

  useEffect(() => {
    setCopied(false);
  }, [loaded]);

  if (!loaded) return null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(loaded);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="harness-summary">
      <div className="harness-actions">
        <h3>Run summary</h3>
        <button type="button" onClick={() => void copy()}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>{loaded}</pre>
    </div>
  );
}
