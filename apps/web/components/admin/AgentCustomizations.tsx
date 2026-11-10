"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { TutorAvatar, TutorAvatarPicker } from "@/components/TutorAvatar";
import { AdminFrame } from "@/components/admin/AdminFrame";
import { ConfigControl } from "@/components/admin/KcTutorConfigFields";
import { api } from "@/lib/api";
import { BLOCK_TYPES } from "@/lib/kc-blocks";
import type { KcBlockType } from "@/lib/kc";
import {
  HUMOR_AND_WIT_OPTIONS,
  INTEREST_WEAVING_OPTIONS,
  METAPHOR_OPTIONS,
  PERSONA_OPTIONS,
  SIDEKICK_OPTIONS,
  VOCABULARY_REGISTER_OPTIONS,
  hoverFor,
} from "@/lib/kc-layer-fields";
import {
  BLOCK_CONFIG_FIELDS,
  BLOCK_CONFIG_TITLES,
  DEFAULT_KC_TUTOR_CONFIG,
  OVERARCHING_FIELDS,
  kcTutorConfigFrom,
  type ConfigField,
  type KcTutorConfig,
} from "@/lib/kc-tutor-config";
import { DEFAULT_AVATAR_PRESET } from "@/lib/tutor-avatars";
import type { TutorProfile } from "@/lib/types";

type SectionTab = "voice" | "overarching" | "blocks" | "all";

const SECTION_TABS: readonly { id: SectionTab; label: string }[] = [
  { id: "voice", label: "Voice & Persona (Layer 3)" },
  { id: "overarching", label: "Overarching Teaching Policy (Layer 4)" },
  { id: "blocks", label: "Block Teaching Rules (Layer 4 — 9 Block Types)" },
  { id: "all", label: "Show All" },
];

const BLOCK_PILL_LABELS: Record<KcBlockType, string> = {
  topic_goal: "Topic / Goal",
  mcq: "MCQ",
  case_study: "Case Study",
  socratic: "Socratic",
  curiosity: "Curiosity",
  worked_example: "Worked Example",
  spot_the_flaw: "Spot the Flaw",
  teach_back: "Teach-Back",
  retrieval_check: "Retrieval Check",
};

type VoiceFieldSpec = {
  key: "persona" | "humor_and_wit" | "sidekick" | "vocabulary_register" | "interest_weaving" | "metaphors";
  label: string;
  hoverName: string;
  options: readonly (readonly [string, string])[];
  group: "character" | "terminology";
  keywords: string;
};

const VOICE_FIELDS: readonly VoiceFieldSpec[] = [
  {
    key: "persona",
    label: "Persona (Framing Archetype)",
    hoverName: "Persona",
    options: PERSONA_OPTIONS,
    group: "character",
    keywords: "persona voice character archetype socratic mentor coach detective explorer storyteller sibling wizard",
  },
  {
    key: "humor_and_wit",
    label: "Humor & Wit",
    hoverName: "Humor and wit",
    options: HUMOR_AND_WIT_OPTIONS,
    group: "character",
    keywords: "humor wit joke banter light warm playful straightforward anxiety guardrail",
  },
  {
    key: "sidekick",
    label: "Sidekick",
    hoverName: "Sidekick",
    options: SIDEKICK_OPTIONS,
    group: "character",
    keywords: "sidekick companion barnaby pixel spark none",
  },
  {
    key: "vocabulary_register",
    label: "Vocabulary Register (Subject Terminology)",
    hoverName: "Vocabulary register",
    options: VOCABULARY_REGISTER_OPTIONS,
    group: "terminology",
    keywords: "vocabulary register terminology lexicon adaptive everyday conversational academic precision story expressive",
  },
  {
    key: "interest_weaving",
    label: "Interest Weaving",
    hoverName: "Interest weaving",
    options: INTEREST_WEAVING_OPTIONS,
    group: "terminology",
    keywords: "interest weaving personalization hobbies subtle natural frequent thematic off",
  },
  {
    key: "metaphors",
    label: "Fallback Analogy Domain (Metaphors)",
    hoverName: "Metaphors",
    options: METAPHOR_OPTIONS,
    group: "terminology",
    keywords: "metaphors analogy fallback domain everyday games nature sports cooking scifi",
  },
];

