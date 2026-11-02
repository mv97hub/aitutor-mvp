import { ViewChats } from "@/components/ViewChats";
import { api } from "@/lib/api";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "View chats · AI Tutor" };

export default async function ViewChatsPage() {
  let students: Student[] = [];
  let error: string | null = null;
  try {
    students = await api<Student[]>("/students");
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <ViewChats initialStudents={students} initialError={error} />;
}
