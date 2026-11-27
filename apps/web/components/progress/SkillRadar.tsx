"use client";

import { useState } from "react";

import { NOT_ENOUGH_YET, radarGeometry, type SkillRadarPayload } from "@/lib/graph2";

const VIEW_W = 380;
const VIEW_H = 330;
const CX = 190;
const CY = 165;
const RADIUS = 98;
const LABEL_RADIUS = 128;

function labelAnchor(x: number): "start" | "middle" | "end" {
  if (x < CX - 16) return "end";
  if (x > CX + 16) return "start";
  return "middle";
}

export function SkillRadar({
  radar,
  heading = "Thinking skills",
}: {
  radar: SkillRadarPayload | null | undefined;
  heading?: string;
}) {
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const { spokes, readyVertices, filledPolygonPoints, confirmedSegments, ringPolygons } = radarGeometry(radar, {
    cx: CX,
    cy: CY,
    radius: RADIUS,
    labelRadius: LABEL_RADIUS,
  });
  const active = spokes.find((pt) => pt.spoke.skill === selectedSkill) ?? null;
  const readyCount = readyVertices.length;

  return (
    <section className="skill-radar" aria-label={heading}>
      <div className="skill-radar-head">
        <h2>{heading}</h2>
        <p className="skill-radar-sub">
          {readyCount === 0
            ? `Hollow spokes need at least ${radar?.min_observations ?? 3} observations before drawing.`
            : `${readyCount} of 8 skills have enough observations to draw.`}
        </p>
      </div>

      <div className="skill-radar-layout">
        <svg
          className="skill-radar-svg"
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          role="img"
          aria-label="Eight-skill radar chart"
        >
          {ringPolygons.map((points, idx) => (
            <polygon key={idx} points={points} className="skill-radar-ring" />
          ))}

          {spokes.map((pt) => (
            <line
              key={`axis-${pt.spoke.skill}`}
              x1={CX}
              y1={CY}
              x2={pt.outerX}
              y2={pt.outerY}
              className={pt.hollow ? "skill-radar-axis is-hollow" : "skill-radar-axis is-ready"}
            />
          ))}

          {filledPolygonPoints ? (
            <polygon points={filledPolygonPoints} className="skill-radar-fill" />
          ) : null}

          {confirmedSegments.map((seg, idx) => (
            <line
              key={`seg-${idx}`}
              x1={seg.x1}
              y1={seg.y1}
              x2={seg.x2}
              y2={seg.y2}
              className="skill-radar-edge"
            />
          ))}

          {spokes.map((pt) => {
            const isSelected = pt.spoke.skill === selectedSkill;
            const anchor = labelAnchor(pt.labelX);
            return (
              <g
                key={pt.spoke.skill}
                className={pt.hollow ? "skill-radar-spoke is-hollow" : "skill-radar-spoke is-ready"}
                onClick={() => setSelectedSkill(isSelected ? null : pt.spoke.skill)}
              >
                {pt.hollow ? (
                  <circle
                    cx={pt.outerX}
                    cy={pt.outerY}
                    r={5}
                    className={`skill-radar-dot is-hollow${isSelected ? " is-selected" : ""}`}
                    data-skill={pt.spoke.skill}
                    data-hollow="true"
                  />
                ) : (
                  <circle
                    cx={pt.pointX as number}
                    cy={pt.pointY as number}
                    r={5.5}
                    className={`skill-radar-dot is-ready${isSelected ? " is-selected" : ""}`}
                    data-skill={pt.spoke.skill}
                    data-hollow="false"
                  />
                )}
                <text x={pt.labelX} y={pt.labelY} textAnchor={anchor} className="skill-radar-label">
                  {pt.spoke.label}
                </text>
                {pt.hollow ? (
                  <text
                    x={pt.labelX}
                    y={pt.labelY + 12}
                    textAnchor={anchor}
                    className="skill-radar-hollow-tag"
                  >
                    {NOT_ENOUGH_YET}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>

        <ul className="skill-radar-list" aria-label="Skill observations">
          {spokes.map((pt) => {
            const isSelected = pt.spoke.skill === selectedSkill;
            return (
              <li key={pt.spoke.skill}>
                <button
                  type="button"
                  className={`skill-radar-row${pt.hollow ? " is-hollow" : " is-ready"}${isSelected ? " is-selected" : ""}`}
                  aria-pressed={isSelected}
                  onClick={() => setSelectedSkill(isSelected ? null : pt.spoke.skill)}
                >
                  <span className="skill-radar-row-name">{pt.spoke.label}</span>
                  <span className="skill-radar-row-meta">
                    {pt.hollow
                      ? `${NOT_ENOUGH_YET} (${pt.spoke.count}/${radar?.min_observations ?? 3})`
                      : `${Math.round((pt.spoke.score ?? 0) * 100)}% · ${pt.spoke.count} obs`}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {active ? (
        <div className="skill-radar-detail">
          <strong>{active.spoke.label}</strong>
          {active.hollow ? (
            <p>
              {NOT_ENOUGH_YET} — {active.spoke.count} of {radar?.min_observations ?? 3} observations recorded so far.
            </p>
          ) : (
            <>
              <p>
                Based on {active.spoke.count} observations across completed components.
              </p>
              {active.spoke.last_quote ? (
                <blockquote className="skill-end-card-quote">&ldquo;{active.spoke.last_quote}&rdquo;</blockquote>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