const OVERARCHING_CARDS: readonly {
  title: string;
  subtitle: string;
  keys: readonly string[];
}[] = [
  {
    title: "Opening & Teaching Philosophy",
    subtitle: "How components open, how concepts are introduced, and how off-topic tangents are handled.",
    keys: ["orient_framing", "instructional_stance", "stay_on_course"],
  },
  {
    title: "Scaffolding, Misconceptions & Prerequisites",
    subtitle: "How hints escalate on misses, how traps are addressed, and how fragile prerequisites are supported.",
    keys: ["scaffolding_escalation", "misconception_policy", "prerequisite_support_policy"],
  },
  {
    title: "Praise & Component Close",
    subtitle: "How effort and reasoning moves are praised and how finished components are synthesized.",
    keys: ["encouragement_style", "close_summary_depth"],
  },
];

const RESEARCH_DEFAULT_VOICE = {
  persona: "coach",
  vocabulary_register: "adaptive_to_child",
  interest_weaving: "subtle_natural",
  metaphors: "everyday",
  humor_and_wit: "light_warm",
  sidekick: "none",
} as const;

const DEFAULT_DESCRIPTION =
  "Standard balanced AI Tutor profile using research-backed guided discovery and adaptive child vocabulary.";

const LEGACY_LEXICON_MAP: Record<string, string> = {
  "1": "everyday_conversational",
  "2": "everyday_conversational",
  "3": "adaptive_to_child",
  "4": "academic_precision",
  "5": "story_rich_expressive",
  match_child: "adaptive_to_child",
  "early-concrete": "everyday_conversational",
  "middle-grade-vivid": "adaptive_to_child",
  "precise-visual": "academic_precision",
  "analytical-high-school": "academic_precision",
};

const LEGACY_PERSONA_MAP: Record<string, string> = {
  "curious-co-explorer": "explorer",
  "tactical-coach": "coach",
  "debate-moderator": "socratic_mentor",
  "patient-explainer": "coach",
};

const LEGACY_METAPHOR_MAP: Record<string, string> = {
  "playground-sports": "sports",
  "buildings-machines": "everyday",
  "policy-cause": "everyday",
  none: "everyday",
};

const LEGACY_SIDEKICK_MAP: Record<string, string> = {
  off: "none",
  "bumbling-partner": "barnaby",
  "rookie-picture": "pixel",
  pundit: "spark",
};

function normalizeVoiceDraft(profile: TutorProfile): TutorProfile {
  const personaRaw = profile.persona || RESEARCH_DEFAULT_VOICE.persona;
  const persona = PERSONA_OPTIONS.some(([id]) => id === personaRaw)
    ? personaRaw
    : (LEGACY_PERSONA_MAP[personaRaw] ?? RESEARCH_DEFAULT_VOICE.persona);

  const regRaw = profile.vocabulary_register || profile.lexicon || RESEARCH_DEFAULT_VOICE.vocabulary_register;
  const vocabulary_register = VOCABULARY_REGISTER_OPTIONS.some(([id]) => id === regRaw)
    ? regRaw
    : (LEGACY_LEXICON_MAP[regRaw] ?? RESEARCH_DEFAULT_VOICE.vocabulary_register);

  const weavingRaw =
    profile.interest_weaving ||
    (profile.use_interests === false ? "off" : RESEARCH_DEFAULT_VOICE.interest_weaving);
  const interest_weaving = INTEREST_WEAVING_OPTIONS.some(([id]) => id === weavingRaw)
    ? weavingRaw
    : RESEARCH_DEFAULT_VOICE.interest_weaving;

  const metaRaw = profile.metaphors || RESEARCH_DEFAULT_VOICE.metaphors;
  const metaphors = METAPHOR_OPTIONS.some(([id]) => id === metaRaw)
    ? metaRaw
    : (LEGACY_METAPHOR_MAP[metaRaw] ?? RESEARCH_DEFAULT_VOICE.metaphors);

  const humorRaw = profile.humor_and_wit || RESEARCH_DEFAULT_VOICE.humor_and_wit;
  const humor_and_wit = HUMOR_AND_WIT_OPTIONS.some(([id]) => id === humorRaw)
    ? humorRaw
    : RESEARCH_DEFAULT_VOICE.humor_and_wit;

  const sideRaw = profile.sidekick || RESEARCH_DEFAULT_VOICE.sidekick;
  const sidekick = SIDEKICK_OPTIONS.some(([id]) => id === sideRaw)
    ? sideRaw
    : (LEGACY_SIDEKICK_MAP[sideRaw] ?? RESEARCH_DEFAULT_VOICE.sidekick);

  return {
    ...profile,
    id: profile.id || "default",
    name: profile.name || "Default",
    slug: profile.slug || profile.id || "default",
    description: profile.description ?? DEFAULT_DESCRIPTION,
    avatar_preset: profile.avatar_preset || DEFAULT_AVATAR_PRESET,
    avatar_url: profile.avatar_url ?? null,
    is_default: Boolean(profile.is_default || profile.id === "default"),
    persona,
    vocabulary_register,
    lexicon: vocabulary_register,
    interest_weaving,
    use_interests: interest_weaving !== "off",
    metaphors,
    humor_and_wit,
    sidekick,
    kc_tutor_config: kcTutorConfigFrom(profile.kc_tutor_config),
  };
}

