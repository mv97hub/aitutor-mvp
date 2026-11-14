import Link from "next/link";

import { KcBanner } from "@/components/KcBanner";
import { ProfilesView, type HarnessPersona } from "@/components/harness/ProfilesView";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata = { title: "AI Test Children profiles · AI Tutor" };

export default async function TestChildProfilesPage() {
  let personas: HarnessPersona[] = [];
  let loadError: string | null = null;
  try {
    personas = await api<HarnessPersona[]>("/kc/harness/personas");
  } catch (err) {
    loadError = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return (
    <>
      <KcBanner name="AI Test Children" />
      <main className="harness-page">
        <p>
          <Link href="/kc-test-children">Back to AI Test Children</Link>
        </p>
        {loadError ? <p className="banner">{loadError}</p> : null}
        <ProfilesView personas={personas} heading="AI test child profiles" />
      </main>
    </>
  );
}
