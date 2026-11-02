import { AdminFrame } from "@/components/admin/AdminFrame";

export const metadata = { title: "Agent Profiles · AI Tutor" };

export default function AgentProfilesPage() {
  return (
    <AdminFrame current="agents" sidebar={<div className="ds-side-spacer" />}>
      <article className="editor">
        <p className="eyebrow">Administration</p>
        <h2>Agent Profiles</h2>
        <p className="help">Agent profiles are not set up yet.</p>
      </article>
    </AdminFrame>
  );
}