function serializeProfileState(profile: TutorProfile | null): string {
  if (!profile) return "";
  const cfg = kcTutorConfigFrom(profile.kc_tutor_config);
  return JSON.stringify({
    name: profile.name || "Default",
    description: profile.description ?? "",
    avatar_preset: profile.avatar_preset || DEFAULT_AVATAR_PRESET,
    avatar_url: profile.avatar_url ?? null,
    persona: profile.persona,
    vocabulary_register: profile.vocabulary_register,
    interest_weaving: profile.interest_weaving,
    metaphors: profile.metaphors,
    humor_and_wit: profile.humor_and_wit,
    sidekick: profile.sidekick,
    overarching: cfg.overarching,
    blocks: cfg.blocks,
  });
}

function blockModifiedCount(config: KcTutorConfig, type: KcBlockType): number {
  const current = config.blocks[type] ?? {};
  const base = DEFAULT_KC_TUTOR_CONFIG.blocks[type] ?? {};
  let diff = 0;
  for (const field of BLOCK_CONFIG_FIELDS[type]) {
    if (current[field.key] !== base[field.key]) diff += 1;
  }
  return diff;
}

function matchesQuery(query: string, ...parts: (string | undefined)[]): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = parts.filter(Boolean).join(" ").toLowerCase();
  return q.split(/\s+/).every((token) => haystack.includes(token));
}

function Choice({
  label,
  value,
  options,
  help,
  title,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly (readonly [string, string])[];
  help?: string;
  title?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label title={title}>
      {label}
      <select title={title} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([id, text]) => (
          <option key={id} value={id}>
            {text}
          </option>
        ))}
      </select>
      {help ? <span className="help">{help}</span> : null}
    </label>
  );
}

