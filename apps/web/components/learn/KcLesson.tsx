"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ChoiceWidget } from "@/components/LessonBlocks";
import type { TutorMood } from "@/components/learn/LearnQuestPanel";
import { TutorAvatar } from "@/components/TutorAvatar";
import type { KcTutorSession } from "@/lib/kc";
import { goalStartActions } from "@/lib/kc-goal-start";
import { choiceShowing, lessonComposerVisible, quizFor } from "@/lib/learn-mobile";
import { blockStepDivider, starBurst } from "@/lib/learn";
import type { TutorProfile } from "@/lib/types";

function isTyping(element: HTMLElement) {
  if (element.isContentEditable) return true;
  return element.tagName === "INPUT" || element.tagName === "TEXTAREA" || element.tagName === "SELECT";
}

export function KcLesson({
  session,
  model,
  activeTutor,
  learnMode = false,
  onActivity,
  nextTopic = null,
  homeHref = "/learn",
  topicCompleteStars = 0,
  topicStrength = "You finished this topic.",
  onOpenTopic,
  courseDone = false,
  hideComposerWhileChoosing = false,
}: {
  session: KcTutorSession;
  model: string;
  activeTutor: TutorProfile;
  learnMode?: boolean;
  onActivity?: (mood: TutorMood) => void;
  nextTopic?: { id: string; title: string } | null;
  homeHref?: string;
  topicCompleteStars?: number;
  topicStrength?: string;
  onOpenTopic?: (kcId: string) => void;
  courseDone?: boolean;
  hideComposerWhileChoosing?: boolean;
}) {
  const router = useRouter();
  const routerRef = useRef(router);
  routerRef.current = router;
  const started = useRef("");
  const threadRef = useRef<HTMLDivElement>(null);
  const draftRef = useRef<HTMLTextAreaElement>(null);
  const sending = useRef(false);
  const awaitingReply = useRef(false);
  const [draft, setDraft] = useState("");
  const [speakError, setSpeakError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [speaking, setSpeaking] = useState(false);
  const [answering, setAnswering] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);
  const [pendingLine, setPendingLine] = useState<{ text: string; priorMatches: number } | null>(null);
  const [settled, setSettled] = useState<{ anchorId: string; ids: string[]; note: string } | null>(null);
  const [burst, setBurst] = useState<{ award: number; firstTry: boolean; revealed: boolean } | null>(null);
  const seenBlocks = useRef<string[] | null>(null);
  const anchor = [...session.messages].reverse().find((message) => message.role === "assistant");
  const quiz = session.choice ? quizFor(session.choice) : null;
  const activeSettled = settled && anchor && settled.anchorId === anchor.id ? settled : null;
  const choosing = choiceShowing({
    hasChoice: quiz !== null,
    status: session.status,
    needsSpeech: session.needs_speech,
    settled: activeSettled !== null,
  });
  const latestMessageId = session.messages[session.messages.length - 1]?.id ?? "";
  const composerOpen = session.status !== "completed" && !session.needs_speech;
  const showComposer = lessonComposerVisible({
    status: session.status,
    needsSpeech: session.needs_speech,
    choosing,
    hideWhileChoosing: hideComposerWhileChoosing,
  });
  const goalActions = goalStartActions({
    status: session.status,
    needsSpeech: session.needs_speech,
    blockType: session.active_block_type,
    substep: session.active_substep,
    choosing,
  });
  const echoedMatches = pendingLine
    ? session.messages.filter((message) => message.role === "user" && message.content === pendingLine.text).length
    : 0;
  const showPendingLine = pendingLine !== null && echoedMatches <= pendingLine.priorMatches;

  function focusDraft() {
    const field = draftRef.current;
    if (!field || field.disabled) return;
    field.focus({ preventScroll: true });
  }

  useLayoutEffect(() => {
    const node = threadRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [latestMessageId, session.messages.length, pendingLine]);

  useEffect(() => {
    if (!composerOpen || choosing) return;
    const active = document.activeElement;
    if (active instanceof HTMLElement && active !== document.body && active !== draftRef.current && isTyping(active)) return;
    focusDraft();
  }, [composerOpen, choosing]);

  useEffect(() => {
    if (answering) {
      awaitingReply.current = true;
      return;
    }
    if (!awaitingReply.current) return;
    awaitingReply.current = false;
    const field = draftRef.current;
    if (!field || field.disabled) return;
    const active = document.activeElement;
    if (active instanceof HTMLElement && active !== field && active !== document.body && isTyping(active)) return;
    field.focus({ preventScroll: true });
  }, [answering]);

  useEffect(() => {
    if (!session.needs_speech) {
      setSpeaking(false);
      return;
    }
    // Message count is omitted: a new line must not abort the intro and start it again.
    const key = `${session.id}:${session.step}:${attempt}:${model}`;
    if (started.current === key) return;
    started.current = key;
    const controller = new AbortController();
    let cancelled = false;
    setSpeaking(true);
    setSpeakError(null);
    void fetch("/api/kc/tutor/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: session.id, model }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = (await response.text()).trim();
          throw new Error(text || "The tutor could not say this step.");
        }
        if (!cancelled) routerRef.current.refresh();
      })
      .catch((err: unknown) => {
        if (cancelled || (err instanceof DOMException && err.name === "AbortError")) return;
        setSpeakError(err instanceof Error ? err.message : "The tutor could not say this step.");
      })
      .finally(() => {
        if (!cancelled) setSpeaking(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
      if (started.current === key) started.current = "";
    };
  }, [attempt, model, session.id, session.needs_speech, session.step]);

  useEffect(() => {
    if (!learnMode) return;
    const blocks = session.block_progress ?? [];
    if (seenBlocks.current === null) {
      seenBlocks.current = blocks.filter((block) => block.status === "completed").map((block) => block.id);
      return;
    }
    const result = starBurst(seenBlocks.current, blocks);
    seenBlocks.current = result.seen;
    if (result.award <= 0) return;
    setBurst({ award: result.award, firstTry: result.firstTry, revealed: result.revealed });
    const timer = window.setTimeout(() => setBurst(null), 2200);
    return () => window.clearTimeout(timer);
  }, [learnMode, session.block_progress]);

  useEffect(() => {
    if (!learnMode || !onActivity) return;
    if (speaking || answering) {
      onActivity("thinking");
      return;
    }
    if (burst?.firstTry) {
      onActivity("first_try");
      return;
    }
    const active = (session.block_progress ?? []).find((block) => block.status === "active");
    onActivity(active && (active.attempts ?? 0) > 0 ? "retry" : "ready");
  }, [answering, burst, learnMode, onActivity, session.block_progress, speaking]);

  async function sendAnswer(answer: string) {
    const cleaned = answer.trim();
    if (!cleaned || sending.current) return;
    const priorMatches = session.messages.filter((message) => message.role === "user" && message.content === cleaned).length;
    sending.current = true;
    setAnswering(true);
    setReplyError(null);
    setPendingLine({ text: cleaned, priorMatches });
    setDraft("");
    focusDraft();
    try {
      const response = await fetch("/api/kc/tutor/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: session.id, answer: cleaned, model }),
      });
      if (!response.ok) {
        const text = (await response.text()).trim();
        throw new Error(text || "The tutor could not answer.");
      }
      router.refresh();
    } catch (err: unknown) {
      setSettled(null);
      setPendingLine(null);
      setDraft((current) => (current.trim() ? current : cleaned));
      setReplyError(err instanceof Error ? err.message : "The tutor could not answer.");
    } finally {
      sending.current = false;
      setAnswering(false);
    }
  }

  return (
    <div className={learnMode ? "kc-lesson cb-lesson" : "kc-lesson"}>
      {burst ? (
        <p className="learn-star-burst" role="status">
          +{burst.award} ★
          {burst.firstTry ? " · first try" : ""}
          {burst.revealed && !burst.firstTry ? " · Guided Walkthrough Complete" : ""}
        </p>
      ) : null}
      <div ref={threadRef} className={learnMode ? "ds-scroll cb-thread" : "ds-scroll"} role="log" aria-live="polite" aria-relevant="additions">
        <div className="ds-column">
          {learnMode && (session.completed_blocks ?? 0) === 0 && session.status !== "completed" ? (
            <article className="learn-topic-banner">
              <TutorAvatar
                preset={session.avatar_preset || activeTutor.avatar_preset}
                avatarUrl={session.avatar_url ?? activeTutor.avatar_url}
                name={session.tutor_name || activeTutor.name}
                size="md"
              />
              <div>
                <strong>{session.tutor_name || activeTutor.name || "Your tutor"} is ready</strong>
                <p>Let&apos;s explore {session.title}, one step at a time.</p>
              </div>
            </article>
          ) : null}
          {session.messages.map((message, index) => {
            const previous = index > 0 ? session.messages[index - 1] : undefined;
            const divider = blockStepDivider(
              index === 0 ? undefined : previous?.step,
              index === 0 ? (message.step ?? 0) : message.step,
              session.block_progress,
              session.total_blocks,
            );
            return (
              <div key={message.id}>
              {divider ? (
                <div className="kc-step-divider">
                  <span>{divider}</span>
                </div>
              ) : null}
              <div
                className={
                  learnMode
                    ? `cb-msg ${message.role === "user" ? "is-student" : "is-tutor"}`
                    : `bubble ${message.role === "user" ? "user" : "assistant"}`
                }
              >
                {learnMode && message.role === "assistant" ? (
                  <span className="cb-avatar is-yellow" aria-hidden="true">
                    {(session.tutor_name || activeTutor.name || "T").slice(0, 1).toUpperCase()}
                  </span>
                ) : null}
                {learnMode ? (
                  <div className="cb-bubble">
                    <p>{message.content}</p>
                  </div>
                ) : (
                  <>
                    {message.role === "assistant" ? (
                      <div className="bubble-tutor-head">
                        <TutorAvatar
                          preset={session.avatar_preset || activeTutor.avatar_preset}
                          avatarUrl={session.avatar_url ?? activeTutor.avatar_url}
                          name={session.tutor_name || activeTutor.name || "Default"}
                          size="sm"
                        />
                        <strong className="bubble-tutor-name">
                          {session.tutor_name || activeTutor.name || "Default"}
                        </strong>
                      </div>
                    ) : null}
                    <p>{message.content}</p>
                  </>
                )}
              </div>
              {quiz && anchor?.id === message.id ? (
                <article
                  className="bubble assistant widget-message"
                  aria-label={activeSettled ? "Your choice" : "Choose an answer"}
                >
                  <ChoiceWidget
                    quiz={quiz}
                    busy={answering}
                    settled={activeSettled}
                    onSubmit={(choice, explanation, transcript) => {
                      const ids = Array.isArray(choice) ? choice : [choice];
                      setSettled({ anchorId: message.id, ids, note: explanation });
                      void sendAnswer(transcript);
                    }}
                  />
                </article>
              ) : null}
              </div>
            );
          })}
          {showPendingLine && pendingLine ? (
            learnMode ? (
              <div className="cb-msg is-student">
                <div className="cb-bubble">
                  <p>{pendingLine.text}</p>
                </div>
              </div>
            ) : (
              <div className="bubble user">
                <p>{pendingLine.text}</p>
              </div>
            )
          ) : null}
          {learnMode && session.status === "completed" ? (
            <article className="learn-next-card">
              <p>Topic complete! · ★ {topicCompleteStars}</p>
              <p>{topicStrength}</p>
              {nextTopic ? (
                <button type="button" className="learn-btn primary" onClick={() => onOpenTopic?.(nextTopic.id)}>
                  Continue to Next Topic → {nextTopic.title}
                </button>
              ) : courseDone ? (
                <a className="learn-btn primary" href={homeHref}>
                  Course complete! View my trophy card →
                </a>
              ) : (
                <p>The next topic opens when this one is finished.</p>
              )}
            </article>
          ) : null}
        </div>
      </div>
      {speaking || answering ? <p className="ds-typing">{learnMode ? "Tutor is thinking…" : "Tutor is writing…"}</p> : null}
      {speakError ? (
        <div className="banner" role="alert">
          <p>{speakError}</p>
          <button type="button" className="ghost" onClick={() => setAttempt((value) => value + 1)}>
            Try again
          </button>
        </div>
      ) : null}
      {replyError ? (
        <div className="banner" role="alert">
          <p>{replyError}</p>
        </div>
      ) : null}
      {goalActions.length > 0 ? (
        <div className="kc-explain-chips">
          {goalActions.map((label) => (
            <button key={label} type="button" className={learnMode ? "cb-chip" : undefined} onClick={() => void sendAnswer(label)}>
              {label}
            </button>
          ))}
        </div>
      ) : null}
      {composerOpen && session.active_block_type === "explanation" && !choosing ? (
        <div className="kc-explain-chips">
          {session.active_substep === "summary_check" ? (
            <button type="button" className={learnMode ? "cb-chip" : undefined} onClick={() => void sendAnswer("No final questions — let's continue!")}>
              No final questions — let&apos;s continue!
            </button>
          ) : (
            <>
              <button type="button" className={learnMode ? "cb-chip" : undefined} onClick={() => void sendAnswer("Tell me more")}>
                Tell me more
              </button>
              <button type="button" className={learnMode ? "cb-chip" : undefined} onClick={() => void sendAnswer("Got it - move on")}>
                Got it - move on
              </button>
            </>
          )}
        </div>
      ) : null}
      {learnMode && showComposer ? (
        <div className="cb-quick">
          <button type="button" className="cb-chip" onClick={() => void sendAnswer("Give me a hint")}>
            Give me a hint
          </button>
          <button type="button" className="cb-chip" onClick={() => void sendAnswer("Explain again")}>
            Explain again
          </button>
          <button type="button" className="cb-chip" onClick={() => void sendAnswer("I got it!")}>
            I got it!
          </button>
        </div>
      ) : null}
      {showComposer ? (
        <form
          className={learnMode ? "cb-composer" : "ds-composer-seat"}
          onSubmit={(event) => {
            event.preventDefault();
            if (choosing || sending.current) return;
            void sendAnswer(draft);
          }}
        >
          {learnMode ? (
            <>
              <textarea
                ref={draftRef}
                className="cb-input"
                name="answer"
                rows={1}
                value={draft}
                required={!choosing}
                placeholder={choosing ? "Choose an answer above" : "Message"}
                aria-label="Your answer"
                disabled={choosing}
                maxLength={2000}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    if (!choosing) event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              <button className="cb-btn is-primary" type="submit" disabled={choosing || answering || draft.trim().length === 0}>
                Send
              </button>
            </>
          ) : (
            <div className="ds-card">
              <textarea
                ref={draftRef}
                className="ds-draft"
                name="answer"
                rows={1}
                value={draft}
                required={!choosing}
                placeholder={choosing ? "Choose an answer above" : "Message"}
                aria-label="Your answer"
                disabled={choosing}
                maxLength={2000}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    if (!choosing) event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              <div className="ds-card-row">
                <button className="ds-send" type="submit" aria-label="Send" disabled={choosing || answering || draft.trim().length === 0}>
                  ↑
                </button>
              </div>
            </div>
          )}
        </form>
      ) : null}
    </div>
  );
}
