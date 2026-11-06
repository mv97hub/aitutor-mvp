import { KcStudio } from "@/components/KcStudio";
import { api } from "@/lib/api";
import type { KcCourse, KcDraft, KcNetwork, KcStructure } from "@/lib/kc";

export const dynamic = "force-dynamic";

export const metadata = { title: "KC Course Creator · AI Tutor" };

export default async function KcStudioPage({
  searchParams,
}: {
  searchParams: Promise<{ course?: string; network?: string; message?: string; error?: string }>;
}) {
  const params = await searchParams;
  let courses: KcCourse[] = [];
  let selected: KcCourse | null = null;
  let structure: KcStructure | null = null;
  let network: KcNetwork | null = null;
  let draft: KcDraft | null = null;
  let reply = "";
  let error: string | null = params.error ? decodeURIComponent(params.error) : null;
  try {
    courses = await api<KcCourse[]>("/kc/courses");
    if (params.course) {
      selected = courses.find((item) => item.id === params.course) ?? (await api<KcCourse>(`/kc/courses/${params.course}`));
      structure = await api<KcStructure>(`/kc/courses/${params.course}/structure`);
      if (params.network === "1") {
        network = await api<KcNetwork>(`/kc/courses/${params.course}/network`);
      }
      const message = (params.message || "").trim();
      if (message) {
        const result = await api<{ reply: string; draft: KcDraft }>(`/kc/courses/${params.course}/draft`, {
          method: "POST",
          body: JSON.stringify({ message }),
        });
        draft = result.draft;
        reply = result.reply;
      }
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "The studio service is not reachable.";
  }
  return (
    <KcStudio
      initialCourses={courses}
      initialCourse={selected}
      initialStructure={structure}
      initialNetwork={network}
      initialDraft={draft}
      initialReply={reply}
      initialMessage={params.message ?? ""}
      initialError={error}
    />
  );
}