export function AgentCustomizations() {
  const [profiles, setProfiles] = useState<TutorProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("default");
  const [draft, setDraft] = useState<TutorProfile | null>(null);
  const [baseline, setBaseline] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<SectionTab>("voice");
  const [selectedBlock, setSelectedBlock] = useState<KcBlockType>("topic_goal");
  const [showAllBlocks, setShowAllBlocks] = useState(false);
  const [avatarPickerOpen, setAvatarPickerOpen] = useState(false);

  const [newTutorOpen, setNewTutorOpen] = useState(false);
  const [newTutorName, setNewTutorName] = useState("");
  const [newTutorDesc, setNewTutorDesc] = useState("");
  const [newTutorPreset, setNewTutorPreset] = useState<string>(DEFAULT_AVATAR_PRESET);
  const [newTutorCloneFrom, setNewTutorCloneFrom] = useState<string>("");
  const [creatingTutor, setCreatingTutor] = useState(false);
  const [deletingTutor, setDeletingTutor] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api<TutorProfile[]>("/tutor-profiles")
      .then((list) => {
        if (cancelled) return;
        const normalizedList = (list.length > 0 ? list : []).map(normalizeVoiceDraft);
        setProfiles(normalizedList);
        const first = normalizedList.find((p) => p.is_default) ?? normalizedList[0];
        if (first) {
          setSelectedProfileId(first.id || "default");
          setDraft(first);
          setBaseline(serializeProfileState(first));
        }
        setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load tutor profiles.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function selectProfile(profile: TutorProfile) {
    const normalized = normalizeVoiceDraft(profile);
    setSelectedProfileId(normalized.id || "default");
    setDraft(normalized);
    setBaseline(serializeProfileState(normalized));
    setSaved(false);
    setError(null);
  }

  const hasUnsavedChanges = useMemo(() => {
    if (!draft || !baseline) return false;
    return serializeProfileState(draft) !== baseline;
  }, [draft, baseline]);

  const config = useMemo(
    () => kcTutorConfigFrom(draft?.kc_tutor_config),
    [draft?.kc_tutor_config],
  );

  function updateIdentityField(
    patch: Partial<Pick<TutorProfile, "name" | "description" | "avatar_preset" | "avatar_url">>,
  ) {
    setSaved(false);
    setDraft((current) => (current ? { ...current, ...patch } : current));
  }

  function updateVoiceField(key: VoiceFieldSpec["key"], value: string) {
    setSaved(false);
    setDraft((current) => {
      if (!current) return current;
      const next: TutorProfile = { ...current, [key]: value };
      if (key === "vocabulary_register") {
        next.lexicon = value;
      }
      if (key === "interest_weaving") {
        next.use_interests = value !== "off";
      }
      return next;
    });
  }

  function updateOverarching(key: string, value: string) {
    setSaved(false);
    setDraft((current) => {
      if (!current) return current;
      const cfg = kcTutorConfigFrom(current.kc_tutor_config);
      return {
        ...current,
        stay_on_course: key === "stay_on_course" ? value !== "exploratory" : current.stay_on_course,
        misconception_policy:
          key === "misconception_policy" ? value : current.misconception_policy,
        kc_tutor_config: {
          ...cfg,
          overarching: { ...cfg.overarching, [key]: value },
        },
      };
    });
  }

  function updateBlockField(type: KcBlockType, key: string, value: string | number | boolean) {
    setSaved(false);
    setDraft((current) => {
      if (!current) return current;
      const cfg = kcTutorConfigFrom(current.kc_tutor_config);
      return {
        ...current,
        kc_tutor_config: {
          ...cfg,
          blocks: {
            ...cfg.blocks,
            [type]: { ...cfg.blocks[type], [key]: value },
          },
        },
      };
    });
  }

  function resetBlockToDefault(type: KcBlockType) {
    setSaved(false);
    setDraft((current) => {
      if (!current) return current;
      const cfg = kcTutorConfigFrom(current.kc_tutor_config);
      return {
        ...current,
        kc_tutor_config: {
          ...cfg,
          blocks: {
            ...cfg.blocks,
            [type]: { ...DEFAULT_KC_TUTOR_CONFIG.blocks[type] },
          },
        },
      };
    });
  }

  function resetToResearchDefaults() {
    setSaved(false);
    setDraft((current) => {
      if (!current) return current;
      const freshConfig = kcTutorConfigFrom(DEFAULT_KC_TUTOR_CONFIG);
      return {
        ...current,
        persona: RESEARCH_DEFAULT_VOICE.persona,
        vocabulary_register: RESEARCH_DEFAULT_VOICE.vocabulary_register,
        lexicon: RESEARCH_DEFAULT_VOICE.vocabulary_register,
        interest_weaving: RESEARCH_DEFAULT_VOICE.interest_weaving,
        use_interests: true,
        metaphors: RESEARCH_DEFAULT_VOICE.metaphors,
        humor_and_wit: RESEARCH_DEFAULT_VOICE.humor_and_wit,
        sidekick: RESEARCH_DEFAULT_VOICE.sidekick,
        stay_on_course: true,
        misconception_policy: freshConfig.overarching.misconception_policy,
        kc_tutor_config: freshConfig,
      };
    });
  }

  async function handleCreateTutor() {
    const trimmed = newTutorName.trim();
    if (!trimmed) {
      setError("Tutor name is required.");
      return;
    }
    setCreatingTutor(true);
    setError(null);
    setSaved(false);
    try {
      const created = await api<TutorProfile>("/tutor-profiles", {
        method: "POST",
        body: JSON.stringify({
          name: trimmed,
          description:
            newTutorDesc.trim() ||
            DEFAULT_DESCRIPTION,
          avatar_preset: newTutorPreset || DEFAULT_AVATAR_PRESET,
          source_profile_id: newTutorCloneFrom || null,
        }),
      });
      const normalized = normalizeVoiceDraft(created);
      setProfiles((prev) => [...prev.filter((p) => p.id !== normalized.id), normalized]);
      setSelectedProfileId(normalized.id || "default");
      setDraft(normalized);
      setBaseline(serializeProfileState(normalized));
      setNewTutorOpen(false);
      setNewTutorName("");
      setNewTutorDesc("");
      setNewTutorPreset(DEFAULT_AVATAR_PRESET);
      setNewTutorCloneFrom("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create tutor profile.");
    } finally {
      setCreatingTutor(false);
    }
  }

  async function handleDeleteTutor() {
    if (!draft || draft.is_default || draft.id === "default") return;
    setDeletingTutor(true);
    setError(null);
    setSaved(false);
    try {
      await api<{ deleted: boolean }>(`/tutor-profiles/${encodeURIComponent(draft.id || "")}`, {
        method: "DELETE",
      });
      const remaining = profiles.filter((p) => p.id !== draft.id);
      setProfiles(remaining);
      const next = remaining.find((p) => p.is_default) ?? remaining[0] ?? null;
      if (next) {
        selectProfile(next);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete tutor profile.");
    } finally {
      setDeletingTutor(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const cfg = kcTutorConfigFrom(draft.kc_tutor_config);
      const targetId = draft.id || selectedProfileId || "default";
      const savedProfile = await api<TutorProfile>(
        `/tutor-profiles/${encodeURIComponent(targetId)}`,
        {
          method: "PUT",
          body: JSON.stringify({
            name: (draft.name || "Default").trim() || "Default",
            description: (draft.description ?? DEFAULT_DESCRIPTION).trim(),
            avatar_preset: draft.avatar_preset || DEFAULT_AVATAR_PRESET,
            avatar_url: draft.avatar_url ?? null,
            instructive: draft.instructive || 3,
            persona: draft.persona,
            lexicon: draft.vocabulary_register || draft.lexicon || "adaptive_to_child",
            vocabulary_register: draft.vocabulary_register || "adaptive_to_child",
            interest_weaving: draft.interest_weaving || "subtle_natural",
            humor_and_wit: draft.humor_and_wit || "light_warm",
            voice_override: true,
            metaphors: draft.metaphors,
            sidekick: draft.sidekick,
            struggle_window: draft.struggle_window || "standard",
            anti_spoiler: true,
            one_question: true,
            use_interests: (draft.interest_weaving || "subtle_natural") !== "off",
            stay_on_course: cfg.overarching.stay_on_course !== "exploratory",
            growth_praise: cfg.overarching.encouragement_style === "process_praise",
            misconception_policy: cfg.overarching.misconception_policy || "explain_and_retry_once",
            self_explanation: true,
            enrichment: String(cfg.blocks.topic_goal?.enrichment_mode || "on_request"),
            kc_tutor_config: cfg,
          }),
        },
      );
      const normalized = normalizeVoiceDraft(savedProfile);
      setProfiles((prev) =>
        prev.map((item) => (item.id === normalized.id ? normalized : item)),
      );
      setDraft(normalized);
      setBaseline(serializeProfileState(normalized));
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the tutor profile.");
    } finally {
      setSaving(false);
    }
  }

  const isSearching = searchQuery.trim().length > 0;

  const matchingVoiceFields = useMemo(
    () =>
      VOICE_FIELDS.filter((field) =>
        matchesQuery(
          searchQuery,
          field.label,
          field.key,
          field.keywords,
          hoverFor(field.hoverName),
          field.options.map(([id, text]) => `${id} ${text}`).join(" "),
        ),
      ),
    [searchQuery],
  );

  const matchingOverarchingFields = useMemo(
    () =>
      OVERARCHING_FIELDS.filter((field) =>
        matchesQuery(
          searchQuery,
          field.label,
          field.key,
          field.help,
          field.kind === "enum" ? field.options.map(([id, text]) => `${id} ${text}`).join(" ") : "",
        ),
      ),
    [searchQuery],
  );

  const matchingBlocks = useMemo(() => {
    const out: { type: KcBlockType; fields: ConfigField[] }[] = [];
    for (const type of BLOCK_TYPES) {
      const title = BLOCK_CONFIG_TITLES[type];
      const pill = BLOCK_PILL_LABELS[type];
      const blockMatchesDirectly = matchesQuery(searchQuery, type, title, pill);
      const fields = BLOCK_CONFIG_FIELDS[type].filter(
        (field) =>
          blockMatchesDirectly ||
          matchesQuery(
            searchQuery,
            type,
            title,
            pill,
            field.label,
            field.key,
            field.help,
            field.kind === "enum" ? field.options.map(([id, text]) => `${id} ${text}`).join(" ") : "",
          ),
      );
      if (fields.length > 0) {
        out.push({ type, fields });
      }
    }
    return out;
  }, [searchQuery]);

  const showVoiceSection = isSearching
    ? matchingVoiceFields.length > 0
    : activeTab === "voice" || activeTab === "all";

  const showOverarchingSection = isSearching
    ? matchingOverarchingFields.length > 0
    : activeTab === "overarching" || activeTab === "all";

  const showBlocksSection = isSearching
    ? matchingBlocks.length > 0
    : activeTab === "blocks" || activeTab === "all";

  return (
    <AdminFrame current="customizations">
      <article className="editor agent-config-editor">
        <p className="eyebrow">Administration</p>
        <h2>AI Tutor Configuration</h2>
        <p className="help">
          Configure the Default AI Tutor or create custom AI Tutor profiles with distinct 64-icon SVG avatars,
          descriptions, Layer 3 Voice &amp; Persona settings, and Layer 4 Overarching &amp; Block Teaching Rules.
        </p>

        <section className="tutor-profile-switcher" aria-label="Tutor Profiles">
          <div className="tutor-profile-pills" role="tablist" aria-label="Available AI Tutors">
            {profiles.map((profile) => {
              const active = profile.id === (draft?.id || selectedProfileId);
              return (
                <button
                  key={profile.id || profile.slug}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  className={`tutor-profile-pill${active ? " is-active" : ""}`}
                  onClick={() => selectProfile(profile)}
                >
                  <TutorAvatar
                    preset={profile.avatar_preset}
                    avatarUrl={profile.avatar_url}
                    name={profile.name}
                    size="sm"
                  />
                  <span className="tutor-profile-pill-name">{profile.name || "Default"}</span>
                  {profile.is_default || profile.id === "default" ? (
                    <span className="agent-pill-badge">Default</span>
                  ) : null}
                </button>
              );
            })}
            <button
              type="button"
              className="button ghost tutor-profile-new-btn"
              onClick={() => {
                setNewTutorCloneFrom(draft?.id || "default");
                setNewTutorOpen((open) => !open);
              }}
            >
              + New Tutor
            </button>
          </div>

          {newTutorOpen ? (
            <div className="agent-config-card tutor-new-card" role="region" aria-label="Create New Tutor">
              <h4>Create New AI Tutor Profile</h4>
              <div className="tutor-new-grid">
                <label>
                  Tutor Name
                  <input
                    type="text"
                    aria-label="New Tutor Name"
                    placeholder="e.g. Professor Athena, Coach Leo, Captain Spark"
                    value={newTutorName}
                    maxLength={120}
                    onChange={(event) => setNewTutorName(event.target.value)}
                  />
                </label>
                <label>
                  Copy Settings From
                  <select
                    aria-label="Copy Settings From"
                    value={newTutorCloneFrom}
                    onChange={(event) => setNewTutorCloneFrom(event.target.value)}
                  >
                    <option value="">Research Defaults</option>
                    {profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        Clone from {p.name} ({p.slug})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="tutor-new-desc-field">
                  Tutor Description
                  <input
                    type="text"
                    aria-label="New Tutor Description"
                    placeholder="Short description shown to learners in the Tutor selector..."
                    value={newTutorDesc}
                    onChange={(event) => setNewTutorDesc(event.target.value)}
                  />
                </label>
              </div>
              <div className="rail-actions">
                <button
                  type="button"
                  className="button"
                  disabled={creatingTutor || !newTutorName.trim()}
                  onClick={() => void handleCreateTutor()}
                >
                  {creatingTutor ? "Creating..." : "Create Tutor"}
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setNewTutorOpen(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
        </section>

        {loading ? <p className="help">Loading tutor profiles.</p> : null}
        {draft ? (
          <form className="agent-form agent-config-form" onSubmit={(event) => void onSubmit(event)}>
            <header className="agent-sticky-header" aria-label="Search and configuration actions">
              <div className="agent-search-wrap">
                <input
                  type="search"
                  className="agent-search-input"
                  aria-label="Search settings"
                  placeholder="Search settings by name, block, or keyword (e.g. retry, mcq, vocabulary, praise)..."
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                />
                {isSearching ? (
                  <button
                    type="button"
                    className="ghost agent-search-clear"
                    onClick={() => setSearchQuery("")}
                  >
                    Clear
                  </button>
                ) : null}
              </div>
              <div className="agent-header-actions">
                <span
                  className={`agent-status-badge${hasUnsavedChanges ? " is-unsaved" : " is-clean"}`}
                  role="status"
                >
                  {hasUnsavedChanges ? "Unsaved changes" : saved ? "Saved" : "All changes saved"}
                </span>
                <button
                  type="button"
                  className="ghost"
                  onClick={resetToResearchDefaults}
                >
                  Reset to Research Defaults
                </button>
                <button className="button" type="submit" disabled={saving}>
                  {saving ? "Saving..." : "Save configuration"}
                </button>
              </div>
            </header>

            <section className="agent-config-card tutor-identity-card" aria-label="Tutor Identity & Avatar">
              <div className="tutor-identity-top">
                <div className="tutor-identity-summary">
                  <TutorAvatar
                    preset={draft.avatar_preset}
                    avatarUrl={draft.avatar_url}
                    name={draft.name}
                    size="lg"
                  />
                  <div>
                    <h3>
                      {draft.name || "Default"}{" "}
                      {draft.is_default || draft.id === "default" ? (
                        <span className="agent-custom-badge">Default Profile</span>
                      ) : (
                        <span className="help">({draft.slug})</span>
                      )}
                    </h3>
                    <p className="help">{draft.description || DEFAULT_DESCRIPTION}</p>
                  </div>
                </div>
                <div className="tutor-identity-actions">
                  <button
                    type="button"
                    className="ghost"
                    aria-expanded={avatarPickerOpen}
                    onClick={() => setAvatarPickerOpen((prev) => !prev)}
                  >
                    {avatarPickerOpen ? "Hide 64-Icon Avatar Picker" : "Choose Avatar (64 Icons)"}
                  </button>
                  {!draft.is_default && draft.id !== "default" ? (
                    <button
                      type="button"
                      className="ghost"
                      disabled={deletingTutor}
                      onClick={() => void handleDeleteTutor()}
                    >
                      {deletingTutor ? "Deleting..." : "Delete Tutor"}
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="tutor-identity-fields">
                <label>
                  Tutor Name
                  <input
                    type="text"
                    aria-label="Tutor Name"
                    value={draft.name || ""}
                    maxLength={120}
                    disabled={Boolean(draft.is_default || draft.id === "default")}
                    onChange={(event) => updateIdentityField({ name: event.target.value })}
                  />
                </label>
                <label>
                  Tutor Description
                  <textarea
                    aria-label="Tutor Description"
                    rows={2}
                    value={draft.description ?? ""}
                    onChange={(event) => updateIdentityField({ description: event.target.value })}
                  />
                </label>
              </div>

              {avatarPickerOpen ? (
                <TutorAvatarPicker
                  preset={draft.avatar_preset || DEFAULT_AVATAR_PRESET}
                  avatarUrl={draft.avatar_url}
                  onChangePreset={(nextPreset) => updateIdentityField({ avatar_preset: nextPreset })}
                  onChangeUrl={(nextUrl) => updateIdentityField({ avatar_url: nextUrl })}
                />
              ) : null}
            </section>

            {!isSearching ? (
              <nav className="agent-section-tabs" aria-label="Configuration sections">
                {SECTION_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`agent-section-tab${activeTab === tab.id ? " is-active" : ""}`}
                    aria-pressed={activeTab === tab.id}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            ) : (
              <p className="agent-search-banner">
                Showing matching controls for <strong>&ldquo;{searchQuery.trim()}&rdquo;</strong> across Layer 3,
                Overarching Policy, and the 9 Block Types.
              </p>
            )}

            {isSearching && !showVoiceSection && !showOverarchingSection && !showBlocksSection ? (
              <p className="help">No settings matched &ldquo;{searchQuery.trim()}&rdquo;.</p>
            ) : null}

            {showVoiceSection ? (
              <section className="agent-config-section" aria-label="Voice & Persona (Layer 3)">
                <div className="agent-section-heading">
                  <h3 className="agent-layer">Voice &amp; Persona (Layer 3)</h3>
                  <p className="help">
                    Six orthogonal voice controls governing framing archetype, terminology register, interest weaving,
                    fallback analogies, humor guardrails, and sidekick presence.
                  </p>
                </div>

                <aside className="agent-harmony-note" aria-label="Cross-Layer Harmony">
                  <strong>Cross-Layer Harmony:</strong> Sentence length, reading complexity, paragraph density, and
                  explanation representation format are governed per-child by <strong>Layer 2</strong> (
                  <code>reading_level</code>, <code>response_length</code>, <code>learning_support</code>,{" "}
                  <code>explanation_style</code>). Layer 3 never overrides a child&apos;s reading level or emotional
                  safety settings.
                </aside>

                <div className="agent-card-grid">
                  {(["character", "terminology"] as const).map((groupKey) => {
                    const groupFields = (isSearching ? matchingVoiceFields : VOICE_FIELDS).filter(
                      (field) => field.group === groupKey,
                    );
                    if (groupFields.length === 0) return null;
                    const cardTitle =
                      groupKey === "character"
                        ? "Character, Humor & Sidekick"
                        : "Terminology & Personalization";
                    const cardSub =
                      groupKey === "character"
                        ? "Framing metaphor, warm levity with automatic miss/anxiety suppression, and optional sidekick."
                        : "Subject terminology introduction, Layer 2 interest weaving frequency, and fallback analogy domain.";
                    return (
                      <div key={groupKey} className="agent-config-card">
                        <h4>{cardTitle}</h4>
                        <p className="help">{cardSub}</p>
                        {groupFields.map((field) => {
                          const currentVal = String(
                            draft[field.key] ?? RESEARCH_DEFAULT_VOICE[field.key],
                          );
                          return (
                            <Choice
                              key={field.key}
                              label={field.label}
                              value={currentVal}
                              options={field.options}
                              title={hoverFor(field.hoverName)}
                              help={hoverFor(field.hoverName)}
                              onChange={(val) => updateVoiceField(field.key, val)}
                            />
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              </section>
            ) : null}

            {showOverarchingSection ? (
              <section
                className="agent-config-section"
                aria-label="Overarching Teaching Policy (Layer 4)"
              >
                <div className="agent-section-heading">
                  <h3 className="agent-layer">Overarching Teaching Policy (Layer 4)</h3>
                  <p className="help">
                    Eight overarching pedagogical policies applied across every block type while the tutor walks a
                    knowledge component.
                  </p>
                </div>

                <div className="agent-card-grid">
                  {OVERARCHING_CARDS.map((card) => {
                    const cardFields = card.keys
                      .map((key) => OVERARCHING_FIELDS.find((f) => f.key === key))
                      .filter((f): f is ConfigField => Boolean(f))
                      .filter((f) =>
                        isSearching
                          ? matchingOverarchingFields.some((mf) => mf.key === f.key)
                          : true,
                      );
                    if (cardFields.length === 0) return null;
                    return (
                      <div key={card.title} className="agent-config-card">
                        <h4>{card.title}</h4>
                        <p className="help">{card.subtitle}</p>
                        {cardFields.map((field) => (
                          <ConfigControl
                            key={field.key}
                            field={field}
                            value={config.overarching[field.key]}
                            onChange={(val) => updateOverarching(field.key, String(val))}
                          />
                        ))}
                      </div>
                    );
                  })}
                </div>
              </section>
            ) : null}

            {showBlocksSection ? (
              <section
                className="agent-config-section"
                aria-label="Block Teaching Rules (Layer 4 — 9 Block Types)"
              >
                <div className="agent-section-heading">
                  <h3 className="agent-layer">Block Teaching Rules (Layer 4 — 9 Block Types)</h3>
                  <p className="help">
                    Specialized teaching mechanics, retry caps, and scaffolding rules for each of the nine block types.
                  </p>
                </div>

                {!isSearching ? (
                  <div className="agent-block-pills" role="group" aria-label="9-Block Pill Selector Bar">
                    {BLOCK_TYPES.map((type) => {
                      const diffCount = blockModifiedCount(config, type);
                      const isSelected = !showAllBlocks && selectedBlock === type;
                      return (
                        <button
                          key={type}
                          type="button"
                          className={`kc-chip agent-block-pill${isSelected ? " is-active" : ""}`}
                          aria-pressed={isSelected}
                          onClick={() => {
                            setShowAllBlocks(false);
                            setSelectedBlock(type);
                          }}
                        >
                          <span>{BLOCK_PILL_LABELS[type]}</span>
                          {diffCount > 0 ? (
                            <span className="agent-pill-badge" title={`${diffCount} customized setting(s)`}>
                              {diffCount}
                            </span>
                          ) : null}
                        </button>
                      );
                    })}
                    <button
                      type="button"
                      className={`kc-chip agent-block-pill${showAllBlocks ? " is-active" : ""}`}
                      aria-pressed={showAllBlocks}
                      onClick={() => setShowAllBlocks((prev) => !prev)}
                    >
                      Show All 9
                    </button>
                  </div>
                ) : null}

                <div className="agent-card-grid">
                  {(isSearching
                    ? matchingBlocks
                    : showAllBlocks || activeTab === "all"
                      ? BLOCK_TYPES.map((type) => ({ type, fields: BLOCK_CONFIG_FIELDS[type] }))
                      : [{ type: selectedBlock, fields: BLOCK_CONFIG_FIELDS[selectedBlock] }]
                  ).map(({ type, fields }) => {
                    const diffCount = blockModifiedCount(config, type);
                    return (
                      <section
                        key={type}
                        className="agent-config-card"
                        aria-label={BLOCK_CONFIG_TITLES[type]}
                      >
                        <div className="agent-block-card-header">
                          <div>
                            <h4>{BLOCK_CONFIG_TITLES[type]}</h4>
                            {diffCount > 0 ? (
                              <span className="agent-custom-badge">
                                {diffCount} customized
                              </span>
                            ) : (
                              <span className="help">Using research defaults</span>
                            )}
                          </div>
                          <button
                            type="button"
                            className="ghost"
                            disabled={diffCount === 0}
                            onClick={() => resetBlockToDefault(type)}
                          >
                            Reset block to default
                          </button>
                        </div>
                        {fields.map((field) => (
                          <ConfigControl
                            key={`${type}-${field.key}`}
                            field={field}
                            value={config.blocks[type]?.[field.key]}
                            onChange={(value) => updateBlockField(type, field.key, value)}
                          />
                        ))}
                      </section>
                    );
                  })}
                </div>
              </section>
            ) : null}

            {error ? (
              <div className="banner" role="alert">
                <p>{error}</p>
              </div>
            ) : null}
            {saved ? <p className="note">Saved tutor profile &ldquo;{draft.name}&rdquo;.</p> : null}
          </form>
        ) : null}
        {!loading && !draft && error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
      </article>
    </AdminFrame>
  );
}
