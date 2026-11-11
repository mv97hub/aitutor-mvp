"use client";

import type { KcBlueprint, KcStatement } from "@/lib/kc";
import { coverageOf } from "@/lib/kc-standards";

/** Statements down the side, components across, gaps highlighted. */
export function KcCoverageMatrix({
  statements,
  blueprint,
}: {
  statements: KcStatement[];
  blueprint: KcBlueprint;
}) {
  const coverage = coverageOf(statements, blueprint);
  const columns = blueprint.units.flatMap((unit) => unit.components);
  if (!statements.length) return null;

  return (
    <div className="kc-coverage">
      <h3>Coverage</h3>
      <div className="kc-coverage-scroll">
        <table>
          <caption>Standard statements down the side, components across.</caption>
          <thead>
            <tr>
              <th scope="col">Statement</th>
              {columns.map((item, index) => (
                <th key={item.code || `new-${index}`} scope="col">
                  {item.code || "New"}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {coverage.rows.map((row) => (
              <tr key={row.code} className={`kc-coverage-${row.status}`}>
                <th scope="row">
                  <span className="studio-code">{row.code}</span> {row.text}
                </th>
                {columns.map((item, index) => (
                  <td key={item.code || `new-${index}`}>{row.components.includes(item.code) ? "Yes" : ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ds-quiet">
        {coverage.gaps.length ? `Missing: ${coverage.gaps.join(", ")}. ` : "Every statement is on a component. "}
        {coverage.once_without_review.length
          ? `Covered only once, with no later review: ${coverage.once_without_review.join(", ")}. `
          : ""}
        {coverage.extensions.length ? `Extension: ${coverage.extensions.join(", ")}.` : ""}
      </p>
    </div>
  );
}
