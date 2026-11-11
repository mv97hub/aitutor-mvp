import { ChildChooser } from "@/components/learn/ChildChooser";
import { api } from "@/lib/api";
import type { LearnerCard } from "@/lib/learn";
import { LEARN_MOBILE } from "@/lib/learn-mobile";

export const dynamic = "force-dynamic";

export const metadata = { title: "Who's learning · AI Tutor" };

export default async function LearnMobilePage() {
  let learners: LearnerCard[] = [];
  let error: string | null = null;
  try {
    learners = await api<LearnerCard[]>("/kc/tutor/learners");
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <ChildChooser learners={learners} error={error} basePath={LEARN_MOBILE} />;
}
