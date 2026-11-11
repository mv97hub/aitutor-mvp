import { ParentLanding } from "@/components/parent/ParentLanding";
import { api } from "@/lib/api";
import type { Parent } from "@/lib/parent";

export const dynamic = "force-dynamic";

export const metadata = { title: "Parent portal · AI Tutor" };

export default async function ParentLandingPage() {
  let parents: Parent[] = [];
  let error: string | null = null;
  try {
    parents = await api<Parent[]>("/parents");
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <ParentLanding parents={parents} error={error} />;
}
