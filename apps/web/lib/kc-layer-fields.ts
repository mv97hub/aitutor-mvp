/** Hover text and the field catalog for the seven-layer KC tutor. */

export type LayerField = {
  layer: string;
  name: string;
  hover: string;
  role: string;
  kind: "Configured" | "Derived";
  where: string;
};

export const LAYER_HEADINGS = [
  "Safety",
  "Layer 1, Component",
  "Layer 2, Child",
  "Layer 3, Voice",
  "Layer 4, Guidance",
  "Layer 5, Encouragement",
  "Layer 6, Metacognition",
  "Layer 7, Feedback loop",
] as const;

export const MOVE_SEQUENCES = [
  "Factual. Orient from the outline. Each topic is typed and checks that topic's goal. Retrieve, evidence is the fact. Optional restatement when self-explanation is on and the retrieval was only a fragment. An empty field is skipped.",
  "Procedural. Orient names the procedure. Each step is one typed discussion and checks that step's goal. The child chooses what to do next, then fills the blanked step, then the solo problem, then why this order when self-explanation is on.",
  "Conceptual. Orient does not name the rule. Each topic is typed and checks that topic's goal. Predict case one, then case two. Both are on-screen choices. Contrast, then state the rule. Transfer when that field is stored.",
  "Causal. Orient names the decision. Each link is typed and checks that link's goal. What is at stake. Mark the flawed claim on screen. Defend the chain. Counterfactual when that field is stored and self-explanation is on.",
  "Synthesis. Orient names the job and the two earlier components. Each job is a typed topic. The rookie's faulty plan, then the correction, then which component does which job.",
] as const;

export const GRADE_BAND_OPTIONS = [
  ["early_elementary", "Early elementary (Grades K-2, ages 5-7)"],
  ["upper_elementary", "Upper elementary (Grades 3-5, ages 8-10)"],
  ["middle_school", "Middle school (Grades 6-8, ages 11-13)"],
  ["high_school", "High school (Grades 9-12, ages 14-18)"],
] as const;

export const READING_LEVEL_OPTIONS = [
  ["emerging", "Emerging (Very short sentences, everyday sight words, define new terms right away)"],
  ["early_fluent", "Early fluent (Concrete sentences, one clause at a time, plain transitions)"],
  ["on_grade", "On grade (Natural grade-level vocabulary and sentence flow)"],
  ["advanced", "Advanced (Precise academic terms and richer compound sentences)"],
] as const;

export const RESPONSE_LENGTH_OPTIONS = [
  ["bite_sized", "Bite-sized (1-2 short sentences per turn; low working-memory load)"],
  ["balanced", "Balanced (2-4 sentences per turn; standard conversational flow)"],
  ["detailed", "Detailed (Fuller explanations with explicit connections when needed)"],
] as const;

export const EXPRESSION_STYLE_OPTIONS = [
  ["one_word_or_taps", "One word or taps (Types 1-3 words; tutor validates the idea and models a clean sentence)"],
  ["short_phrases", "Short phrases (Types brief phrases or single sentences; tutor keeps follow-ups crisp)"],
  ["conversational", "Conversational (Likes back-and-forth dialogue and thinking out loud)"],
  ["analytical", "Analytical (Writes fuller reasoning and likes precise pushback)"],
] as const;

export const EXPLANATION_STYLE_OPTIONS = [
  ["concrete_examples", "Concrete examples (Everyday real-world objects and familiar situations first)"],
  ["step_by_step", "Step by step (Numbered, sequential breakdown of one piece at a time)"],
  ["visual_spatial", "Visual-spatial (Vivid mental pictures, spatial layouts, and diagram descriptions)"],
  ["story_and_analogy", "Story and analogy (Short narrative hooks and 'imagine if' comparisons)"],
  ["pattern_and_rule", "Pattern and rule (Show the underlying rule or structure first, then apply it)"],
] as const;

export const CHALLENGE_APPETITE_OPTIONS = [
  ["needs_reassurance", "Needs reassurance (Hesitant to guess; normalize mistakes early and lower stakes)"],
  ["steady", "Steady (Comfortable trying with normal scaffolding)"],
  ["loves_a_challenge", "Loves a challenge (Enjoys stretch prompts, quick pacing, and minimal hints)"],
] as const;

