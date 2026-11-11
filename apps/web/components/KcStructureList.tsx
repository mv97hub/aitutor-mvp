"use client";

import { useState } from "react";

import { addKcComponent, deleteKcUnit, moveKcComponent, removeKcComponent } from "@/lib/kc-actions";
import { blockSummary } from "@/lib/kc-blocks";
import type { KcComponent, KcStructure } from "@/lib/kc";
import { pipelineAction } from "@/lib/kc-pipeline";
import { structureControls, unitsAfterStartOver, type StartOverChoice } from "@/lib/kc-structure";

function rowStatus(row: { missing: string[]; marked_complete: boolean }) {
  if (row.missing.length) return row.missing.join(", ");
  if (row.marked_complete) return "Marked complete";
  return "Complete";
}

/** Units and components. Deleting a unit or a component asks first. */
export function KcStructureList({
  courseId,
  structure,
  patches,
  order,
  mode = "wizard",
}: {
  courseId: string;
  structure: KcStructure | null;
  patches: KcComponent[];
  order: string[];
  mode?: "wizard" | "chat";
}) {
  const unitGroups = (structure?.groups ?? []).filter((group) => typeof group.unit_index === "number");
  const controls = structureControls(unitGroups.length);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);

  async function confirmStartOver(choice: StartOverChoice) {
    const remaining = unitsAfterStartOver(unitGroups, choice);
    const clearComponents = choice === "delete-components" && remaining.length === 0;
    setResetOpen(false);
    setResetError(null);
    try {
      await pipelineAction(courseId, "reset", { components: clearComponents });
      const modeQuery = mode === "chat" ? "&mode=chat" : "";
      window.location.assign(`/kc-studio?course=${courseId}${modeQuery}`);
    } catch (error) {
      setResetError(error instanceof Error ? error.message : "The draft did not reset.");
    }
  }

  return (
    <div className="kc-structure">
      <div className="kc-blueprint-row">
        <h2>Course structure</h2>
        {controls.startOver ? (
          <button className="ghost" type="button" onClick={() => setResetOpen(true)}>
            Start over
          </button>
        ) : null}
      </div>
      {resetError ? (
        <p className="banner" role="alert">
          {resetError}
        </p>
      ) : null}
      {resetOpen ? (
        <div className="kc-confirm" role="dialog" aria-modal="true" aria-label="Start over">
          <p>Start over clears the draft. Deleting components also removes the ones already on this course.</p>
          <div className="kc-pipeline-actions">
            <button className="ghost" type="button" onClick={() => void confirmStartOver("draft")}>
              Reset draft only
            </button>
            <button className="button" type="button" onClick={() => void confirmStartOver("delete-components")}>
              Start over and delete components
            </button>
            <button className="ghost" type="button" onClick={() => setResetOpen(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
      {(structure?.groups ?? []).map((group, groupIndex) => (
        <section key={`${group.title ?? "group"}-${groupIndex}`} aria-label={group.title || "Components"}>
          {group.title ? (
            <div className="kc-blueprint-row">
              <h3>{group.title}</h3>
              {typeof group.unit_index === "number" && controls.deleteUnit ? (
                <form
                  action={deleteKcUnit}
                  onSubmit={(event) => {
                    if (!window.confirm(`Delete ${group.title} and its components?`)) event.preventDefault();
                  }}
                >
                  <input type="hidden" name="course_id" value={courseId} />
                  <input type="hidden" name="unit_index" value={group.unit_index} />
                  {mode === "chat" ? <input type="hidden" name="mode" value="chat" /> : null}
                  <button className="ghost" type="submit">
                    Delete unit
                  </button>
                </form>
              ) : null}
            </div>
          ) : null}
          <ul>
            {group.components.map((row) => (
              <li key={row.id}>
                <a href={`/kc-creator?course=${courseId}&kc=${row.id}`}>
                  <strong>{row.title}</strong>
                  {row.description ? <p className="kc-brief">{row.description}</p> : null}
                  <span>{row.blocks?.length ? blockSummary(row.blocks) : "No blocks yet"}</span>
                  <em>{rowStatus(row)}</em>
                </a>
                <span className="kc-row-actions">
                  <form action={moveKcComponent}>
                    <input type="hidden" name="course_id" value={courseId} />
                    <input type="hidden" name="id" value={row.id} />
                    <input type="hidden" name="direction" value="-1" />
                    {order.map((id) => (
                      <input key={id} type="hidden" name="order" value={id} />
                    ))}
                    <button className="ghost" type="submit" aria-label={`Move ${row.title} up`}>
                      Up
                    </button>
                  </form>
                  <form action={moveKcComponent}>
                    <input type="hidden" name="course_id" value={courseId} />
                    <input type="hidden" name="id" value={row.id} />
                    <input type="hidden" name="direction" value="1" />
                    {order.map((id) => (
                      <input key={id} type="hidden" name="order" value={id} />
                    ))}
                    <button className="ghost" type="submit" aria-label={`Move ${row.title} down`}>
                      Down
                    </button>
                  </form>
                  <form
                    action={removeKcComponent}
                    onSubmit={(event) => {
                      if (!window.confirm(`Remove ${row.title}?`)) event.preventDefault();
                    }}
                  >
                    <input type="hidden" name="course_id" value={courseId} />
                    <input type="hidden" name="id" value={row.id} />
                    <button className="ghost" type="submit" aria-label={`Remove ${row.title}`}>
                      Remove
                    </button>
                  </form>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {patches.length ? (
        <section>
          <h3>Patches</h3>
          <ul>
            {patches.map((patch) => (
              <li key={patch.id}>
                <a href={`/kc-creator?course=${courseId}&kc=${patch.id}`}>
                  <strong>{patch.title}</strong>
                  {patch.description ? <p className="kc-brief">{patch.description}</p> : null}
                  <span>{patch.blocks?.length ? blockSummary(patch.blocks) : "No blocks yet"}</span>
                  <em>Not a target</em>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <form className="kc-add" action={addKcComponent}>
        <input type="hidden" name="course_id" value={courseId} />
        <label>
          Add a component by title
          <input aria-label="New component title" name="title" required />
        </label>
        <button className="button" type="submit">
          Add
        </button>
      </form>
    </div>
  );
}
