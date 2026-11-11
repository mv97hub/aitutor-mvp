"use client";

import { type Ref } from "react";
import { useFormStatus } from "react-dom";

import { EnterSubmitTextarea } from "@/components/EnterSubmitTextarea";
import { KcModelSelect } from "@/components/KcModelSelect";
import { postKcCreatorMessage } from "@/lib/kc-actions";

function WorkingNote({ pending }: { pending: boolean }) {
  if (!pending) return null;
  return <p className="ds-typing">Writing…</p>;
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
  allowedBlockTypes = [],
}: {
  courseId: string;
  nodeId: string;
  model: string;
  formRef?: Ref<HTMLFormElement>;
  allowedBlockTypes?: string[];
}) {
  return (
    <form className="ds-composer-seat" action={postKcCreatorMessage} ref={formRef}>
      <input type="hidden" name="course_id" value={courseId} />
      <input type="hidden" name="node_id" value={nodeId} />
      <input type="hidden" name="allowed_block_types" value={allowedBlockTypes.join(",")} />
      <CreatorFields model={model} />
    </form>
  );
}
