import { AgentCustomizations } from "@/components/admin/AgentCustomizations";

export const dynamic = "force-dynamic";

export const metadata = { title: "AI Tutor Configuration · AI Tutor" };

export default function TutorConfigurationPage() {
  return <AgentCustomizations />;
}
