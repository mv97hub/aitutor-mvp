import { isKcModel, kcModel, modelForCall, type KcModel } from "./kc-models.ts";

export const SKILL_ORDER = [
  "evidence",
  "perspectives",
  "causes",
  "inquiry",
  "errors",
  "transfer",
  "explaining",
  "calibration",
] as const;

export type SkillKey = (typeof SKILL_ORDER)[number];

export const SKILL_LABELS: Record<SkillKey, string> = {
  evidence: "Evidence",
  perspectives: "Perspectives",
  causes: "Causes",
  inquiry: "Inquiry",
  errors: "Errors",
  transfer: "Transfer",
  explaining: "Explaining",
  calibration: "Calibration",
};

export const NOT_ENOUGH_YET = "not enough yet";
export const MAX_END_CARD_SKILLS = 3;

export type SkillEndCardItem = {
  skill: string;
  label: string;
  sentence: string;
  quote: string;
};

export type SkillEndCard = {
  items: SkillEndCardItem[];
};

export type SkillRadarSpoke = {
  skill: SkillKey | string;
  label: string;
  count: number;
  ready: boolean;
  hollow: boolean;
  score: number | null;
  status_label: string | null;
  last_quote: string | null;
  last_observed_at: string | null;
};

export type SkillRadarPayload = {
  student_id: string;
  min_observations: number;
  spokes: SkillRadarSpoke[];
};

export type RadarSpokePoint = {
  spoke: SkillRadarSpoke;
  index: number;
  angleRad: number;
  outerX: number;
  outerY: number;
  labelX: number;
  labelY: number;
  /** Plotted vertex on [0, maxRadius]. Strictly null when hollow (< min_observations). */
  pointX: number | null;
  pointY: number | null;
  hollow: boolean;
  displayStatus: string;
};

/** Resolve the single post-close batch judge model.
 * Uses GRAPH2_JUDGE_MODEL env override when set to an allowed KC model,
 * otherwise falls back to the child's configured tutor model.
 */
export function judgeModelForCall(tutorModel: string | undefined | null, envOverride?: string | null): KcModel {
  const rawEnv = typeof envOverride === "string" ? envOverride.trim() : "";
  if (rawEnv) {
    const mapped = modelForCall(rawEnv);
    if (isKcModel(mapped)) return mapped;
  }
  return kcModel(tutorModel);
}

/** Validate and bound the child's synchronous closing end card (<= 3 skills, each with sentence + quote). */
export function normalizeEndCard(raw: unknown): SkillEndCard | null {
  if (!raw || typeof raw !== "object") return null;
  const rows = (raw as { items?: unknown }).items;
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const items: SkillEndCardItem[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const item = row as Partial<SkillEndCardItem>;
    const skill = typeof item.skill === "string" ? item.skill.trim().toLowerCase() : "";
    const label = typeof item.label === "string" ? item.label.trim() : "";
    const sentence = typeof item.sentence === "string" ? item.sentence.trim() : "";
    const quote = typeof item.quote === "string" ? item.quote.trim() : "";
    if (!skill || !label || !sentence || !quote || seen.has(skill)) continue;
    seen.add(skill);
    items.push({ skill, label, sentence, quote });
    if (items.length >= MAX_END_CARD_SKILLS) break;
  }
  return items.length > 0 ? { items } : null;
}

