import { AdminFrame } from "@/components/admin/AdminFrame";

export const metadata = { title: "Tutor Configuration · AI Tutor" };

export default function TutorConfigurationPage() {
  return (
    <AdminFrame current="tutor" sidebar={<div className="ds-side-spacer" />}>
      <article className="editor">
        <p className="eyebrow">Administration</p>
        <h2>Tutor Configuration</h2>
        <p className="help">Tutor configuration is not set up yet.</p>
      </article>
    </AdminFrame>
  );
}
