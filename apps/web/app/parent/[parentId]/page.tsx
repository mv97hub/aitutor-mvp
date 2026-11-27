import { redirect } from "next/navigation";

import { ParentDashboard } from "@/components/parent/ParentDashboard";
import { ParentMissing } from "@/components/parent/ParentMissing";
import { api } from "@/lib/api";
import type { SkillRadarPayload } from "@/lib/graph2";
import { knownId, parentSettings, type Parent } from "@/lib/parent";
import type { ParentCopilotSummary } from "@/lib/parent-copilot";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Parent dashboard · AI Tutor" };

export default async function ParentDashboardPage({ params }: { params: Promise<{ parentId: string }> }) {
  const { parentId: raw } = await params;
  const parentId = knownId(raw);
  if (!parentId) return <ParentMissing title="That parent was not found." detail="Pick someone from the parent list." />;
  let parent: Parent | null = null;
  let learners: Student[] = [];
  const radars: Record<string, SkillRadarPayload | null> = {};
  const copilots: Record<string, ParentCopilotSummary | null> = {};
  let error: string | null = null;
  try {
    [parent, learners] = await Promise.all([
      api<Parent>(`/parents/${parentId}`),
      api<Student[]>(`/parents/${parentId}/students`),
    ]);
    const loadedChildData = await Promise.all(
      learners.map(async (child) => {
        const [radarPayload, copilotPayload] = await Promise.all([
          api<SkillRadarPayload>(`/parents/${parentId}/children/${child.id}/radar`).catch(() => null),
          api<ParentCopilotSummary>(`/parents/${parentId}/children/${child.id}/copilot`).catch(() => null),
        ]);
        return [child.id, radarPayload, copilotPayload] as const;
      }),
    );
    for (const [cid, radarPayload, copilotPayload] of loadedChildData) {
      radars[cid] = radarPayload;
      copilots[cid] = copilotPayload;
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  if (!parent) {
    return <ParentMissing title="That parent was not found." detail={error || "Pick someone from the parent list."} />;
  }
  if (learners.length === 0) redirect(parentSettings(parent.id));
  return <ParentDashboard parent={parent} learners={learners} radars={radars} copilots={copilots} />;
}
