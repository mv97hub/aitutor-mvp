import Link from "next/link";

import { KcBanner } from "@/components/KcBanner";
import { KcCourseList } from "@/components/KcCourseList";
import { NetworkMap } from "@/components/KcNetwork";
import { KcNewCourse } from "@/components/KcNewCourse";
import { KcStudioComposer } from "@/components/KcComposer";
import {
  addKcComponent,
  markKcReady,
  moveKcComponent,
  pushKcDraft,
  removeKcComponent,
  saveKcCourse,
} from "@/lib/kc-actions";
import {
  AUDIENCES,
  KINDS,
  TYPE_LABELS,
  type KcComponent,
  type KcCourse,
  type KcDraft,
  type KcNetwork,
  type KcStructure,
} from "@/lib/kc";

export function KcStudio({
  initialCourses,
  initialCourse,
  initialStructure,
  initialNetwork,
  initialDraft,
  initialReply,
  initialMessage,
  initialModel,
  initialError,
}: {
  initialCourses: KcCourse[];
  initialCourse: KcCourse | null;
  initialStructure: KcStructure | null;
  initialNetwork: KcNetwork | null;
  initialDraft: KcDraft | null;
  initialReply: string;
  initialMessage: string;
  initialModel: string;
  initialError: string | null;
}) {
  const course = initialCourse;
  const order = course?.components.map((item) => item.id) ?? [];
  const courseDraft = initialDraft?.kind === "course" ? initialDraft : null;

  return (
    <main className="ds-shell studio-shell kc-screen">
      <KcBanner name="KC Course Creator" />
      <aside className="ds-side">
        <Link href="/manage-kc-courses" className="studio-manage-link">
          Manage KC courses
        </Link>
        <KcNewCourse />
        <KcCourseList
          courses={initialCourses}
          activeId={course?.id ?? null}
          hrefBase="/kc-studio?course="
        />
      </aside>
      <section className="studio-stage kc-course-stage">
        {initialError ? (
          <div className="banner" role="alert">
            <p>{initialError}</p>
          </div>
        ) : null}
        {!course ? <div className="ds-empty"><p>Choose a course, or create one.</p></div> : null}
        {course ? (
          <>
            <form className="studio-prefs" action={saveKcCourse} key={course.id}>
              <input type="hidden" name="course_id" value={course.id} />
              <div className="studio-prefs-head">
                <div className="studio-prefs-title">
                  <h1>
                    <span className="studio-code">{course.code}</span>
                    {course.title}
                    <span className="studio-draft">{course.ready ? "Ready" : "Draft"}</span>
                  </h1>
                </div>
                <div className="studio-prefs-actions">
                  <button className="button" type="submit">
                    Save course
                  </button>
                  <a className="ghost" href={`/kc-studio?course=${course.id}&network=1`}>
                    Network
                  </a>
                  <button type="submit" formAction={markKcReady}>
                    {course.ready ? "Ready" : "Mark ready"}
                  </button>
                </div>
              </div>
              <div className="studio-grid">
                <label>
                  Name
                  <input aria-label="Course name" name="title" defaultValue={course.title} required />
                </label>
                <label>
                  Audience
                  <select aria-label="Audience" name="audience" defaultValue={course.audience}>
                    {AUDIENCES.map((band) => (
                      <option key={band}>{band}</option>
                    ))}
                  </select>
                </label>
                <label className="studio-span">
                  What the kid should come away able to do
                  <textarea aria-label="Course description" name="description" defaultValue={course.description} rows={3} />
                </label>
                <label>
                  Kind
                  <select aria-label="Kind" name="kind" defaultValue={course.kind}>
                    {KINDS.map((kind) => (
                      <option key={kind.id} value={kind.id}>
                        {kind.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Minutes, optional
                  <input aria-label="Minutes" name="minutes" inputMode="numeric" defaultValue={course.minutes ?? ""} />
                </label>
              </div>
            </form>
            <HistoryLog label="Course history" text={course.history ?? ""} />
            <div className="studio-columns">
              <div className="studio-tree" aria-label="Course structure">
                <StructureView
                  courseId={course.id}
                  structure={initialStructure}
                  patches={course.patches}
                  order={order}
                />
              </div>
              <div className="studio-chat">
                <div className="ds-scroll">
                  <div className="ds-column">
                    {!initialMessage ? (
                      <p className="ds-quiet">
                        The draft names the subject and its major ideas, then the component list.
                        Each component gets an outline, topics, and goals. Nothing is stored until you push it.
                      </p>
                    ) : null}
                    {initialMessage ? (
                      <div className="bubble user">
                        <p>{initialMessage}</p>
                      </div>
                    ) : null}
                    {initialReply ? (
                      <div className="bubble assistant">
                        <p className="kc-reply">{initialReply}</p>
                      </div>
                    ) : null}
                    {courseDraft ? (
                      <ol className="kc-draft-list" aria-label="Draft component list">
                        {courseDraft.components.map((item) => (
                          <li key={item.code}>
                            <strong>{item.title}</strong> <span className="studio-code">{item.code}</span>
                            {item.description ? <p className="kc-brief">{item.description}</p> : null}
                          </li>
                        ))}
                      </ol>
                    ) : null}
                  </div>
                </div>
                {courseDraft ? (
                  <form action={pushKcDraft}>
                    <input type="hidden" name="course_id" value={course.id} />
                    <input type="hidden" name="kind" value="course" />
                    <input type="hidden" name="components" value={JSON.stringify(courseDraft.components)} />
                    <button className="button studio-push" type="submit">
                      Push draft
                    </button>
                  </form>
                ) : null}
                <KcStudioComposer
                  key={`${initialMessage}\n${initialReply}\n${initialError ?? ""}`}
                  courseId={course.id}
                  model={initialModel}
                />
              </div>
            </div>
          </>
        ) : null}
      </section>
      {initialNetwork && course ? (
        <NetworkModal title={course.title} network={initialNetwork} closeHref={`/kc-studio?course=${course.id}`} />
      ) : null}
    </main>
  );
}

function HistoryLog({ label, text }: { label: string; text: string }) {
  return (
    <section className="kc-history">
      <h3>{label}</h3>
      <pre aria-label={label}>{text.trim() ? text : "No history yet."}</pre>
    </section>
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
      {structure?.groups.map((group) => (
        <section key={group.kc_type}>
          <h3>{TYPE_LABELS[group.kc_type] ?? group.kc_type}</h3>
          <ul>
            {group.components.map((row) => (
              <li key={row.id}>
                <a href={`/kc-creator?course=${courseId}&kc=${row.id}`}>
                  <strong>{row.title}</strong>
                  {row.description ? <p className="kc-brief">{row.description}</p> : null}
                  <span>{TYPE_LABELS[row.kc_type ?? "unset"]}</span>
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
        </section>
      ))}
      {patches.length ? (
        <section>
          <h3>Patches</h3>
          <ul>
            {patches.map((patch) => (
              <li key={patch.id}>
                <a href={`/kc-creator?course=${courseId}&kc=${patch.id}`}>
                  <strong>{patch.title}</strong>
                  {patch.description ? <p className="kc-brief">{patch.description}</p> : null}
                  <span>{TYPE_LABELS[patch.kc_type ?? "unset"]}</span>
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
