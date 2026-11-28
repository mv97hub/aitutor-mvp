import type { KcTutorCourse, KcWarmupItem } from "./kc";

export const PLACEMENT_MIN_COMPONENTS = 4;

export function shouldOfferPlacementEntry(course: KcTutorCourse): boolean {
  if (typeof course.placement_eligible === "boolean") {
    return course.placement_eligible;
  }
  const count = course.component_count ?? 0;
  const status = course.placement_status ?? "not_started";
  return !course.started && count >= PLACEMENT_MIN_COMPONENTS && (status === "not_started" || status === "in_progress");
}

export function placementProbeCountLabel(course: KcTutorCourse): string {
  const max = course.placement_max_probes && course.placement_max_probes > 0
    ? Math.min(4, course.placement_max_probes)
    : Math.min(4, Math.max(1, Math.ceil(Math.log2(Math.max(2, course.component_count ?? 4)))));
  return max === 1 ? "1 quick question" : `up to ${max} quick questions`;
}

export function warmupBadgeLabel(count: number | undefined): string | null {
  const n = Math.max(0, Math.floor(count ?? 0));
  if (n === 0) return null;
  if (n === 1) return "2-min memory boost ready";
  return `${n} quick memory boosts ready`;
}

export function retentionPercent(item: Pick<KcWarmupItem, "retrieval_strength">): number {
  const clamped = Math.max(0, Math.min(1, Number(item.retrieval_strength ?? 0)));
  return Math.round(clamped * 100);
}
