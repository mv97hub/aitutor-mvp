import Link from "next/link";

import { CreatorDebugButton, CreatorDebugShell } from "@/components/CreatorDebug";
import { KcBanner } from "@/components/KcBanner";
import { KcBlockScope } from "@/components/KcBlockCanvas";
import { KcCourseHistory } from "@/components/KcCourseHistory";
import { KcCourseList } from "@/components/KcCourseList";
import { KcCourseSettings } from "@/components/KcIntakeForm";
import { NetworkMap } from "@/components/KcNetwork";
import { KcNewCourse } from "@/components/KcNewCourse";
import { KcPipelinePanel } from "@/components/KcPipeline";
import { addKcComponent, moveKcComponent, removeKcComponent } from "@/lib/kc-actions";
import { blockSummary } from "@/lib/kc-blocks";
import type { KcComponent, KcCourse, KcNetwork, KcPipeline, KcStructure } from "@/lib/kc";
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
}) {
  const course = initialCourse;
  const order = course?.components.map((item) => item.id) ?? [];

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
            <div className="studio-columns">
              <div className="studio-tree" aria-label="Course structure">
                <StructureView courseId={course.id} structure={initialStructure} patches={course.patches} order={order} />
              </div>
              <div className="studio-chat">
                <div className="ds-scroll">
                  <div className="ds-column">
                    <KcPipelinePanel
                      key={course.id}
                      courseId={course.id}
                      model={initialModel}
                      pipeline={initialPipeline}
                    />
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

function rowStatus(row: { missing: string[]; marked_complete: boolean }) {
  if (row.missing.length) return row.missing.join(", ");
  if (row.marked_complete) return "Marked complete";
  return "Complete";
}

function StructureView({
  courseId,
  structure,
  patches,
  order,
}: {
  courseId: string;
  structure: KcStructure | null;
  patches: KcComponent[];
  order: string[];
}) {
  return (
    <div className="kc-structure">
      <h2>Course structure</h2>
      <ul>
        {structure?.groups.flatMap((group) => group.components).map((row) => (
          <li key={row.id}>
            <a href={`/kc-creator?course=${courseId}&kc=${row.id}`}>
              <strong>{row.title}</strong>
              {row.description ? <p className="kc-brief">{row.description}</p> : null}
              <span>{row.blocks?.length ? blockSummary(row.blocks) : "No blocks yet"}</span>
              <em>{rowStatus(row)}</em>
            </a>
            <span className="kc-row-actions">
              <form action={moveKcComponent}>
                <input type="hidden" name="course_id" value={courseId} />
                <input type="hidden" name="id" value={row.id} />
                <input type="hidden" name="direction" value="-1" />
                {order.map((id) => (
                  <input key={id} type="hidden" name="order" value={id} />
                ))}
                <button className="ghost" type="submit" aria-label={`Move ${row.title} up`}>
                  Up
                </button>
              </form>
              <form action={moveKcComponent}>
                <input type="hidden" name="course_id" value={courseId} />
                <input type="hidden" name="id" value={row.id} />
                <input type="hidden" name="direction" value="1" />
                {order.map((id) => (
                  <input key={id} type="hidden" name="order" value={id} />
                ))}
                <button className="ghost" type="submit" aria-label={`Move ${row.title} down`}>
                  Down
                </button>
              </form>
              <form action={removeKcComponent}>
                <input type="hidden" name="course_id" value={courseId} />
                <input type="hidden" name="id" value={row.id} />
                <button className="ghost" type="submit" aria-label={`Remove ${row.title}`}>
                  Remove
                </button>
              </form>
            </span>
          </li>
        ))}
      </ul>
      {patches.length ? (
        <section>
          <h3>Patches</h3>
          <ul>
            {patches.map((patch) => (
              <li key={patch.id}>
                <a href={`/kc-creator?course=${courseId}&kc=${patch.id}`}>
                  <strong>{patch.title}</strong>
                  {patch.description ? <p className="kc-brief">{patch.description}</p> : null}
                  <span>{patch.blocks?.length ? blockSummary(patch.blocks) : "No blocks yet"}</span>
                  <em>Not a target</em>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <form className="kc-add" action={addKcComponent}>
        <input type="hidden" name="course_id" value={courseId} />
        <label>
          Add a component by title
          <input aria-label="New component title" name="title" required />
        </label>
        <button className="button" type="submit">
          Add
        </button>
      </form>
    </div>
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
