"use client";

import { useEffect, useState, useTransition, type Ref } from "react";
import { useRouter } from "next/navigation";
import { useFormStatus } from "react-dom";

import { EnterSubmitTextarea } from "@/components/EnterSubmitTextarea";
import { KcModelSelect } from "@/components/KcModelSelect";
import { postKcCreatorMessage } from "@/lib/kc-actions";

function WorkingNote({ pending }: { pending: boolean }) {
  if (!pending) return null;
  return <p className="ds-typing">Writing…</p>;
}

export function KcStudioComposer({ courseId, model }: { courseId: string; model: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [locked, setLocked] = useState(false);
  const working = locked || pending;

  useEffect(() => {
    if (!pending) setLocked(false);
  }, [pending]);

  return (
    <form
      className="ds-composer-seat"
      onSubmit={(event) => {
        event.preventDefault();
        if (working) return;
        const data = new FormData(event.currentTarget);
        const params = new URLSearchParams();
        params.set("course", courseId);
        params.set("message", String(data.get("message") || "").trim());
        params.set("model", String(data.get("model") || model));
        setLocked(true);
        startTransition(() => {
          router.push(`/kc-studio?${params.toString()}`);
        });
      }}
    >
      <WorkingNote pending={working} />
      <div className="ds-card">
        <EnterSubmitTextarea
          className="ds-draft"
          aria-label="Studio chat"
          name="message"
          rows={1}
          required
          disabled={working}
          placeholder="Ask for a component list"
        />
        <div className="ds-card-row kc-model-row">
          <KcModelSelect value={model} />
          <button className="ds-send" type="submit" aria-label="Send" disabled={working}>
            ↑
          </button>
        </div>
      </div>
    </form>
  );
}

function CreatorFields({ model }: { model: string }) {
  const { pending } = useFormStatus();
  return (
    <>
      <WorkingNote pending={pending} />
      <div className="ds-card">
        <EnterSubmitTextarea
          className="ds-draft"
          name="message"
          rows={1}
          required
          disabled={pending}
          placeholder="Ask about this component"
          aria-label="Component chat"
          maxLength={8000}
        />
        <div className="ds-card-row kc-model-row">
          <KcModelSelect value={model} />
          <button className="ds-send" type="submit" aria-label="Send" disabled={pending}>
            ↑
          </button>
        </div>
      </div>
    </>
  );
}

export function KcCreatorComposer({
  courseId,
  nodeId,
  model,
  formRef,
}: {
  courseId: string;
  nodeId: string;
  model: string;
  formRef?: Ref<HTMLFormElement>;
}) {
  return (
    <form className="ds-composer-seat" action={postKcCreatorMessage} ref={formRef}>
      <input type="hidden" name="course_id" value={courseId} />
      <input type="hidden" name="node_id" value={nodeId} />
      <CreatorFields model={model} />
    </form>
  );
}
