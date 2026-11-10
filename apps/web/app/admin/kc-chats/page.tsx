import { ViewKcChats } from "@/components/ViewKcChats";
import { api } from "@/lib/api";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "KC View Chats · Administration · AI Tutor" };

export default async function AdminKcChatsPage() {
  let students: Student[] = [];
  let error: string | null = null;
  try {
    students = await api<Student[]>("/students");
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <ViewKcChats initialStudents={students} initialError={error} />;
}
