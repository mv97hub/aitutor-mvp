/** Global AI safety settings, the admin field list, and KC chat review helpers. */

export const SAFETY_GROUPS = [
  "Overall",
  "Content",
  "Wellbeing",
  "Privacy",
  "Honesty",
  "Manipulation",
  "Review",
] as const;

export type SafetyGroup = (typeof SAFETY_GROUPS)[number];

export const BLOCKED_TOPIC_OPTIONS = [
  ["sexual_content", "Sexual content"],
  ["graphic_violence", "Graphic violence"],
  ["weapons", "Weapons"],
  ["drugs_and_alcohol", "Drugs and alcohol"],
  ["self_harm_methods", "Self-harm methods"],
  ["hate_or_harassment", "Hate or harassment"],
  ["gambling", "Gambling"],
  ["dangerous_challenges", "Dangerous challenges and stunts"],
] as const;

export type AiSafetySettings = {
  safety_strictness: "strict" | "standard";
  age_scaling: boolean;
  blocked_topics: string[];
  sensitive_school_topics: "brief_age_appropriate" | "redirect_to_parent_or_teacher" | "decline";
  harmful_words: "calm_redirect" | "redirect_and_note" | "ignore";
  distress_response: "supportive_and_trusted_adult" | "supportive_only";
  trusted_adult_message: string;
  helpline: string;
  emotional_reliance: "gentle_limits" | "off";
  personal_information: "never_ask_and_discourage" | "never_ask";
  no_secrets: true;
  ai_disclosure: "always_honest";
  uncertainty: "say_not_sure" | "best_effort";
  advice_limits: "no_medical_legal_safety_advice";
  links_and_media: "never_share_links" | "course_material_only";
  jailbreak_resistance: "stay_in_role_and_redirect";
  role_play_limits: "teaching_roles_only" | "none";
  flag_safety_moments: boolean;
};

export type SafetyField = {
  key: keyof AiSafetySettings;
  label: string;
  group: SafetyGroup;
  hover: string;
  kind: "select" | "bool" | "topics" | "message" | "locked";
  options?: readonly (readonly [string, string])[];
};

export const SAFETY_FIELDS: readonly SafetyField[] = [
  {
    key: "safety_strictness",
    label: "Safety strictness",
    group: "Overall",
    hover: "Strict refuses at the first sign of a boundary. Standard allows a brief, factual, age-appropriate answer on sensitive school topics.",
    kind: "select",
    options: [
      ["strict", "Strict"],
      ["standard", "Standard"],
    ],
  },
  {
    key: "age_scaling",
    label: "Age scaling",
    group: "Overall",
    hover: "Uses the child's age to tighten wording under 8 and allow a little more factual detail at 14 and up. It never goes below the strictness setting.",
    kind: "bool",
  },
  {
    key: "blocked_topics",
    label: "Blocked topics",
    group: "Content",
    hover: "Topics the tutor does not teach, describe, or role-play. All are on by default.",
    kind: "topics",
  },
  {
    key: "sensitive_school_topics",
    label: "Sensitive school topics",
    group: "Content",
    hover: "How the tutor handles history, health, and news questions that touch the blocked list.",
    kind: "select",
    options: [
      ["brief_age_appropriate", "Brief and age-appropriate"],
      ["redirect_to_parent_or_teacher", "Redirect to a parent or teacher"],
      ["decline", "Decline"],
    ],
  },
  {
    key: "harmful_words",
    label: "Harmful words from the child",
    group: "Content",
    hover: "How the tutor responds to insults, slurs, or bullying language.",
    kind: "select",
    options: [
      ["calm_redirect", "Calm redirect"],
      ["redirect_and_note", "Redirect and note"],
      ["ignore", "Ignore"],
    ],
  },
  {
    key: "distress_response",
    label: "Distress response",
    group: "Wellbeing",
    hover: "When a child says they are hurt, scared, unsafe, or hopeless, the tutor stays kind and does not diagnose or counsel.",
    kind: "select",
    options: [
      ["supportive_and_trusted_adult", "Supportive, and point to a trusted adult"],
      ["supportive_only", "Supportive only"],
    ],
  },
  {
    key: "trusted_adult_message",
    label: "Trusted-adult message",
    group: "Wellbeing",
    hover: "The short text the tutor uses in a distress moment. The helpline line stays blank until you fill it in.",
    kind: "message",
  },
  {
    key: "emotional_reliance",
    label: "Emotional reliance",
    group: "Wellbeing",
    hover: "The tutor never says it will miss the child, never asks them to stay, and encourages time with people.",
    kind: "select",
    options: [
      ["gentle_limits", "Gentle limits"],
      ["off", "Off"],
    ],
  },
  {
    key: "personal_information",
    label: "Personal information",
    group: "Privacy",
    hover: "The tutor never asks for a last name, address, school, phone, email, password, or photo, and does not repeat them.",
    kind: "select",
    options: [
      ["never_ask_and_discourage", "Never ask, and discourage sharing"],
      ["never_ask", "Never ask"],
    ],
  },
  {
    key: "no_secrets",
    label: "No secrets",
    group: "Privacy",
    hover: "Always on. The tutor never asks a child to keep something from a parent or teacher, and never promises secrecy.",
    kind: "locked",
    options: [["true", "Always on"]],
  },
  {
    key: "ai_disclosure",
    label: "AI disclosure",
    group: "Honesty",
    hover: "If asked, the tutor says it is an AI tutor, not a person or a friend with a life outside the lesson.",
    kind: "locked",
    options: [["always_honest", "Always honest"]],
  },
  {
    key: "uncertainty",
    label: "Uncertainty",
    group: "Honesty",
    hover: "The tutor says when it is unsure, or gives its best careful answer. It does not invent facts, quotes, or sources.",
    kind: "select",
    options: [
      ["say_not_sure", "Say when unsure"],
      ["best_effort", "Best effort"],
    ],
  },
  {
    key: "advice_limits",
    label: "Advice limits",
    group: "Honesty",
    hover: "Health, legal, and dangerous-activity questions go to a trusted adult.",
    kind: "locked",
    options: [["no_medical_legal_safety_advice", "No medical, legal, or safety advice"]],
  },
  {
    key: "links_and_media",
    label: "Links and media",
    group: "Honesty",
    hover: "No web addresses, downloads, or invitations to other apps. Course material only allows names already in the lesson.",
    kind: "select",
    options: [
      ["never_share_links", "Never share links"],
      ["course_material_only", "Course material only"],
    ],
  },
  {
    key: "jailbreak_resistance",
    label: "Jailbreak resistance",
    group: "Manipulation",
    hover: "The tutor ignores requests to reveal instructions, ignore rules, switch roles, or role-play an unsafe character, and returns to the lesson without lecturing.",
    kind: "locked",
    options: [["stay_in_role_and_redirect", "Stay in role and redirect"]],
  },
  {
    key: "role_play_limits",
    label: "Role-play limits",
    group: "Manipulation",
    hover: "Fun characters inside the lesson are fine. Real people, adult characters, and romantic role-play are not.",
    kind: "select",
    options: [
      ["teaching_roles_only", "Teaching roles only"],
      ["none", "No role-play"],
    ],
  },
  {
    key: "flag_safety_moments",
    label: "Flag safety moments",
    group: "Review",
    hover: "The tutor returns a safety flag with each reply. Flagged turns are saved for review in KC View Chats and do not change progress.",
    kind: "bool",
  },
];

