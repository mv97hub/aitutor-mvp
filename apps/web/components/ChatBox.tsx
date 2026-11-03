"use client";

import type { UIMessage } from "ai";

import type { TriangleDiagram } from "@/lib/types";

type LoosePart = {
  type: string;
  text?: string;
  data?: unknown;
  state?: string;
  output?: unknown;
  toolCallId?: string;
};

type Point = { x: number; y: number };

function readOutput(output: unknown) {
  if (!output || typeof output !== "object") return null;
  const record = output as Record<string, unknown>;
  return {
    ok: typeof record.ok === "boolean" ? record.ok : undefined,
    passed: typeof record.passed === "boolean" ? record.passed : undefined,
    score: typeof record.score === "number" ? record.score : undefined,
    feedback: typeof record.feedback === "string" ? record.feedback : undefined,
    kind: typeof record.kind === "string" ? record.kind : undefined,
    reason: typeof record.reason === "string" ? record.reason : undefined,
  };
}

function finite(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
}

function readTriangle(value: unknown): TriangleDiagram | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  if (record.kind !== "triangle") return null;
  if (!Array.isArray(record.sides) || record.sides.length !== 3) return null;
  if (!Array.isArray(record.angles) || record.angles.length !== 3) return null;
  const sides = [];
  for (const item of record.sides) {
    if (!item || typeof item !== "object") return null;
    const side = item as Record<string, unknown>;
    const length = finite(side.length);
    if (typeof side.label !== "string" || !side.label.trim() || length == null || length <= 0) return null;
    sides.push({ label: side.label, length });
  }
  const angles = [];
  for (const item of record.angles) {
    if (!item || typeof item !== "object") return null;
    const angle = item as Record<string, unknown>;
    const degrees = finite(angle.degrees);
    if (typeof angle.label !== "string" || !angle.label.trim() || degrees == null) return null;
    angles.push({ label: angle.label, degrees });
  }
  return {
    kind: "triangle",
    sides,
    angles,
    right_angle: record.right_angle === true,
  };
}

function caption(label: string, measure: number, unit: string): string {
  if (/\d/.test(label)) return label;
  const rounded = Math.round(measure * 100) / 100;
  return unit ? `${label} ${rounded}${unit}` : `${label} ${rounded}`;
}

function square(vertex: Point, prev: Point, next: Point, size: number): string {
  const toward = (from: Point, to: Point): Point => {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.hypot(dx, dy) || 1;
    return { x: dx / length, y: dy / length };
  };
  const u = toward(vertex, prev);
  const v = toward(vertex, next);
  const first = { x: vertex.x + u.x * size, y: vertex.y + u.y * size };
  const corner = { x: first.x + v.x * size, y: first.y + v.y * size };
  const third = { x: vertex.x + v.x * size, y: vertex.y + v.y * size };
  return `${first.x},${first.y} ${corner.x},${corner.y} ${third.x},${third.y}`;
}

