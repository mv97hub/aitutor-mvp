import type { ReactNode } from "react";
import Link from "next/link";

import { AdminMenu, type AdminSection } from "@/components/admin/AdminMenu";
import { BrandMark } from "@/components/BrandMark";

export function AdminFrame({
  current,
  sidebar,
  children,
}: {
  current: AdminSection;
  sidebar?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="ds-shell ds-desk ds-admin">
      <AdminMenu current={current} />
      <aside className="ds-side">
        <div className="ds-logo">
          <BrandMark />
        </div>
        {sidebar}
        <div className="ds-foot">
          <Link className="ds-settings" href="/">Kid session</Link>
        </div>
      </aside>
      <section className="ds-work">{children}</section>
    </main>
  );
}
