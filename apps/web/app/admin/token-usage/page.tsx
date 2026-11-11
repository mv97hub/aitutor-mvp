import { TokenUsage } from "@/components/admin/TokenUsage";
import { api } from "@/lib/api";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Token usage · Administration · AI Tutor" };

export default async function TokenUsagePage() {
  let students: Student[] = [];
  let error: string | null = null;
  try {
    students = await api<Student[]>("/students");
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <TokenUsage initialStudents={students} initialError={error} />;
}
