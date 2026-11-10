import { MenuSections } from "@/components/MenuSections";
import { menuSectionsFor } from "@/lib/menu-pages";

export const metadata = { title: "Menu · AI Tutor" };

export default async function MenuPage({
  searchParams,
}: {
  searchParams: Promise<{ student?: string | string[] }>;
}) {
  const params = await searchParams;
  const raw = params.student;
  const studentId = Array.isArray(raw) ? raw[0] : raw;
  return (
    <main className="ds-landing menu-page">
      <section className="ds-landing-card">
        <h1>Menu</h1>
        <MenuSections sections={menuSectionsFor(studentId)} />
      </section>
    </main>
  );
}
