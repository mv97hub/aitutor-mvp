import Link from "next/link";

import type { MenuSection } from "@/lib/menu-pages";

export function MenuSections({ sections }: { sections: readonly MenuSection[] }) {
  return (
    <nav className="menu-sections" aria-label="Pages">
      {sections.map((section) => (
        <section key={section.id} className="menu-section" aria-labelledby={`menu-${section.id}`}>
          <h2 id={`menu-${section.id}`} className="menu-section-label">
            {section.title}
          </h2>
          <ul className="menu-links">
            {section.links.map((link) => (
              <li key={`${section.id}-${link.href}`}>
                <Link href={link.href} className="ds-top-btn">
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </nav>
  );
}
