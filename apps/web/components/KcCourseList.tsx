"use client";

import { useState } from "react";

export function KcCourseList({
  courses,
  activeId,
  hrefBase,
}: {
  courses: { id: string; title: string; ready: boolean }[];
  activeId: string | null;
  hrefBase: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className="studio-courses-toggle"
        aria-expanded={open}
        aria-controls="kc-course-list"
        onClick={() => setOpen((value) => !value)}
      >
        Courses
        <span aria-hidden="true">{open ? "▴" : "▾"}</span>
      </button>
      <ul id="kc-course-list" className={`studio-courses${open ? " is-open" : ""}`} aria-label="Courses">
        {courses.length === 0 ? <li className="ds-quiet">No courses yet</li> : null}
        {courses.map((item) => (
          <li key={item.id}>
            <a className={`ds-row${activeId === item.id ? " is-on" : ""}`} href={`${hrefBase}${item.id}`}>
              <strong>{item.title}</strong>
              <small>{item.ready ? "Ready" : "Draft"}</small>
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}