/** Order spokes into the canonical eight-skill clockwise wheel, keeping hollow states explicit. */
export function orderedRadarSpokes(radar: SkillRadarPayload | null | undefined): SkillRadarSpoke[] {
  const minObs = radar?.min_observations ?? 3;
  const byKey = new Map<string, SkillRadarSpoke>();
  for (const item of radar?.spokes ?? []) {
    if (item && typeof item.skill === "string") {
      byKey.set(item.skill.toLowerCase(), item);
    }
  }
  return SKILL_ORDER.map((skill) => {
    const found = byKey.get(skill);
    if (!found) {
      return {
        skill,
        label: SKILL_LABELS[skill],
        count: 0,
        ready: false,
        hollow: true,
        score: null,
        status_label: NOT_ENOUGH_YET,
        last_quote: null,
        last_observed_at: null,
      };
    }
    const count = Number.isFinite(found.count) ? Math.max(0, Math.floor(found.count)) : 0;
    const ready = count >= minObs && found.ready && typeof found.score === "number" && Number.isFinite(found.score);
    return {
      skill,
      label: found.label || SKILL_LABELS[skill],
      count,
      ready,
      hollow: !ready,
      score: ready ? Math.max(0, Math.min(1, found.score as number)) : null,
      status_label: ready ? null : found.status_label || NOT_ENOUGH_YET,
      last_quote: ready ? found.last_quote ?? null : null,
      last_observed_at: found.last_observed_at ?? null,
    };
  });
}

/** Compute 8-spoke SVG radar geometry. Hollow spokes never plot 0.50 (pointX/pointY stay null). */
export function radarGeometry(
  radar: SkillRadarPayload | null | undefined,
  { cx = 190, cy = 165, radius = 104, labelRadius = 132 }: { cx?: number; cy?: number; radius?: number; labelRadius?: number } = {},
): {
  spokes: RadarSpokePoint[];
  readyVertices: { x: number; y: number; index: number }[];
  filledPolygonPoints: string | null;
  confirmedSegments: { x1: number; y1: number; x2: number; y2: number }[];
  ringPolygons: string[];
} {
  const ordered = orderedRadarSpokes(radar);
  const total = ordered.length;

  const spokes: RadarSpokePoint[] = ordered.map((spoke, index) => {
    const angleRad = -Math.PI / 2 + (index * 2 * Math.PI) / total;
    const cos = Math.cos(angleRad);
    const sin = Math.sin(angleRad);
    const outerX = roundCoord(cx + radius * cos);
    const outerY = roundCoord(cy + radius * sin);
    const labelX = roundCoord(cx + labelRadius * cos);
    const labelY = roundCoord(cy + labelRadius * sin);
    const isHollow = spoke.hollow || !spoke.ready || spoke.score === null;
    const r = isHollow ? null : radius * Math.max(0.06, Math.min(1, spoke.score as number));
    return {
      spoke,
      index,
      angleRad,
      outerX,
      outerY,
      labelX,
      labelY,
      pointX: r === null ? null : roundCoord(cx + r * cos),
      pointY: r === null ? null : roundCoord(cy + r * sin),
      hollow: isHollow,
      displayStatus: isHollow ? spoke.status_label || NOT_ENOUGH_YET : `${spoke.count} observations`,
    };
  });

  const readyVertices = spokes
    .filter((pt) => !pt.hollow && pt.pointX !== null && pt.pointY !== null)
    .map((pt) => ({ x: pt.pointX as number, y: pt.pointY as number, index: pt.index }));

  // Only connect truly ready vertices; never fabricate a 0.50 polygon over hollow spokes.
  const filledPolygonPoints =
    readyVertices.length >= 3 ? readyVertices.map((pt) => `${pt.x},${pt.y}`).join(" ") : null;

  const confirmedSegments: { x1: number; y1: number; x2: number; y2: number }[] = [];
  for (let i = 0; i < total; i += 1) {
    const a = spokes[i];
    const b = spokes[(i + 1) % total];
    if (!a.hollow && !b.hollow && a.pointX !== null && a.pointY !== null && b.pointX !== null && b.pointY !== null) {
      confirmedSegments.push({ x1: a.pointX, y1: a.pointY, x2: b.pointX, y2: b.pointY });
    }
  }

  const ringPolygons = [0.33, 0.66, 1.0].map((frac) =>
    spokes
      .map((pt) => `${roundCoord(cx + radius * frac * Math.cos(pt.angleRad))},${roundCoord(cy + radius * frac * Math.sin(pt.angleRad))}`)
      .join(" "),
  );

  return { spokes, readyVertices, filledPolygonPoints, confirmedSegments, ringPolygons };
}

function roundCoord(value: number): number {
  return Math.round(value * 10) / 10;
}