export const COMMUNICATION_TONE_OPTIONS = [
  ["calm_and_gentle", "Calm and gentle (Low-stimulation, patient, zero pressure)"],
  ["warm_and_encouraging", "Warm and encouraging (Friendly, upbeat coach)"],
  ["playful_and_curious", "Playful and curious (Light humor and wonder-driven energy)"],
  ["direct_and_matter_of_fact", "Direct and matter-of-fact (No fluff; straight to the concept)"],
] as const;

export const PASSAGE_ELA_DISPLAY_OPTIONS = [
  ["full_on_open", "Full passage on open"],
  ["chunked_by_paragraph", "Chunked by paragraph"],
] as const;

export const PASSAGE_ELA_EVIDENCE_OPTIONS = [
  ["quote_or_close_paraphrase", "Quote or close paraphrase"],
  ["exact_quote_required", "Exact quote required"],
  ["paragraph_reference", "Paragraph reference"],
] as const;

export const PASSAGE_ELA_SCAFFOLD_OPTIONS = [
  ["point_to_paragraph", "Point to the paragraph"],
  ["contrast_main_vs_detail", "Contrast main idea and detail"],
  ["sentence_starter", "Sentence starter"],
] as const;

export const PASSAGE_ELA_REREAD_OPTIONS = [["free_reprint", "Free reprint"]] as const;

export const LEARNING_SUPPORT_OPTIONS = [
  ["none", "None (No special pacing rules)"],
  ["adhd_focus_friendly", "ADHD focus-friendly (Extra-crisp turns, immediate hook, no multi-part instructions)"],
  ["dyslexia_reading_friendly", "Dyslexia reading-friendly (Simple phonics-friendly words, short lines, avoid dense paragraphs)"],
  ["ell_language_support", "ELL language support (Avoid idioms, explain figurative phrases, pair new terms with synonyms)"],
  ["math_or_test_anxiety", "Math or test anxiety (Frame checks as low-stakes puzzles, never mention tests or grades)"],
] as const;

export const INTEREST_TAG_OPTIONS = [
  ["sports_and_games", "Sports & games"],
  ["video_games", "Video games"],
  ["animals_and_nature", "Animals & nature"],
  ["space_and_science", "Space & science"],
  ["art_and_design", "Art & design"],
  ["music_and_dance", "Music & dance"],
  ["building_and_coding", "Building & coding"],
  ["cooking_and_food", "Cooking & food"],
  ["cars_and_trains", "Cars & trains"],
  ["stories_and_comics", "Stories & comics"],
] as const;

export const PERSONA_OPTIONS = [
  ["socratic_mentor", "Socratic mentor (Calm, respectful academic mentor without theatrical roleplay)"],
  ["coach", "Coach (Warm, encouraging coach — default)"],
  ["detective", "Detective (Curious investigator spotting clues and patterns)"],
  ["explorer", "Explorer (Field explorer discovering ideas alongside the learner)"],
  ["storyteller", "Storyteller (Narrative guide framing concepts as vivid scenes)"],
  ["sibling", "Sibling (Relatable, down-to-earth older sibling)"],
  ["wizard", "Wizard (Playful wizard bringing imaginative wonder)"],
] as const;

export const VOCABULARY_REGISTER_OPTIONS = [
  ["adaptive_to_child", "Adaptive to child (Match Layer 2 reading level & grade band — default)"],
  ["everyday_conversational", "Everyday conversational (Plain everyday words first; technical terms after)"],
  ["academic_precision", "Academic precision (Exact disciplinary terms early with a brief kid-friendly gloss)"],
  ["story_rich_expressive", "Story-rich expressive (Vivid phrasing within sentence-length cap)"],
] as const;

export const INTEREST_WEAVING_OPTIONS = [
  ["subtle_natural", "Subtle & natural (Weave into opening hook or 1 example when natural — default)"],
  ["frequent_thematic", "Frequent thematic (Frame scenarios and word problems around child interests)"],
  ["off", "Off (Neutral curriculum examples or fallback analogy domain)"],
] as const;

export const METAPHOR_OPTIONS = [
  ["everyday", "Everyday life (Default fallback analogy domain)"],
  ["games", "Video games & quests"],
  ["nature", "Nature & animals"],
  ["sports", "Sports & motion"],
  ["cooking", "Cooking & recipes"],
  ["scifi", "Space & sci-fi"],
] as const;

