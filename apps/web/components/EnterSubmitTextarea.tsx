"use client";

import type { TextareaHTMLAttributes } from "react";

export function EnterSubmitTextarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      onKeyDown={(event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          event.currentTarget.form?.requestSubmit();
        }
        props.onKeyDown?.(event);
      }}
    />
  );
}
