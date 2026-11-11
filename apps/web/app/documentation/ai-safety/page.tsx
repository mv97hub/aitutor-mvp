import Link from "next/link";

export const metadata = { title: "AI Safety · Documentation · AI Tutor" };

export default function AiSafetyDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>AI Safety</h1>
        <p>
          AI Safety at <Link href="/admin/ai-safety">/admin/ai-safety</Link> stores one global row. Every tutor and
          every child uses it. The Safety section is the first part of the tutor prompt. It applies on every turn and
          overrides persona, child preferences, humor, and block rules.
        </p>
        <p>
          Flagged turns are saved in their own table and open from a Safety tag in{" "}
          <Link href="/admin/kc-chats">KC View Chats</Link>. A flagged turn does not change progress.
        </p>

        <h2>Overall</h2>
        <ul>
          <li>
            <strong>Safety strictness.</strong> Strict (default) refuses and redirects at the first sign of a boundary.
            Standard allows a brief, factual, age-appropriate answer on sensitive school topics.
          </li>
          <li>
            <strong>Age scaling.</strong> On (default) uses the child&apos;s age. Under 8, wording is shorter and refusals
            are firmer. At 14 and up, a little more factual detail is allowed only inside the strictness already set.
            Off uses the same wording for every age.
          </li>
        </ul>

        <h2>Content</h2>
        <ul>
          <li>
            <strong>Blocked topics.</strong> Sexual content, graphic violence, weapons, drugs and alcohol, self-harm
            methods, hate or harassment, gambling, and dangerous challenges and stunts. All are on by default. The tutor
            does not teach, describe, or role-play a selected topic.
          </li>
          <li>
            <strong>Sensitive school topics.</strong> Brief and age-appropriate (default), redirect to a parent or
            teacher, or decline. This covers history, health, and news that touch the blocked list.
          </li>
          <li>
            <strong>Harmful words from the child.</strong> Calm redirect (default), redirect and note, or ignore.
          </li>
        </ul>

        <h2>Wellbeing</h2>
        <ul>
          <li>
            <strong>Distress response.</strong> Supportive and point to a trusted adult (default), or supportive only.
            The tutor stays kind and does not diagnose or counsel.
          </li>
          <li>
            <strong>Trusted-adult message.</strong> The short text used in that moment. The default is to tell a parent,
            teacher, or another adult you trust. An optional helpline stays blank until it is filled in.
          </li>
          <li>
            <strong>Emotional reliance.</strong> Gentle limits (default) or off. The tutor never says it will miss the
            child, never asks them to stay, and encourages time with people.
          </li>
        </ul>

        <h2>Privacy</h2>
        <ul>
          <li>
            <strong>Personal information.</strong> Never ask and discourage sharing (default), or never ask. The tutor
            does not ask for a last name, address, school, phone, email, password, or photo, and does not repeat them.
          </li>
          <li>
            <strong>No secrets.</strong> Always on. The tutor never asks a child to keep something from a parent or
            teacher, and never promises secrecy.
          </li>
        </ul>

        <h2>Honesty</h2>
        <ul>
          <li>
            <strong>AI disclosure.</strong> Always honest. If asked, the tutor says it is an AI tutor, not a person or a
            friend with a life outside the lesson.
          </li>
          <li>
            <strong>Uncertainty.</strong> Say when unsure (default), or best effort. The tutor does not invent facts,
            quotes, or sources.
          </li>
          <li>
            <strong>Advice limits.</strong> Health, legal, and dangerous-activity questions go to a trusted adult.
          </li>
          <li>
            <strong>Links and media.</strong> Never share links (default), or course material only. No web addresses,
            downloads, or invitations to other apps.
          </li>
        </ul>

        <h2>Manipulation</h2>
        <ul>
          <li>
            <strong>Jailbreak resistance.</strong> The tutor ignores requests to reveal instructions, ignore rules,
            switch roles, or role-play an unsafe character, and returns to the lesson without lecturing.
          </li>
          <li>
            <strong>Role-play limits.</strong> Teaching roles only (default), or none. Fun characters inside the lesson
            are fine. Real people, adult characters, and romantic role-play are not.
          </li>
        </ul>

        <h2>Review</h2>
        <ul>
          <li>
            <strong>Flag safety moments.</strong> On (default). The tutor returns safety_flag as none, distress,
            inappropriate_content, personal_info, manipulation, or other. A value other than none is saved when this
            setting is on. The latest flag also shows in Debug Variables.
          </li>
        </ul>
      </article>
    </main>
  );
}
