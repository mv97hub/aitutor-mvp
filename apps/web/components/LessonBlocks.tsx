"use client";

import { useEffect, useState } from "react";

import type { BlockStep, KidQuiz } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  engage: "Engage",
  try: "Try",
  name: "Name",
  show: "Show",
  teach_back: "Teach back",
};

export function BlockStepper({ steps }: { steps: BlockStep[] }) {
  return (
    <ol className="block-map" aria-label="Blocks in this class">
      {steps.map((step) => (
        <li key={step.id} className={`block-pip is-${step.state}`} aria-current={step.state === "current" ? "step" : undefined}>
          <span className="block-index">{step.position}</span>
          <span>
            <strong>{KIND_LABEL[step.kind] ?? step.kind}</strong>
            <span className="quiet">{step.title}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

export function ChoiceWidget({
  quiz,
  busy,
  onSubmit,
}: {
  quiz: KidQuiz;
  busy: boolean;
  onSubmit: (choice: string | string[], explanation: string, transcript: string) => void;
}) {
  const [picked, setPicked] = useState<string[]>([]);
  const [order, setOrder] = useState(quiz.choices.map((choice) => choice.id));
  const [explanation, setExplanation] = useState("");

  useEffect(() => {
    setPicked([]);
    setOrder(quiz.choices.map((choice) => choice.id));
    setExplanation("");
  }, [quiz]);

  function move(index: number, direction: -1 | 1) {
    const next = index + direction;
    if (next < 0 || next >= order.length) return;
    const copy = [...order];
    const [item] = copy.splice(index, 1);
    copy.splice(next, 0, item);
    setOrder(copy);
  }

  function submit() {
    const note = explanation.trim();
    if (quiz.type === "order") {
      const labels = order.map((id) => quiz.choices.find((choice) => choice.id === id)?.text ?? id);
      onSubmit(order, note, labels.join(" → ") + (note ? `\n${note}` : ""));
      return;
    }
    const ids = quiz.type === "multi" ? picked : picked.slice(0, 1);
    if (ids.length === 0) return;
    const labels = ids.map((id) => quiz.choices.find((choice) => choice.id === id)?.text ?? id);
    onSubmit(quiz.type === "multi" ? ids : ids[0], note, labels.join(", ") + (note ? `\n${note}` : ""));
  }

  const ready = quiz.type === "order" || picked.length > 0;
  return (
    <form
      className="widget"
      onSubmit={(event) => {
        event.preventDefault();
        if (!ready || busy) return;
        submit();
      }}
    >
      <p className="eyebrow">{quiz.type === "flaw" ? "Spot the flaw" : quiz.type === "order" ? "Put in order" : quiz.type === "multi" ? "Select all that fit" : "Choose one"}</p>
      <p className="widget-prompt">{quiz.prompt}</p>
      {quiz.type === "order" ? (
        <ol className="order-list">
          {order.map((id, index) => {
            const choice = quiz.choices.find((item) => item.id === id);
            return (
              <li key={id}>
                <span>{choice?.text}</span>
                <span className="row-actions">
                  <button type="button" className="ghost" disabled={busy || index === 0} onClick={() => move(index, -1)}>Up</button>
                  <button type="button" className="ghost" disabled={busy || index === order.length - 1} onClick={() => move(index, 1)}>Down</button>
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <div className="choice-list" role="group" aria-label={quiz.prompt}>
          {quiz.choices.map((choice) => {
            const on = picked.includes(choice.id);
            return (
              <label key={choice.id} className={`widget-choice ${on ? "is-on" : ""}`}>
                <input
                  type={quiz.type === "multi" ? "checkbox" : "radio"}
                  name="widget-choice"
                  checked={on}
                  disabled={busy}
                  onChange={() => {
                    if (quiz.type === "multi") {
                      setPicked((current) => (on ? current.filter((id) => id !== choice.id) : [...current, choice.id]));
                    } else {
                      setPicked([choice.id]);
                    }
                  }}
                />
                <span>{choice.text}</span>
              </label>
            );
          })}
        </div>
      )}
      {quiz.explain ? (
        <label>
          Why?
          <textarea
            value={explanation}
            onChange={(event) => setExplanation(event.target.value)}
            maxLength={2000}
            disabled={busy}
            placeholder="A short reason"
          />
        </label>
      ) : null}
      <button className="button" type="submit" disabled={busy || !ready}>
        Check
      </button>
    </form>
  );
}
