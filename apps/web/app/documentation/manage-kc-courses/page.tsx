import Link from "next/link";

export const metadata = { title: "Manage KC courses · Documentation · AI Tutor" };

export default function ManageKcCoursesDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>Manage KC courses</h1>
        <p>
          Manage KC courses, at <Link href="/manage-kc-courses">/manage-kc-courses</Link>, lists the courses from{" "}
          <Link href="/kc-studio">KC Course Creator</Link>. It uses the same layout as{" "}
          <Link href="/manage-courses">Manage courses</Link>: pick a course, then Delete.
        </p>
        <p>
          Delete asks for the same password as the quest-course delete page. The right password removes that KC course
          and its components. A wrong password leaves the course as it is.
        </p>
        <p>
          The page is linked from the <Link href="/menu">menu</Link> and from the KC Course Creator sidebar.
        </p>
      </article>
    </main>
  );
}