function layoutTriangle(diagram: TriangleDiagram) {
  const sideA = diagram.sides[0].length;
  const sideB = diagram.sides[1].length;
  const sideC = diagram.sides[2].length;
  const angleA = (diagram.angles[0].degrees * Math.PI) / 180;
  const raw = [
    { x: 0, y: 0 },
    { x: sideC, y: 0 },
    { x: sideB * Math.cos(angleA), y: sideB * Math.sin(angleA) },
  ];
  if (raw.some((point) => !Number.isFinite(point.x) || !Number.isFinite(point.y))) return null;
  if (raw[2].y <= 1e-4) return null;
  const placed = Math.hypot(raw[2].x - raw[1].x, raw[2].y - raw[1].y);
  if (!(sideA > 0) || Math.abs(placed - sideA) / sideA > 0.08) return null;

  const minX = Math.min(...raw.map((point) => point.x));
  const maxX = Math.max(...raw.map((point) => point.x));
  const minY = Math.min(...raw.map((point) => point.y));
  const maxY = Math.max(...raw.map((point) => point.y));
  const spanX = Math.max(maxX - minX, 1e-6);
  const spanY = Math.max(maxY - minY, 1e-6);
  const pad = 52;
  const scale = Math.min(220 / spanX, 150 / spanY);
  const width = spanX * scale + pad * 2;
  const height = spanY * scale + pad * 2;
  const screen = raw.map((point) => ({
    x: pad + (point.x - minX) * scale,
    y: pad + (maxY - point.y) * scale,
  }));
  const center = {
    x: (screen[0].x + screen[1].x + screen[2].x) / 3,
    y: (screen[0].y + screen[1].y + screen[2].y) / 3,
  };
  const outward = (point: Point, distance: number): Point => {
    const dx = point.x - center.x;
    const dy = point.y - center.y;
    const length = Math.hypot(dx, dy) || 1;
    return { x: point.x + (dx / length) * distance, y: point.y + (dy / length) * distance };
  };

  const vertexLabels = screen.map((point, index) => ({
    ...outward(point, 22),
    text: caption(diagram.angles[index].label, diagram.angles[index].degrees, "°"),
  }));
  const sideEnds: Array<[number, number, number]> = [
    [1, 2, 0],
    [0, 2, 1],
    [0, 1, 2],
  ];
  const sideLabels = sideEnds.map(([left, right, index]) => {
    const mid = {
      x: (screen[left].x + screen[right].x) / 2,
      y: (screen[left].y + screen[right].y) / 2,
    };
    return {
      ...outward(mid, 22),
      text: caption(diagram.sides[index].label, diagram.sides[index].length, ""),
    };
  });

  let rightAngle: string | null = null;
  if (diagram.right_angle) {
    const index = diagram.angles.findIndex((angle) => Math.abs(angle.degrees - 90) <= 1.5);
    if (index >= 0) {
      const others = screen.filter((_, item) => item !== index);
      rightAngle = square(screen[index], others[0], others[1], 12);
    }
  }

  const spoken = [
    "Triangle",
    ...diagram.sides.map((side) => `side ${side.label} ${side.length}`),
    ...diagram.angles.map((angle) => `angle ${angle.label} ${angle.degrees} degrees`),
  ].join(", ");

  return {
    width,
    height,
    points: screen.map((point) => `${point.x},${point.y}`).join(" "),
    vertexLabels,
    sideLabels,
    rightAngle,
    spoken,
  };
}

function TriangleFigure({ diagram }: { diagram: TriangleDiagram }) {
  const figure = layoutTriangle(diagram);
  if (!figure) return null;
  return (
    <svg className="lesson-diagram" viewBox={`0 0 ${figure.width} ${figure.height}`} role="img" aria-label={figure.spoken}>
      <polygon points={figure.points} />
      {figure.rightAngle ? <polyline points={figure.rightAngle} /> : null}
      {figure.vertexLabels.map((item, index) => (
        <text key={`angle-${index}`} x={item.x} y={item.y} textAnchor="middle" dominantBaseline="middle">
          {item.text}
        </text>
      ))}
      {figure.sideLabels.map((item, index) => (
        <text key={`side-${index}`} x={item.x} y={item.y} textAnchor="middle" dominantBaseline="middle">
          {item.text}
        </text>
      ))}
    </svg>
  );
}

function diagramFrom(parts: LoosePart[]): TriangleDiagram | null {
  for (const part of parts) {
    if (part.type !== "data-diagram") continue;
    const diagram = readTriangle(part.data);
    if (diagram) return diagram;
  }
  return null;
}

export function ChatBox({ message, studentName }: { message: UIMessage; studentName: string }) {
  const parts = message.parts as LoosePart[];
  const diagram = message.role === "assistant" ? diagramFrom(parts) : null;
  const pieces = parts.map((part, index) => {
    const key = part.toolCallId || `${message.id}-${index}`;
    if (part.type === "text" && part.text?.trim()) {
      return <p key={key}>{part.text}</p>;
    }
    if (part.type === "tool-record_checkpoint_result") {
      if (part.state === "output-error") {
        return (
          <p key={key} className="result-card miss">
            That score did not save.
          </p>
        );
      }
      const output = readOutput(part.output);
      if (!output || part.state !== "output-available") {
        return (
          <p key={key} className="result-card">
            Checking that answer…
          </p>
        );
      }
      if (output.ok === false) {
        return (
          <p key={key} className="result-card miss">
            {output.reason}
          </p>
        );
      }
      const passed = output.passed === true;
      return (
        <p key={key} className={`result-card ${passed ? "pass" : "miss"}`}>
          Beat result: {passed ? "Passed" : "Not yet"}
          {output.score != null ? ` · ${output.score}/100` : ""}
          {output.feedback ? <span>{output.feedback}</span> : null}
        </p>
      );
    }
    return null;
  });
  if (pieces.every((piece) => piece == null) && !diagram) return null;
  return (
    <article className={`bubble ${message.role}`} aria-label={message.role === "user" ? studentName : "Tutor"}>
      {pieces}
      {diagram ? <TriangleFigure diagram={diagram} /> : null}
    </article>
  );
}
