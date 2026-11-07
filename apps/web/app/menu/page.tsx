import Link from "next/link";

import { kcAndAdminPages, olderPages } from "@/lib/menu-pages";

export const metadata = { title: "Menu · AI Tutor" };

export default function MenuPage() {
  return (
    <main className="ds-landing">
      <section className="ds-landing-card">
        <h1>Menu</h1>
        <nav aria-label="Pages">
          <ul>
            {kcAndAdminPages.map((page) => (
              <li key={page.href}>
                <Link href={page.href}>{page.label}</Link>
              </li>
            ))}
          </ul>
          <ul className="menu-older">
            {olderPages.map((page) => (
              <li key={page.href}>
                <Link href={page.href}>{page.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
      </section>
    </main>
  );
}
