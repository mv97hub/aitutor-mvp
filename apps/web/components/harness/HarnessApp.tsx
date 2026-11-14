"use client";

import { useState } from "react";

import { KcBanner } from "@/components/KcBanner";
import { ChatTab } from "@/components/harness/ChatTab";
import { ChildrenTab } from "@/components/harness/ChildrenTab";
import { NewRunTab } from "@/components/harness/NewRunTab";
import { ProfilesView, type HarnessPersona } from "@/components/harness/ProfilesView";
import { RecommendationsTab } from "@/components/harness/RecommendationsTab";
import { ResultsTab } from "@/components/harness/ResultsTab";
import { RunsTab } from "@/components/harness/RunsTab";
import type { KcCourse } from "@/lib/kc";
import type { TutorProfile } from "@/lib/types";

const TABS = ["Children", "Profiles", "New run", "Runs", "Chat", "Results", "Recommendations"] as const;

export function HarnessApp({
  personas: initialPersonas,
  courses,
  profiles,
  loadError,
}: {
  personas: HarnessPersona[];
  courses: KcCourse[];
  profiles: TutorProfile[];
  loadError: string | null;
}) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Children");
  const [personas, setPersonas] = useState(initialPersonas);
  const [runId, setRunId] = useState("");
  const [chatId, setChatId] = useState("");

  return (
    <>
      <KcBanner name="AI Test Children" />
      <main className="harness-page">
        {loadError ? <p className="banner">{loadError}</p> : null}
        <div className="kc-prompt-tabs" role="tablist" aria-label="AI Test Children">
          {TABS.map((item) => (
            <button
              key={item}
              type="button"
              className={`kc-prompt-tab${tab === item ? " is-active" : ""}`}
              aria-selected={tab === item}
              onClick={() => setTab(item)}
            >
              {item}
            </button>
          ))}
        </div>
        {tab === "Children" ? <ChildrenTab personas={personas} onChange={setPersonas} /> : null}
        {tab === "Profiles" ? <ProfilesView personas={personas} /> : null}
        {tab === "New run" ? (
          <NewRunTab
            personas={personas}
            courses={courses}
            profiles={profiles}
            onStarted={(id) => {
              setRunId(id);
              setTab("Runs");
            }}
          />
        ) : null}
        {tab === "Runs" ? (
          <RunsTab
            selected={runId}
            onSelect={setRunId}
            onOpenChat={(nextRun, nextChat) => {
              setRunId(nextRun);
              setChatId(nextChat);
              setTab("Chat");
            }}
          />
        ) : null}
        {tab === "Chat" ? <ChatTab chatId={chatId} /> : null}
        {tab === "Results" ? <ResultsTab runId={runId} /> : null}
        {tab === "Recommendations" ? <RecommendationsTab runId={runId} onSelectRun={setRunId} /> : null}
      </main>
    </>
  );
}
