import type { ReactNode } from "react";

import { AdminMenu, type AdminSection } from "@/components/admin/AdminMenu";

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
    <main className={`ds-shell ds-desk ds-admin${sidebar ? " has-sidebar" : " no-sidebar"}`}>
      <AdminMenu current={current} />
      {sidebar ? <aside className="ds-side">{sidebar}</aside> : null}
      <section className="ds-work">{children}</section>
    </main>
  );
}