export const HUMOR_AND_WIT_OPTIONS = [
  ["light_warm", "Light & warm (Occasional warm, gentle wit — default)"],
  ["playful_banter", "Playful banter (Playful, witty energy on hooks and passes)"],
  ["none_straightforward", "None / straightforward (Zero jokes; clear and earnest throughout)"],
] as const;

export const SIDEKICK_OPTIONS = [
  ["none", "None (No sidekick — default)"],
  ["barnaby", "Barnaby the Badger"],
  ["pixel", "Pixel the Robot"],
  ["spark", "Spark the Dragon"],
] as const;

export function gradeBandForAge(age: number | null | undefined): string {
  if (age == null || Number.isNaN(age)) return "upper_elementary";
  if (age <= 7) return "early_elementary";
  if (age <= 10) return "upper_elementary";
  if (age <= 13) return "middle_school";
  return "high_school";
}

export function normalizeReadingLevelOption(raw: string | undefined | null): string {
  const val = (raw ?? "").trim().toLowerCase().replace(/-/g, "_").replace(/\s+/g, "_");
  if (READING_LEVEL_OPTIONS.some(([id]) => id === val)) return val;
  if (val === "early_reader" || val === "early" || val === "beginner") return "emerging";
  if (val === "middle_grade" || val === "elementary") return "early_fluent";
  if (val === "grade_level" || val === "standard") return "on_grade";
  if (val === "high_school" || val === "above_grade") return "advanced";
  if (val.includes("early") || val.includes("emerg")) return "emerging";
  if (val.includes("high") || val.includes("advanc")) return "advanced";
  return "on_grade";
}

export function normalizeExplanationStyleOption(raw: string | undefined | null): string {
  const val = (raw ?? "").trim().toLowerCase().replace(/-/g, "_").replace(/\s+/g, "_");
  if (EXPLANATION_STYLE_OPTIONS.some(([id]) => id === val)) return val;
  if (val.includes("visual") || val === "picture" || val === "spatial") return "visual_spatial";
  if (val.includes("story") || val === "narrative" || val === "analogy") return "story_and_analogy";
  if (val.includes("step") || val === "procedural") return "step_by_step";
  if (val === "verbal" || val.includes("rule") || val.includes("pattern")) return "pattern_and_rule";
  return "concrete_examples";
}

