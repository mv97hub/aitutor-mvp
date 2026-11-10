import Link from "next/link";
import type { ReactNode } from "react";

import { BrandMark } from "@/components/BrandMark";

const BANNER_NAV_LINKS = [
  { href: "/kc-tutor", label: "KC Tutor", match: "KC Tutor" },
  { href: "/kc-progress", label: "KC Progress", match: "KC Course Progress" },
  { href: "/kc-studio", label: "KC Course Creator", match: "KC Course Creator" },
  { href: "/kc-creator", label: "KC Creator", match: "KC Creator" },
  { href: "/admin", label: "Administration", match: "Administration" },
] as const;

export function KcBanner({ name, children }: { name: string; children?: ReactNode }) {
  return (
    <header className="kc-banner">
      <BrandMark />
      <h1>{name}</h1>
      <nav className="kc-banner-nav" aria-label="Primary navigation">
        {BANNER_NAV_LINKS.map((item) => {
          const isCurrent = name === item.match;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`ds-top-btn is-on-banner${isCurrent ? " is-active" : ""}`}
              aria-current={isCurrent ? "page" : undefined}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </header>
  );
}
