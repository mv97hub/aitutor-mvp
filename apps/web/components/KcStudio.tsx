import Link from "next/link";

import { CreatorDebugButton, CreatorDebugShell } from "@/components/CreatorDebug";
import { KcBanner } from "@/components/KcBanner";
import { KcBlockScope } from "@/components/KcBlockCanvas";
import { KcCourseHistory } from "@/components/KcCourseHistory";
import { KcCourseList } from "@/components/KcCourseList";
import { KcCourseSettings } from "@/components/KcIntakeForm";
import { NetworkMap } from "@/components/KcNetwork";
import { KcNewCourse } from "@/components/KcNewCourse";
import { KcCourseChat } from "@/components/KcCourseChat";
import { KcCourseTransfer } from "@/components/KcCourseTransfer";
import { KcPipelinePanel } from "@/components/KcPipeline";
import { KcStructureList } from "@/components/KcStructureList";
import type { KcCourse, KcNetwork, KcPipeline, KcStructure } from "@/lib/kc";
import type { PromptTurn } from "@/lib/kc-prompt-log";

export function KcStudio({
  initialCourses,
  initialCourse,
  initialStructure,
  initialNetwork,
  initialPipeline,
  initialModel,
  initialError,
  promptScope,
  promptTurn,
  mode = "wizard",
}: {
  initialCourses: KcCourse[];
  initialCourse: KcCourse | null;
  initialStructure: KcStructure | null;
  initialNetwork: KcNetwork | null;
  initialPipeline: KcPipeline | null;
  initialModel: string;
  initialError: string | null;
  promptScope: string;
  promptTurn: PromptTurn | null;
  mode?: "wizard" | "chat";
}) {
  const course = initialCourse;
  const order = course?.components.map((item) => item.id) ?? [];
  const componentCount = initialStructure?.groups.reduce((sum, group) => sum + group.components.length, 0) ?? 0;
  const syllabus = [course?.intake.standard_text, course?.intake.source_text].filter(Boolean).join("\n");

  return (
    <CreatorDebugShell className="ds-shell studio-shell kc-screen" scope={promptScope} turn={promptTurn}>
      <KcBanner name="KC Course Creator" learnerNav={false}>
        <div className="kc-fast">
          {course ? (
            <KcBlockScope
              courseId={course.id}
              nodeId=""
              model={initialModel}
              allowed={course.allowed_block_types}
              surface="studio"
            />
          ) : null}
          <CreatorDebugButton />
        </div>
      </KcBanner>
      <aside className="ds-side">
        <Link href="/manage-kc-courses" className="studio-manage-link">
          Manage KC courses
        </Link>
        <KcNewCourse />
        <KcCourseList courses={initialCourses} activeId={course?.id ?? null} hrefBase="/kc-studio?course=" />
      </aside>
      <section className="studio-stage kc-course-stage">
        {initialError ? (
          <div className="banner" role="alert">
            <p>{initialError}</p>
          </div>
        ) : null}
        {!course ? (
          <div className="ds-empty">
            <p>Choose a course, or create one.</p>
          </div>
        ) : null}
        {course && initialPipeline ? (
          <>
            <KcCourseSettings course={course} drafted={Boolean(initialPipeline.brief || initialPipeline.blueprint)} />
            <div className="kc-modes" aria-label="Course creator">
              <a href={`/kc-studio?course=${course.id}`} aria-current={mode === "chat" ? undefined : "page"}>
                Wizard
              </a>
              <a href={`/kc-studio?course=${course.id}&mode=chat`} aria-current={mode === "chat" ? "page" : undefined}>
                Chat
              </a>
              <KcCourseTransfer courseId={course.id} title={course.title} audience={course.audience} curriculum={syllabus} />
            </div>
            <div className="studio-columns">
              <div className="studio-tree" aria-label="Course structure">
                <KcStructureList
                  courseId={course.id}
                  structure={initialStructure}
                  patches={course.patches}
                  order={order}
                  mode={mode}
                />
              </div>
              <div className="studio-chat">
                <div className="ds-scroll">
                  <div className="ds-column">
                    {mode === "chat" ? (
                      <KcCourseChat key={course.id} courseId={course.id} model={initialModel} pipeline={initialPipeline} />
                    ) : (
                      <KcPipelinePanel
                        key={course.id}
                        courseId={course.id}
                        model={initialModel}
                        pipeline={initialPipeline}
                        componentCount={componentCount}
                      />
                    )}
                  </div>
                </div>
              </div>
            </div>
            <KcCourseHistory text={course.history ?? ""} />
          </>
        ) : null}
      </section>
      {initialNetwork && course ? (
        <NetworkModal title={course.title} network={initialNetwork} closeHref={`/kc-studio?course=${course.id}`} />
      ) : null}
    </CreatorDebugShell>
  );
}

function NetworkModal({ title, network, closeHref }: { title: string; network: KcNetwork; closeHref: string }) {
  return (
    <div className="kc-modal" role="presentation">
      <div className="kc-modal-card" role="dialog" aria-modal="true" aria-label={`${title} network`}>
        <div className="kc-actions">
          <h2>Network</h2>
          <a href={closeHref}>Close</a>
        </div>
        <p className="ds-quiet">View only. A node is a component. Patches sit at the edge.</p>
        <NetworkMap network={network} />
        <ul className="kc-edge-list">
          {network.edges.map((edge, index) => (
            <li key={index}>
              {edge.from_code} {edge.kind === "prerequisite_of" ? "is a prerequisite of" : "encompasses"} {edge.to_code}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