export const LAYER_FIELDS: LayerField[] = [
  {
    layer: "Layer 1, Component",
    name: "Course title",
    hover: "The name the intro and the course outro use. Set it on the course in KC Course Creator.",
    role: "Names the course when a piece starts and when the whole course is finished.",
    kind: "Configured",
    where: "KC Course Creator, /kc-studio",
  },
  {
    layer: "Layer 1, Component",
    name: "Course description",
    hover: "Why this course exists. The intro draws on it. Write that reason on the course.",
    role: "Gives the intro the reason this course exists.",
    kind: "Configured",
    where: "KC Course Creator, /kc-studio",
  },
  {
    layer: "Layer 1, Component",
    name: "Audience",
    hover: "The age band of the course. Wording stays inside it. Pick the band on the course.",
    role: "Keeps examples and sentences inside the course age band.",
    kind: "Configured",
    where: "KC Course Creator, /kc-studio",
  },
  {
    layer: "Layer 1, Component",
    name: "Kind",
    hover: "Mastery, time boxed, or curiosity. Kind changes depth. Time boxed shortens the intro and the close and forces the minimum struggle window. Curiosity allows one extra why after the unit is known.",
    role: "Selects depth, the close length, and whether a course outro can wait for one extra why.",
    kind: "Configured",
    where: "KC Course Creator, /kc-studio",
  },
  {
    layer: "Layer 1, Component",
    name: "Minutes",
    hover: "The budget for a time-boxed course. It is compared with minutes used. Leave it empty on mastery and curiosity.",
    role: "The time budget the prompt compares with minutes used.",
    kind: "Configured",
    where: "KC Course Creator, /kc-studio",
  },
  {
    layer: "Layer 1, Component",
    name: "Component title",
    hover: "The name of this component. The unit close uses it. Set it in KC Creator.",
    role: "Names the unit in the close.",
    kind: "Configured",
    where: "KC Creator, /kc-creator",
  },
  {
    layer: "Layer 1, Component",
    name: "Component code",
    hover: "Derived once from the title at creation, then stored. The close can name the unit by this code.",
    role: "The stable id of the component. The model cannot change it.",
    kind: "Derived",
    where: "Derived from the title when the component is created, then stored",
  },
  {
    layer: "Layer 1, Component",
    name: "Component description",
    hover: "A short summary of the component. The walk does not read it. Edit it on the component.",
    role: "A short summary. Orient and the topic turns do not read it.",
    kind: "Configured",
    where: "KC Creator, /kc-creator",
  },
  {
    layer: "Layer 1, Component",
    name: "Type",
    hover: "The active block type for this preview. The ten types are Topic / Goal, Multiple choice, Case study, Socratic, Curiosity, Worked example, Spot the flaw, Teach back, Retrieval check, and Explanatory walkthrough.",
    role: "Names the block the prompt is built for.",
    kind: "Configured",
    where: "KC Creator, /kc-creator",
  },
  {
    layer: "Layer 1, Component",
    name: "Core truth",
    hover: "The idea a pass must hold. It stays hidden until a real pass or a reveal when anti-spoiler is on.",
    role: "The evidence a pass must hold, and what a reveal may state.",
    kind: "Configured",
    where: "KC Creator, /kc-creator",
  },
  {
    layer: "Layer 1, Component",
    name: "Rubric lines",
    hover: "The evidence list for a checked move. The model names which points the answer met. The app decides the score.",
    role: "The evidence ids a checked move must meet before the app advances.",
    kind: "Configured",
    where: "KC Creator, /kc-creator",
  },
  {
    layer: "Layer 1, Component",
    name: "Misconceptions",
    hover: "Each row is a wrong move and the broken component it points at. A second hit on a stored wrong move leaves this unit fragile and opens that component.",
    role: "The only wrong moves the app will redirect on.",
    kind: "Configured",
    where: "KC Creator, /kc-creator",
  },
  {
    layer: "Layer 1, Component",
    name: "Prerequisite codes",
    hover: "Components the child should already know. The model cannot change these edges.",
    role: "The edges that set the support band.",
    kind: "Configured",
    where: "KC Creator, /kc-creator",
  },
  {
    layer: "Layer 1, Component",
    name: "Encompass codes",
    hover: "When this component becomes known, each encompassed component gains stability. The model cannot change these edges.",
    role: "The edges that receive a stability bump when this unit is known.",
    kind: "Configured",
    where: "KC Creator, /kc-creator",
  },
  {
    layer: "Layer 1, Component",
    name: "Transfer case",
    hover: "A later case the learner uses after stating the rule. Leave it empty to skip that substep. The model does not invent one.",
    role: "Adds the transfer move after the rule when the field is present.",
    kind: "Configured",
    where: "KC Creator, /kc-creator, stored in type fields",
  },
  {
    layer: "Layer 1, Component",
    name: "Counterfactual",
    hover: "A what-if after the learner defends a claim. Leave it empty to skip that substep.",
    role: "Adds the counterfactual move when the field is present and self-explanation is on.",
    kind: "Configured",
    where: "KC Creator, /kc-creator, stored in type fields",
  },
  {
    layer: "Layer 1, Component",
    name: "Substep",
    hover: "The active substep inside the current block. Leave it empty to use that block's opening substep. An explanatory walkthrough uses explain_topic, then summary_check. An ELA passage uses central_idea, cite_evidence, then craft_or_inference.",
    role: "Names which part of the block this preview turn is on.",
    kind: "Configured",
    where: "KC Prompt Tester",
  },
  {
    layer: "Layer 1, Component",
    name: "Topic index",
    hover: "Which topic an explanatory walkthrough is on, counted from 0. Other block types ignore it.",
    role: "Selects the topic the explanation prompt teaches.",
    kind: "Configured",
    where: "KC Prompt Tester",
  },
  {
    layer: "Layer 1, Component",
    name: "Move index",
    hover: "Which move this turn is, counted from the type's sequence and the session step.",
    role: "Tells the model which move to run, and stops a complete before the final move.",
    kind: "Derived",
    where: "Derived from the type sequence and kc_sessions.step",
  },
  {
    layer: "Layer 1, Component",
    name: "Move name",
    hover: "The name of the current move in that sequence.",
    role: "The label of the move the reply must carry.",
    kind: "Derived",
    where: "Derived from the type sequence and kc_sessions.step",
  },
  {
    layer: "Layer 1, Component",
    name: "Evidence",
    hover: "The ids this move must meet. Empty means the move is not checked.",
    role: "The app cannot advance a checked move when this list is empty in the decision.",
    kind: "Derived",
    where: "Derived from the move sequence",
  },
  {
    layer: "Layer 1, Component",
    name: "Choice widget",
    hover: "On for a multiple-choice block and for a case-study choice. Every other block is typed.",
    role: "Shows the on-screen choices. The model still does not set the score.",
    kind: "Derived",
    where: "Derived from the move",
  },
  {
    layer: "Layer 1, Component",
    name: "Prerequisite status",
    hover: "Known, fragile, or unknown for each prerequisite, from this child's states.",
    role: "Feeds the support band.",
    kind: "Derived",
    where: "Derived from this child's kc_states",
  },
  {
    layer: "Layer 1, Component",
    name: "Course position",
    hover: "This target's place among the course targets, such as 3 of 8, plus the previous and next titles. Empty at either end.",
    role: "The intro and the unit close use it so the child can hear where this piece sits.",
    kind: "Derived",
    where: "Derived from kc_goals.target_kc_ids and the component titles",
  },
  {
    layer: "Layer 2, Child",
    name: "Display name",
    hover: "The child's name. It is shown and is not edited in KC Tutor settings. The voice speaks to this name.",
    role: "The name the reply addresses.",
    kind: "Configured",
    where: "Shown on KC Tutor settings, /kc-tutor. Not edited there.",
  },
  {
    layer: "Layer 2, Child",
    name: "Age",
    hover: "The child's age (5 to 18). Sets developmental framing, example maturity, and the default grade band.",
    role: "Wording and example complexity.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "AI Model",
    hover:
      "Which model speaks for this child. The list is the same ChatGPT and DeepSeek models used elsewhere. The default is gpt-4.1. Changing it changes the voice of the reply. It does not change mastery.",
    role: "Selects the model for tutor speak and answer turns.",
    kind: "Configured",
    where: "Child settings, KC Tutor settings, parent settings, and the prompt tester. Saved on the student.",
  },
  {
    layer: "Layer 2, Child",
    name: "Grade band",
    hover: "Developmental band: early elementary (K-2), upper elementary (3-5), middle school (6-8), or high school (9-12). Auto-derived from age by default, or overridden.",
    role: "Frames example maturity and conceptual scaffolding for the learner's developmental stage.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Reading level",
    hover: "Reading and vocabulary level: emerging, early fluent, on grade, or advanced. Emerging and early fluent shorten sentences and define new terms right away.",
    role: "Calibrates vocabulary complexity and sentence structure.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Response length",
    hover: "How much text the tutor puts in a single turn: bite-sized (1-2 sentences), balanced (2-4 sentences), or detailed (fuller explanations with explicit connections).",
    role: "Controls cognitive load and sentence chunking per turn.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Expression style",
    hover: "What the child's own replies look like: one word or taps, short phrases, conversational, or analytical. Prevents penalizing brief typing.",
    role: "Tells the tutor how to interpret brief or detailed learner input and how to model replies back.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Explanation style",
    hover: "How explanations are represented: concrete examples, step by step, visual-spatial mental pictures, story and analogy, or pattern and rule.",
    role: "Chooses the primary cognitive representation when introducing or hinting at a concept.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Modality",
    hover: "Legacy representation alias mapped to Explanation style. Visual may ask for a described picture when the component has cases or steps.",
    role: "Backward-compatible representation field.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Challenge appetite",
    hover: "How the learner responds to difficulty: needs reassurance (normalize mistakes early), steady (normal scaffolding), or loves a challenge (stretch prompts and minimal hints).",
    role: "Adjusts scaffolding pace and how mistakes or stretch questions are framed.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Communication tone",
    hover: "Conversational energy: calm and gentle, warm and encouraging, playful and curious, or direct and matter-of-fact.",
    role: "Sets the affective warmth and directness of the tutor's replies.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Learning support",
    hover: "Optional pacing or language accommodations: none, ADHD focus-friendly, dyslexia reading-friendly, ELL language support, or math/test anxiety.",
    role: "Applies targeted UDL accommodations to sentence layout, idioms, and check framing.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Interest tags",
    hover: "Up to 4 curated interest categories (such as video games, animals & nature, or space & science) woven into analogies when Use interests is on.",
    role: "Provides reliable topic anchors for analogies when Use interests is on.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Interests",
    hover: "Specific favorites or personal context (up to 120 chars, such as Minecraft redstone or soccer goalie). Used when Use interests is on.",
    role: "Specific personal favorites for examples when Use interests is on.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor, saved on the student",
  },
  {
    layer: "Layer 2, Child",
    name: "Attempts on this move",
    hover: "How many tries the child has used on this move. It drives the hint ladder.",
    role: "Compared with the effective struggle window to choose the next hint.",
    kind: "Derived",
    where: "Derived from kc_sessions.move_attempts",
  },
  {
    layer: "Layer 2, Child",
    name: "Hint tier already given",
    hover: "The hint rung already used on this move: nudge, analogy, scaffold, or reveal.",
    role: "The rung the next miss steps up from.",
    kind: "Derived",
    where: "Derived from kc_sessions.hint_tier",
  },
  {
    layer: "Layer 2, Child",
    name: "Component status",
    hover: "Unknown, fragile, or known for this child on this component.",
    role: "Known only when the final move passes with no reveal.",
    kind: "Derived",
    where: "Derived from kc_states",
  },
  {
    layer: "Layer 2, Child",
    name: "Stability",
    hover: "How settled the component is for this child. Known rises to at least 1.0. An encompass link still adds its weight.",
    role: "Rises when the unit is known, and when another component encompasses this one.",
    kind: "Derived",
    where: "Derived from kc_states",
  },
  {
    layer: "Layer 2, Child",
    name: "Last answer",
    hover: "The child's most recent answer in this session.",
    role: "The answer the decision is checking. Phrase matching is not the pass rule.",
    kind: "Derived",
    where: "Derived from the session transcript",
  },
  {
    layer: "Layer 2, Child",
    name: "Last misconception",
    hover: "The stored wrong move matched on this move, if one was.",
    role: "A second hit on the same stored wrong move redirects and leaves the unit fragile.",
    kind: "Derived",
    where: "Derived from the session and the component's stored wrong moves",
  },
  {
    layer: "Layer 2, Child",
    name: "Minutes used",
    hover: "Time already spent on this course, compared with the course budget.",
    role: "Shows the time-boxed budget against time already used.",
    kind: "Derived",
    where: "Derived from session time",
  },
  {
    layer: "Layer 2, Child",
    name: "Support band",
    hover: "Ready when prerequisites are known, stretch when one is fragile, hold when one is unknown. Hold names the missing piece and the patch card. It does not teach that other component in this chat.",
    role: "Tells the tutor whether to stay, stretch, or point at a missing prerequisite.",
    kind: "Derived",
    where: "Derived from prerequisite statuses",
  },
  {
    layer: "Layer 3, Voice",
    name: "Persona",
    hover: "Tutor archetype framing metaphor (socratic_mentor, coach, detective, explorer, storyteller, sibling, wizard). Persona sets the framing metaphor while Layer 2 communication_tone governs emotional intensity.",
    role: "Sets the tutor's framing metaphor without overriding the child's Layer 2 communication tone.",
    kind: "Configured",
    where: "Admin Tutor settings, Layer 3, Voice. Saved on the tutor profile.",
  },
  {
    layer: "Layer 3, Voice",
    name: "Vocabulary register",
    hover: "Subject terminology register (adaptive_to_child, everyday_conversational, academic_precision, story_rich_expressive). Layer 2 exclusively owns sentence length and reading complexity; Vocabulary register only governs how disciplinary terms are introduced.",
    role: "Controls when and how technical subject vocabulary is introduced.",
    kind: "Configured",
    where: "Admin Tutor settings, Layer 3, Voice. Saved on the tutor profile.",
  },
  {
    layer: "Layer 3, Voice",
    name: "Interest weaving",
    hover: "How often to weave the child's Layer 2 interests into hooks and examples: subtle_natural (default), frequent_thematic, or off.",
    role: "Governs whether and how often the child's personal interests anchor examples.",
    kind: "Configured",
    where: "Admin Tutor settings, Layer 3, Voice. Saved on the tutor profile.",
  },
  {
    layer: "Layer 3, Voice",
    name: "Metaphors",
    hover: "Fallback analogy domain (everyday, games, nature, sports, cooking, scifi) used when interest_weaving is off, when the child has no Layer 2 interests set, or when personal interests do not fit cleanly.",
    role: "Provides the fallback analogy theme when child interests are off or do not fit.",
    kind: "Configured",
    where: "Admin Tutor settings, Layer 3, Voice. Saved on the tutor profile.",
  },
  {
    layer: "Layer 3, Voice",
    name: "Humor and wit",
    hover: "Humor & levity guardrail (light_warm, playful_banter, none_straightforward). Automatically suppressed on missed attempts (nudge/scaffold/reveal) and whenever Layer 2 learning_support is math_or_test_anxiety or communication_tone is calm_and_gentle.",
    role: "Controls warm wit on hooks and passes while enforcing safety suppression on misses and anxiety profiles.",
    kind: "Configured",
    where: "Admin Tutor settings, Layer 3, Voice. Saved on the tutor profile.",
  },
  {
    layer: "Layer 3, Voice",
    name: "Sidekick",
    hover: "Optional sidekick character (none, barnaby, pixel, spark). When enabled, voices at most one short line on hooks or hints and never asks a second competing question.",
    role: "Optional sidekick line on hooks or hints without adding a competing question.",
    kind: "Configured",
    where: "Admin Tutor settings, Layer 3, Voice. Saved on the tutor profile.",
  },
  {
    layer: "Layer 4, Guidance",
    name: "Orient framing",
    hover: "How the component outline is introduced before the first block: none, brief_hook, or elaborate_outline (time-boxed courses override to brief_hook).",
    role: "Shapes the opening orientation on Turn 1 before Block 1's prompt.",
    kind: "Configured",
    where: "Admin Tutor settings, Overarching Teaching Policy. Saved on the tutor profile.",
  },
  {
    layer: "Layer 4, Guidance",
    name: "Instructional stance",
    hover: "Default teaching philosophy when introducing concepts: direct_instruction_first, guided_discovery (default), or productive_challenge_first.",
    role: "Controls whether blocks model the rule first, pair an anchor with a guiding question, or let the learner try first.",
    kind: "Configured",
    where: "Admin Tutor settings, Overarching Teaching Policy. Saved on the tutor profile.",
  },
  {
    layer: "Layer 4, Guidance",
    name: "Scaffolding escalation",
    hover: "Contingent hint progression on nudge and scaffold turns: socratic_probing, progressive_nudge_then_scaffold (default), or worked_example_on_first_miss.",
    role: "Determines how hints escalate when the learner misses a step.",
    kind: "Configured",
    where: "Admin Tutor settings, Overarching Teaching Policy. Saved on the tutor profile.",
  },
  {
    layer: "Layer 4, Guidance",
    name: "Stay on course",
    hover: "Tangent handling policy: strict, brief_answer_then_return (default), or exploratory.",
    role: "Whether a tangent is redirected immediately, answered in one sentence, or briefly explored.",
    kind: "Configured",
    where: "Admin Tutor settings, Overarching Teaching Policy. Saved on the tutor profile.",
  },
  {
    layer: "Layer 4, Guidance",
    name: "Misconception policy",
    hover: "How stored misconceptions and distractor traps are handled: nudge_without_naming, explain_and_retry_once (default), or immediate_redirect.",
    role: "Governs whether a matched misconception is nudged, contrasted with one retry, or immediately redirected.",
    kind: "Configured",
    where: "Admin Tutor settings, Overarching Teaching Policy. Saved on the tutor profile.",
  },
  {
    layer: "Layer 4, Guidance",
    name: "Prerequisite support policy",
    hover: "How fragile or missing prerequisites in Layer 1 are supported: inline_micro_recap (default), scaffold_heavily, or no_special_adjustment.",
    role: "Shapes how the tutor supports fragile or missing prerequisite knowledge.",
    kind: "Configured",
    where: "Admin Tutor settings, Overarching Teaching Policy. Saved on the tutor profile.",
  },
  {
    layer: "Layer 5, Encouragement",
    name: "Encouragement style",
    hover: "Feedback praise policy on task attempts: process_praise (default — names the strategy or reasoning move), matter_of_fact_confirm, or minimal, while respecting Layer 2 needs_reassurance on misses.",
    role: "Sets the pedagogical praise rule on pass, nudge, and scaffold turns.",
    kind: "Configured",
    where: "Admin Tutor settings, Overarching Teaching Policy. Saved on the tutor profile.",
  },
  {
    layer: "Layer 6, Metacognition",
    name: "Close summary depth",
    hover: "Component close synthesis depth: concise, restate_in_learner_words, or diagnostic_strengths_and_gaps (default).",
    role: "Controls how the tutor synthesizes takeaways, strengths, and gaps when closing a component.",
    kind: "Configured",
    where: "Admin Tutor settings, Overarching Teaching Policy. Saved on the tutor profile.",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Reveals used",
    hover: "How many times a reveal has ended a move in this session. A reveal leaves the unit fragile.",
    role: "Counts reveals. A reveal blocks known.",
    kind: "Derived",
    where: "Derived from kc_sessions.reveals",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Off-course count",
    hover: "How many turns the model marked as off this component.",
    role: "Counts tangents. The score still comes from this component.",
    kind: "Derived",
    where: "Derived from kc_sessions.off_course_count",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Rubric points met",
    hover: "Evidence ids already met on this move. They are also stored on the model-prompt row.",
    role: "The running evidence list. An empty list cannot advance a checked move.",
    kind: "Derived",
    where: "Derived from the session, and stored on the model-prompt row",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Last four messages",
    hover: "The last four turns in this chat.",
    role: "The recent transcript the model reads.",
    kind: "Derived",
    where: "Derived from the session transcript",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Affect",
    hover: "Engaged, stuck, guessing, or frustrated, from the latest decision. Stuck or guessing adds one calm line when growth-mindset praise is on.",
    role: "Tells the encouragement line whether the child is stuck or guessing.",
    kind: "Derived",
    where: "Written from the model decision onto kc_sessions.affect",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Help requested",
    hover: "Whether the latest decision said the child asked for help.",
    role: "Recorded for the next turn. It does not by itself reveal the answer.",
    kind: "Derived",
    where: "Written from the model decision onto the session",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Last practiced",
    hover: "When this child last practiced this component.",
    role: "The timestamp on kc_states.",
    kind: "Derived",
    where: "Derived from kc_states.last_practiced",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Redirect pending",
    hover: "Whether a redirect to a broken component is already waiting.",
    role: "The patch card the fragile close can name.",
    kind: "Derived",
    where: "Derived from kc_sessions.redirect_kc_id",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Enrichment turns",
    hover: "How many enrichment stays this move has used. Two is the cap.",
    role: "Stops a stay once the cap is reached.",
    kind: "Derived",
    where: "Derived from kc_sessions.enrichment_turns",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Unit close",
    hover: "Whether this turn must include the unit close. The app sets the flag. The model writes the words. A known unit names the component and what the child can now do. A fragile unit says the unit is paused.",
    role: "Tells the reply to close the unit in the same turn that ends it.",
    kind: "Derived",
    where: "Set by the app when it ends the component",
  },
  {
    layer: "Layer 7, Feedback loop",
    name: "Course outro",
    hover: "Whether this turn must append the course outro. True when the unit close is required and every target component is known or fragile. Fragile stays fragile. The app sets the flag. The model writes the words.",
    role: "Appends the course complete line after the unit close, and only then.",
    kind: "Derived",
    where: "Set by the app when the unit ends known or fragile and every other target is known or fragile",
  },
  {
    layer: "Layer 2, Child",
    name: "Model",
    hover: "Which model speaks. Changing it changes the voice of the reply, not the moves or the score. The default stays gpt-4.1.",
    role: "Selects the model Vercel calls. It does not change mastery.",
    kind: "Configured",
    where: "KC Tutor settings, /kc-tutor. Kept on this page.",
  },
];

export function hoverFor(name: string): string {
  return LAYER_FIELDS.find((field) => field.name === name)?.hover ?? "";
}
