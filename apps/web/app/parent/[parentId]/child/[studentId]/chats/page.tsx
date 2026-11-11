import { ParentChats } from "@/components/parent/ParentChats";
import { ParentMissing } from "@/components/parent/ParentMissing";
import { api } from "@/lib/api";
import { knownId, type Parent, type ParentChatSummary } from "@/lib/parent";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Chats · Parent portal · AI Tutor" };

export default async function ParentChatsPage({
  params,
}: {
  params: Promise<{ parentId: string; studentId: string }>;
}) {
  const { parentId: rawParent, studentId: rawStudent } = await params;
  const parentId = knownId(rawParent);
  const studentId = knownId(rawStudent);
  if (!parentId || !studentId) {
    return <ParentMissing title="That page was not found." detail="Pick a parent and a child from the list." />;
  }
  let parent: Parent | null = null;
  let learner: Student | null = null;
  let learners: Student[] = [];
  let sessions: ParentChatSummary[] = [];
  let error: string | null = null;
  try {
    const [loaded, linked] = await Promise.all([
      api<Parent>(`/parents/${parentId}`),
      api<Student[]>(`/parents/${parentId}/students`),
    ]);
    parent = loaded;
    learners = linked;
    learner = linked.find((item) => item.id === studentId) ?? null;
    if (learner) sessions = await api<ParentChatSummary[]>(`/parents/${parentId}/children/${studentId}/sessions`);
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  if (!parent) {
    return <ParentMissing title="That parent was not found." detail={error || "Pick someone from the parent list."} />;
  }
  if (!learner) {
    return (
      <ParentMissing
        title="That child is not linked to you."
        detail={error || "Open your settings from the dashboard to choose the children you follow."}
      />
    );
  }
  return (
    <ParentChats
      parentId={parent.id}
      parentName={parent.name}
      studentId={learner.id}
      studentName={learner.display_name}
      learners={learners}
      initialSessions={sessions}
      initialError={error}
    />
  );
}
