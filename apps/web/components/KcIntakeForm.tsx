"use client";

import { useRef, useState } from "react";

import { markKcReady, saveKcCourse } from "@/lib/kc-actions";
import { AUDIENCES, COURSE_USES, DEPTHS, KINDS, READING_LEVELS, type KcCourse } from "@/lib/kc";
import { CURRICULA, curriculumOf, STANDARD_EXAMPLE } from "@/lib/kc-standards";

/** The course intake. Required answers come first. A standard is optional and can be pasted. */
export function KcCourseSettings({ course, drafted }: { course: KcCourse; drafted: boolean }) {
  const [kind, setKind] = useState(course.kind);
  const [standard, setStandard] = useState(course.intake.standard || "");
  const help = useRef<HTMLDialogElement>(null);
  const intake = course.intake;
  const chosen = curriculumOf(standard);

  return (
    <form className="studio-prefs" action={saveKcCourse}>
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
      {drafted ? <p className="ds-quiet">Changing these answers starts the draft over.</p> : null}
      <div className="studio-grid">
        <label>
          Topic
          <input aria-label="Course name" name="title" defaultValue={course.title} required />
        </label>
        <label>
          Age band
          <select aria-label="Audience" name="audience" defaultValue={course.audience}>
            {AUDIENCES.map((band) => (
              <option key={band}>{band}</option>
            ))}
          </select>
        </label>
        <label>
          Reading level
          <select aria-label="Reading level" name="reading_level" defaultValue={intake.reading_level}>
            {READING_LEVELS.map((level) => (
              <option key={level.id} value={level.id}>
                {level.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Depth
          <select aria-label="Depth" name="depth" defaultValue={intake.depth}>
            {DEPTHS.map((depth) => (
              <option key={depth.id} value={depth.id}>
                {depth.label}
              </option>
            ))}
          </select>
        </label>
        <label className="studio-span">
          By the end the child can
          <textarea
            aria-label="Course description"
            name="description"
            defaultValue={course.description}
            rows={2}
            placeholder="One sentence, in the form: by the end the child can..."
          />
        </label>
        <label>
          Exact component count, optional
          <input
            aria-label="Component count"
            name="component_count"
            inputMode="numeric"
            defaultValue={intake.component_count ?? ""}
            placeholder="Leave blank to use the depth"
          />
        </label>
        <label>
          Kind
          <select
            aria-label="Kind"
            name="kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as KcCourse["kind"])}
          >
            {KINDS.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        {kind === "time_boxed" ? (
          <label>
            Minutes
            <input aria-label="Minutes" name="minutes" inputMode="numeric" defaultValue={course.minutes ?? ""} />
          </label>
        ) : (
          <input type="hidden" name="minutes" value="" />
        )}
        <label>
          Standard, optional
          <select
            aria-label="Standard"
            name="standard"
            value={standard}
            onChange={(event) => setStandard(event.target.value)}
          >
            {CURRICULA.map((item) => (
              <option key={item.id || "none"} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        {standard ? (
          <>
            <label>
              Grade or year
              <input
                aria-label="Grade or year"
                name="standard_grade"
                defaultValue={intake.standard_grade}
                required
                placeholder="For example, 3 or Year 4"
              />
            </label>
            {standard === "other" ? (
              <label className="studio-span">
                Name of the standard
                <input aria-label="Name of the standard" name="standard_name" defaultValue={intake.standard_name} required />
              </label>
            ) : (
              <input type="hidden" name="standard_name" value="" />
            )}
            <label className="studio-span">
              Standard statements, optional
              <textarea
                aria-label="Standard statements"
                name="standard_text"
                defaultValue={intake.standard_text}
                rows={6}
                placeholder="One statement per line, with its code in front if it has one"
              />
            </label>
            <div className="studio-span kc-standard-note">
              <p>
                Pasted text is preferred and is used as written. If you leave this blank, the model recalls the
                statements for this grade and topic. Recalled standards should be checked before the blueprint.
              </p>
              <button className="ghost" type="button" onClick={() => help.current?.showModal()}>
                How to get this
              </button>
              <dialog ref={help} className="kc-standard-help">
                <h2>How to get this</h2>
                {chosen.host ? (
                  <p>
                    Go to the official standards site for {chosen.label}:{" "}
                    <a href={chosen.site} target="_blank" rel="noreferrer">
                      {chosen.host}
                    </a>
                    .
                  </p>
                ) : (
                  <p>Use the official site for the curriculum you named. This option has no single site to link.</p>
                )}
                <ol>
                  <li>Copy the statements for one grade and one topic, not the whole subject.</li>
                  <li>Paste them as a list: one statement per line, with its code in front if it has one.</li>
                </ol>
                <p>Sample, not a real course:</p>
                <pre>{STANDARD_EXAMPLE}</pre>
                <div className="kc-pipeline-actions">
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => {
                      const write = navigator.clipboard?.writeText(STANDARD_EXAMPLE);
                      if (write) void write.catch(() => undefined);
                    }}
                  >
                    Copy the sample
                  </button>
                  <button className="button" type="button" onClick={() => help.current?.close()}>
                    Close
                  </button>
                </div>
                <p>Keep it to the statements the course should cover, usually 5 to 20 lines. A whole-subject paste makes the course too broad.</p>
              </dialog>
            </div>
          </>
        ) : (
          <>
            <input type="hidden" name="standard_grade" value="" />
            <input type="hidden" name="standard_name" value="" />
            <input type="hidden" name="standard_text" value="" />
          </>
        )}
        <label>
          How it will be used, optional
          <select aria-label="How it will be used" name="use" defaultValue={intake.use}>
            {COURSE_USES.map((item) => (
              <option key={item.id || "unset"} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="studio-span">
          Starting point, optional
          <input
            aria-label="Starting point"
            name="starting_point"
            defaultValue={intake.starting_point}
            placeholder="None, some, or what the child can already do"
          />
        </label>
        <label>
          Must cover, optional
          <input aria-label="Must cover" name="must_cover" defaultValue={intake.must_cover} />
        </label>
        <label>
          Must avoid, optional
          <input aria-label="Must avoid" name="must_avoid" defaultValue={intake.must_avoid} />
        </label>
        <label>
          Interests for real-world hooks, optional
          <input aria-label="Interests" name="interests" defaultValue={intake.interests} />
        </label>
        <label>
          Misconceptions you have seen, optional
          <input
            aria-label="Misconceptions"
            name="misconceptions_seen"
            defaultValue={intake.misconceptions_seen}
          />
        </label>
        <label className="studio-span">
          Source text, optional
          <textarea aria-label="Source text" name="source_text" defaultValue={intake.source_text} rows={4} />
        </label>
      </div>
    </form>
  );
}
