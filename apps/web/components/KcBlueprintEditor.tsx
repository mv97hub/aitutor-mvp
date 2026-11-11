"use client";

import { useEffect, useState } from "react";

import { KcCoverageMatrix } from "@/components/KcCoverageMatrix";
import type { KcBlueprint, KcStatement } from "@/lib/kc";
import {
  addComponent,
  earlierCodes,
  editComponent,
  editOutcomes,
  editUnit,
  moveComponent,
  parseCodes,
  removeComponent,
} from "@/lib/kc-blueprint-edit";

/** The blueprint, editable before any descriptions are written. */
export function KcBlueprintEditor({
  blueprint,
  statements = [],
  busy,
  onSave,
  onApprove,
}: {
  blueprint: KcBlueprint;
  statements?: KcStatement[];
  busy: boolean;
  onSave: (blueprint: KcBlueprint) => void;
  onApprove: (blueprint: KcBlueprint) => void;
}) {
  const signature = blueprint.units.map((unit) => unit.components.map((item) => item.code).join(",")).join("|");
  const incoming = JSON.stringify(blueprint);
  const [draft, setDraft] = useState(blueprint);

  useEffect(() => {
    setDraft(JSON.parse(incoming) as KcBlueprint);
  }, [incoming]);

  const position = new Map<string, number>();
  let count = 0;
  for (const unit of draft.units) {
    for (const item of unit.components) {
      count += 1;
      if (item.code) position.set(item.code, count);
    }
  }

  return (
    <div className="kc-blueprint">
      <div className="kc-blueprint-layout">
        <div className="kc-blueprint-main">
      <label>
        Outcomes, one per line
        <textarea
          aria-label="Course outcomes"
          rows={Math.max(3, draft.outcomes.length)}
          value={draft.outcomes.join("\n")}
          disabled={busy}
          onChange={(event) => setDraft(editOutcomes(draft, event.target.value))}
        />
      </label>
      {draft.units.map((unit, unitIndex) => (
        <section key={`${signature}-${unitIndex}`} className="kc-blueprint-unit">
          <h3>Unit {unitIndex + 1}</h3>
          <label>
            Unit title
            <input
              aria-label={`Unit ${unitIndex + 1} title`}
              value={unit.title}
              disabled={busy}
              onChange={(event) => setDraft(editUnit(draft, unitIndex, { title: event.target.value }))}
            />
          </label>
          <label>
            Unit summary
            <input
              aria-label={`Unit ${unitIndex + 1} summary`}
              value={unit.summary}
              disabled={busy}
              onChange={(event) => setDraft(editUnit(draft, unitIndex, { summary: event.target.value }))}
            />
          </label>
          <ol>
            {unit.components.map((item, index) => {
              const spot = { unit: unitIndex, index };
              const earlier = earlierCodes(draft, spot);
              return (
                <li key={item.code || `new-${unitIndex}-${index}`}>
                  <div className="kc-blueprint-row">
                    <strong>{item.code ? `Component ${position.get(item.code)}` : "New component"}</strong>
                    <span className="studio-code">{item.code || "code assigned on save"}</span>
                    {statements.length && !(item.standards ?? []).length ? <span>Extension</span> : null}
                    <span className="kc-row-actions">
                      <button
                        type="button"
                        className="ghost"
                        aria-label={`Move ${item.title || "component"} up`}
                        disabled={busy || (unitIndex === 0 && index === 0)}
                        onClick={() => setDraft(moveComponent(draft, spot, -1))}
                      >
                        Up
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        aria-label={`Move ${item.title || "component"} down`}
                        disabled={busy || (unitIndex === draft.units.length - 1 && index === unit.components.length - 1)}
                        onClick={() => setDraft(moveComponent(draft, spot, 1))}
                      >
                        Down
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        aria-label={`Remove ${item.title || "component"}`}
                        disabled={busy}
                        onClick={() => setDraft(removeComponent(draft, spot))}
                      >
                        Remove
                      </button>
                    </span>
                  </div>
                  <label>
                    Title
                    <input
                      aria-label={`Component ${index + 1} title in unit ${unitIndex + 1}`}
                      value={item.title}
                      disabled={busy}
                      onChange={(event) => setDraft(editComponent(draft, spot, { title: event.target.value }))}
                    />
                  </label>
                  <label>
                    Summary
                    <input
                      aria-label={`Component ${index + 1} summary in unit ${unitIndex + 1}`}
                      value={item.summary}
                      disabled={busy}
                      onChange={(event) => setDraft(editComponent(draft, spot, { summary: event.target.value }))}
                    />
                  </label>
                  {statements.length ? (
                    <label>
                      Standard codes
                      <input
                        aria-label={`Component ${index + 1} standards in unit ${unitIndex + 1}`}
                        value={(item.standards ?? []).join(", ")}
                        disabled={busy}
                        placeholder="Leave blank for an extension"
                        onChange={(event) =>
                          setDraft(editComponent(draft, spot, { standards: parseCodes(event.target.value) }))
                        }
                      />
                    </label>
                  ) : null}
                  <label>
                    Prerequisites
                    <input
                      aria-label={`Component ${index + 1} prerequisites in unit ${unitIndex + 1}`}
                      value={item.prerequisites.join(", ")}
                      disabled={busy}
                      placeholder={earlier.length ? earlier.join(", ") : "None yet"}
                      onChange={(event) =>
                        setDraft(editComponent(draft, spot, { prerequisites: parseCodes(event.target.value) }))
                      }
                    />
                  </label>
                </li>
              );
            })}
          </ol>
          <button type="button" className="ghost" disabled={busy} onClick={() => setDraft(addComponent(draft, unitIndex))}>
            Add a component
          </button>
        </section>
      ))}
        </div>
        {statements.length ? <KcCoverageMatrix statements={statements} blueprint={draft} /> : null}
      </div>
      <div className="kc-pipeline-actions">
        <button type="button" className="ghost" disabled={busy} onClick={() => onSave(draft)}>
          Save blueprint
        </button>
        <button type="button" className="button" disabled={busy} onClick={() => onApprove(draft)}>
          Approve and write descriptions
        </button>
      </div>
    </div>
  );
}
