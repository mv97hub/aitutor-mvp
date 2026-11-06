"use client";

import type { TextareaHTMLAttributes } from "react";

export function EnterSubmitTextarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      onKeyDown={(event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          const field = event.currentTarget;
          const form = field.form;
          const send = form?.querySelector("button.ds-send");
          if (form && !field.disabled && !(send instanceof HTMLButtonElement && send.disabled)) {
            form.requestSubmit();
          }
        }
        props.onKeyDown?.(event);
      }}
    />
  );
}
