import { KcCreator } from "@/components/KcCreator";
import { api } from "@/lib/api";
import type { KcCourse, KcCreatorThread } from "@/lib/kc";
import { kcModel } from "@/lib/kc-models";

export const dynamic = "force-dynamic";

export const metadata = { title: "KC Creator · AI Tutor" };

export default async function KcCreatorPage({
  searchParams,
}: {
  searchParams: Promise<{ course?: string; kc?: string; model?: string; error?: string }>;
}) {
  const params = await searchParams;
  const model = kcModel(params.model);
  let courses: KcCourse[] = [];
  let selected: KcCourse | null = null;
  let thread: KcCreatorThread | null = null;
  let error: string | null = params.error ? decodeURIComponent(params.error) : null;
  try {
    courses = await api<KcCourse[]>("/kc/courses");
    if (params.course) {
      selected = courses.find((item) => item.id === params.course) ?? (await api<KcCourse>(`/kc/courses/${params.course}`));
    }
    if (params.kc) {
      thread = await api<KcCreatorThread>(`/kc/nodes/${params.kc}/thread`);
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "The studio service is not reachable.";
  }
  const component =
    selected == null || params.kc == null
      ? null
      : (selected.components.find((item) => item.id === params.kc) ??
        selected.patches.find((item) => item.id === params.kc) ??
        null);
  return (
    <KcCreator
      courses={courses}
      course={selected}
      component={component}
      thread={component ? thread : null}
      model={model}
      error={error}
    />
  );
}
