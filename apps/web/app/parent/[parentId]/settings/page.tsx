import { ParentMissing } from "@/components/parent/ParentMissing";
import { ParentSettings } from "@/components/parent/ParentSettings";
import { api } from "@/lib/api";
import { knownId, type Parent } from "@/lib/parent";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Parent settings · AI Tutor" };

export default async function ParentSettingsPage({ params }: { params: Promise<{ parentId: string }> }) {
  const { parentId: raw } = await params;
  const parentId = knownId(raw);
  if (!parentId) return <ParentMissing title="That parent was not found." detail="Pick someone from the parent list." />;
  let parent: Parent | null = null;
  let students: Student[] = [];
  let linked: Student[] = [];
  let error: string | null = null;
  try {
    [parent, students, linked] = await Promise.all([
      api<Parent>(`/parents/${parentId}`),
      api<Student[]>("/students"),
      api<Student[]>(`/parents/${parentId}/students`),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  if (!parent) {
    return <ParentMissing title="That parent was not found." detail={error || "Pick someone from the parent list."} />;
  }
  return (
    <ParentSettings
      key={linked.map((item) => item.id).join(",")}
      parent={parent}
      students={students}
      linkedIds={linked.map((item) => item.id)}
      error={error}
    />
  );
}