export const DEFAULT_TRUSTED_ADULT = "Tell a parent, teacher, or another adult you trust.";

export function defaultAiSafety(): AiSafetySettings {
  return {
    safety_strictness: "strict",
    age_scaling: true,
    blocked_topics: BLOCKED_TOPIC_OPTIONS.map(([id]) => id),
    sensitive_school_topics: "brief_age_appropriate",
    harmful_words: "calm_redirect",
    distress_response: "supportive_and_trusted_adult",
    trusted_adult_message: DEFAULT_TRUSTED_ADULT,
    helpline: "",
    emotional_reliance: "gentle_limits",
    personal_information: "never_ask_and_discourage",
    no_secrets: true,
    ai_disclosure: "always_honest",
    uncertainty: "say_not_sure",
    advice_limits: "no_medical_legal_safety_advice",
    links_and_media: "never_share_links",
    jailbreak_resistance: "stay_in_role_and_redirect",
    role_play_limits: "teaching_roles_only",
    flag_safety_moments: true,
  };
}

export type AiSafetyResponse = {
  settings: AiSafetySettings;
  safety_text: string;
};

export type SafetyEvent = {
  id: string;
  created_at: string;
  student_display_name: string;
  kc_session_id: string | null;
  course_title: string;
  component_title: string;
  category: string;
  child_message: string;
  tutor_reply: string;
  reviewed_at: string | null;
  reviewed_by: string;
};

export type SafetyEventPage = {
  events: SafetyEvent[];
  total: number;
  limit: number;
  offset: number;
};

export const SAFETY_CATEGORY_LABELS: Record<string, string> = {
  distress: "Distress",
  inappropriate_content: "Inappropriate content",
  personal_info: "Personal info",
  manipulation: "Manipulation",
  other: "Other",
};

export function safetyCategoryLabel(category: string): string {
  return SAFETY_CATEGORY_LABELS[category] || category;
}

export function showSafetyTag(count: number): boolean {
  return count > 0;
}

export function eventsForChat<T extends { kc_session_id: string | null }>(events: T[], sessionId: string): T[] {
  return events.filter((event) => event.kc_session_id === sessionId);
}

export function unreviewedEvents<T extends { reviewed_at: string | null }>(events: T[]): T[] {
  return events.filter((event) => !event.reviewed_at);
}

export function unreviewedChatTotal(chats: readonly { unreviewed_safety_count?: number }[]): number {
  return chats.reduce((sum, chat) => sum + (chat.unreviewed_safety_count ?? 0), 0);
}

export function filterChatsWithUnreviewed<T extends { unreviewed_safety_count?: number }>(
  chats: readonly T[],
  enabled: boolean,
): T[] {
  if (!enabled) return [...chats];
  return chats.filter((chat) => (chat.unreviewed_safety_count ?? 0) > 0);
}

export function safetyExcerpt(prompt: string): string {
  if (!prompt.startsWith("Safety\n")) return "";
  const marker = "\n\nThis turn\n";
  const end = prompt.indexOf(marker);
  return end > 0 ? prompt.slice(0, end) : prompt;
}
