export type TutorAvatarCategoryId =
  | "classic_mentor"
  | "animals_companions"
  | "mythic_fantasy"
  | "scifi_space_tech"
  | "science_discovery"
  | "exploration_nature"
  | "arts_music_creativity"
  | "sports_games_strategy";

export type TutorAvatarPreset = {
  id: string;
  label: string;
  category: TutorAvatarCategoryId;
  keywords: string;
  bg: string;
  fg: string;
  paths: readonly string[];
};

export const DEFAULT_AVATAR_PRESET = "default_circle";

export const TUTOR_AVATAR_CATEGORIES: readonly {
  id: TutorAvatarCategoryId;
  label: string;
  shortLabel: string;
}[] = [
  { id: "classic_mentor", label: "Classic & Mentor", shortLabel: "Classic & Mentor" },
  { id: "animals_companions", label: "Animals & Companions", shortLabel: "Animals" },
  { id: "mythic_fantasy", label: "Mythic & Fantasy", shortLabel: "Mythic" },
  { id: "scifi_space_tech", label: "Sci-Fi, Space & Tech", shortLabel: "Sci-Fi & Space" },
  { id: "science_discovery", label: "Science & Discovery", shortLabel: "Science" },
  { id: "exploration_nature", label: "Exploration & Nature", shortLabel: "Exploration & Nature" },
  { id: "arts_music_creativity", label: "Arts, Music & Creativity", shortLabel: "Arts & Music" },
  { id: "sports_games_strategy", label: "Sports, Games & Strategy", shortLabel: "Sports & Games" },
];

export const TUTOR_AVATAR_PRESETS: readonly TutorAvatarPreset[] = [
  // 1. Classic & Mentor (8)
  {
    id: "default_circle",
    label: "Default Neutral Gray Circle",
    category: "classic_mentor",
    keywords: "default neutral gray circle classic standard",
    bg: "#e2e8f0",
    fg: "#475569",
    paths: ["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"],
  },
  {
    id: "mentor_cap",
    label: "Graduation Cap",
    category: "classic_mentor",
    keywords: "mentor graduation cap scholar academic teacher",
    bg: "#e0e7ff",
    fg: "#3730a3",
    paths: [
      "M2 9l10-4 10 4-10 4L2 9Z",
      "M6 11v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5",
      "M20 9v6",
    ],
  },
  {
    id: "open_book",
    label: "Open Book",
    category: "classic_mentor",
    keywords: "open book reading literature study guide",
    bg: "#dbeafe",
    fg: "#1e40af",
    paths: [
      "M2 5h6a4 4 0 0 1 4 4v11a3 3 0 0 0-3-3H2V5Z",
      "M22 5h-6a4 4 0 0 0-4 4v11a3 3 0 0 1 3-3h7V5Z",
    ],
  },
  {
    id: "scroll_quill",
    label: "Scroll & Quill",
    category: "classic_mentor",
    keywords: "scroll quill parchment writing history sage",
    bg: "#fef3c7",
    fg: "#92400e",
    paths: [
      "M6 4h9a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z",
      "M8 8h5M8 12h5M8 16h3",
      "M19 4c1.5 1.5 1.5 4 0 5.5L14 15l-2 1 1-2 5.5-5.5",
    ],
  },
  {
    id: "lightbulb",
    label: "Bright Idea Bulb",
    category: "classic_mentor",
    keywords: "lightbulb bright idea spark insight invention",
    bg: "#fef9c3",
    fg: "#854d0e",
    paths: [
      "M9 18h6M10 21h4",
      "M12 3a6 6 0 0 0-3.8 10.6c.5.5.8 1.2.8 1.9v.5h6v-.5c0-.7.3-1.4.8-1.9A6 6 0 0 0 12 3Z",
    ],
  },
  {
    id: "lantern",
    label: "Guiding Lantern",
    category: "classic_mentor",
    keywords: "lantern guide light path lamp warm",
    bg: "#ffedd5",
    fg: "#9a3412",
    paths: [
      "M9 4h6M10 4V2h4v2",
      "M7 7h10l-1 11H8L7 7Z",
      "M7 20h10M12 10v5",
    ],
  },
  {
    id: "glasses_scholar",
    label: "Scholar Glasses",
    category: "classic_mentor",
    keywords: "glasses scholar spectacles wise reader",
    bg: "#e0e7ff",
    fg: "#312e81",
    paths: [
      "M6.5 14a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z",
      "M17.5 14a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z",
      "M10 10.5h4M3 10.5H2M22 10.5h-1",
    ],
  },
  {
    id: "chalkboard",
    label: "Lesson Board",
    category: "classic_mentor",
    keywords: "chalkboard blackboard classroom lesson teacher",
    bg: "#dcfce7",
    fg: "#166534",
    paths: [
      "M3 5h18v12H3V5Z",
      "M2 17h20M7 9h5M7 13h8M16 13h2",
      "M8 17l-2 4M16 17l2 4",
    ],
  },

  // 2. Animals & Companions (8)
  {
    id: "owl",
    label: "Wise Owl",
    category: "animals_companions",
    keywords: "owl wise bird night Athena feathers",
    bg: "#fef3c7",
    fg: "#78350f",
    paths: [
      "M6 6l2 2h8l2-2v9a6 6 0 0 1-12 0V6Z",
      "M9.5 11a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM14.5 11a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z",
      "M11 13l1 1.5L13 13",
    ],
  },
  {
    id: "fox",
    label: "Clever Fox",
    category: "animals_companions",
    keywords: "fox clever orange woodland forest companion",
    bg: "#ffedd5",
    fg: "#c2410c",
    paths: [
      "M4 5l4 5h8l4-5-2 11-6 4-6-4L4 5Z",
      "M9.5 12.5h.5M14 12.5h.5M11 16h2",
    ],
  },
  {
    id: "badger",
    label: "Friendly Badger",
    category: "animals_companions",
    keywords: "badger barnaby burrow stripes woodland",
    bg: "#f1f5f9",
    fg: "#1e293b",
    paths: [
      "M5 7a3 3 0 0 1 3-2h8a3 3 0 0 1 3 2l1 7-8 5-8-5 1-7Z",
      "M10 5v11M14 5v11M11 15h2",
    ],
  },
  {
    id: "dolphin",
    label: "Playful Dolphin",
    category: "animals_companions",
    keywords: "dolphin ocean sea leap smart marine",
    bg: "#e0f2fe",
    fg: "#0369a1",
    paths: [
      "M4 16c2-6 7-10 13-9 2 .3 3 1.8 3 3-2 0-3.5.8-4.5 2-2 2.4-5.5 3.5-8.5 3l-3 3v-2Z",
      "M11 7l1-3 2 3",
    ],
  },
  {
    id: "turtle",
    label: "Steady Turtle",
    category: "animals_companions",
    keywords: "turtle tortoise shell steady patient green",
    bg: "#dcfce7",
    fg: "#15803d",
    paths: [
      "M6 14a6 6 0 0 1 12 0H6Z",
      "M18 13a2 2 0 1 0 3 0 2 2 0 0 0-3 0ZM4 14h14",
      "M8 14v3M16 14v3M12 8v6",
    ],
  },
  {
    id: "lion",
    label: "Brave Lion",
    category: "animals_companions",
    keywords: "lion mane brave courage king cat",
    bg: "#fef08a",
    fg: "#a16207",
    paths: [
      "M12 3l2.5 2 3-.5 1 3 2.5 2-1.5 3 .5 3-3 1-1.5 2.5-3.5-1-3.5 1L7.5 16.5l-3-1 .5-3-1.5-3 2.5-2 1-3 3 .5L12 3Z",
      "M9.5 11.5h.5M14 11.5h.5M10.5 14.5h3",
    ],
  },
  {
    id: "penguin",
    label: "Curious Penguin",
    category: "animals_companions",
    keywords: "penguin ice arctic bird waddle cute",
    bg: "#dbeafe",
    fg: "#1e3a8a",
    paths: [
      "M8 9a4 4 0 0 1 8 0v8a3 3 0 0 1-3 3H11a3 3 0 0 1-3-3V9Z",
      "M6 11l2-1v5l-2-1v-3ZM18 11l-2-1v5l2-1v-3Z",
      "M11 9.5l1 1 1-1",
    ],
  },
  {
    id: "octopus",
    label: "Multi-Tasking Octopus",
    category: "animals_companions",
    keywords: "octopus tentacles ocean clever sea",
    bg: "#f3e8ff",
    fg: "#6b21a8",
    paths: [
      "M7 10a5 5 0 0 1 10 0v3H7v-3Z",
      "M6 13c0 3-2 4-2 6M9 13v6M12 13v6M15 13v6M18 13c0 3 2 4 2 6",
      "M10 10h.5M13.5 10h.5",
    ],
  },

  // 3. Mythic & Fantasy (8)
  {
    id: "dragon",
    label: "Friendly Dragon",
    category: "mythic_fantasy",
    keywords: "dragon spark wings mythic fire fantasy",
    bg: "#fee2e2",
    fg: "#b91c1c",
    paths: [
      "M5 7l3-3 2 3h4l2-3 3 3-2 9-6 4-6-4-2-9Z",
      "M9 11h1M14 11h1M10 15h4",
    ],
  },
  {
    id: "wizard_hat",
    label: "Wizard Hat",
    category: "mythic_fantasy",
    keywords: "wizard hat magic mage spell stars",
    bg: "#ede9fe",
    fg: "#5b21b6",
    paths: [
      "M3 18h18",
      "M6 18L13 4l3 7 2 7H6Z",
      "M11 13l1-1 1 1-1 1-1-1Z",
    ],
  },
  {
    id: "phoenix",
    label: "Rising Phoenix",
    category: "mythic_fantasy",
    keywords: "phoenix wings flame fire rise bird",
    bg: "#ffedd5",
    fg: "#c2410c",
    paths: [
      "M12 4l2 4 6-2-3 6 3 4-6-1-2 5-2-5-6 1 3-4-3-6 6 2 2-4Z",
    ],
  },
  {
    id: "unicorn",
    label: "Star Unicorn",
    category: "mythic_fantasy",
    keywords: "unicorn horn magic star horse",
    bg: "#fce7f3",
    fg: "#9d174d",
    paths: [
      "M15 3l-4 5",
      "M7 9l4-1 5 3-1 6H8v-5l-1-3Z",
      "M12 11h.5",
    ],
  },
  {
    id: "griffin",
    label: "Guardian Griffin",
    category: "mythic_fantasy",
    keywords: "griffin eagle lion wings guardian",
    bg: "#fef3c7",
    fg: "#92400e",
    paths: [
      "M4 8l5 2 3-5 3 5 5-2-3 7-5 4-5-4-3-7Z",
      "M11 12l1 1.5 1-1.5",
    ],
  },
  {
    id: "crystal_orb",
    label: "Crystal Orb",
    category: "mythic_fantasy",
    keywords: "crystal orb ball fortune magic glow",
    bg: "#e0e7ff",
    fg: "#4338ca",
    paths: [
      "M12 17a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z",
      "M7 20h10l-1.5-3h-7L7 20Z",
      "M10 8a3 3 0 0 0-2 2",
    ],
  },
  {
    id: "magic_wand",
    label: "Sparkle Wand",
    category: "mythic_fantasy",
    keywords: "magic wand star sparkle spell",
    bg: "#fae8ff",
    fg: "#86198f",
    paths: [
      "M4 20L15 9",
      "M17 3l1 2.5L20.5 6.5 18 7.5 17 10l-1-2.5L13.5 6.5 16 5.5 17 3Z",
      "M8 6v2M7 7h2",
    ],
  },
  {
    id: "castle_tower",
    label: "Castle Tower",
    category: "mythic_fantasy",
    keywords: "castle tower fortress kingdom quest",
    bg: "#e2e8f0",
    fg: "#334155",
    paths: [
      "M6 5h2v2h2V5h4v2h2V5h2v5l-1 10H7L6 10V5Z",
      "M10 20v-4a2 2 0 0 1 4 0v4",
    ],
  },

  // 4. Sci-Fi, Space & Tech (8)
  {
    id: "robot",
    label: "Friendly Robot",
    category: "scifi_space_tech",
    keywords: "robot pixel bot ai android tech",
    bg: "#cffafe",
    fg: "#155e75",
    paths: [
      "M12 3v3M9 3h6",
      "M5 8h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2Z",
      "M9 12h1M14 12h1M9 16h6",
    ],
  },
  {
    id: "rocket",
    label: "Space Rocket",
    category: "scifi_space_tech",
    keywords: "rocket launch spaceship blastoff",
    bg: "#dbeafe",
    fg: "#1d4ed8",
    paths: [
      "M12 3c3 2.5 4.5 6 4.5 10.5L12 17l-4.5-3.5C7.5 9 9 5.5 12 3Z",
      "M7.5 12L5 15v3l3-1M16.5 12l2.5 3v3l-3-1",
      "M12 9.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z",
    ],
  },
  {
    id: "astronaut",
    label: "Astronaut Helmet",
    category: "scifi_space_tech",
    keywords: "astronaut helmet space explorer visor",
    bg: "#e0e7ff",
    fg: "#312e81",
    paths: [
      "M6 11a6 6 0 0 1 12 0v5a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2v-5Z",
      "M8 10h8v4H8v-4Z",
    ],
  },
  {
    id: "planet_ring",
    label: "Ringed Planet",
    category: "scifi_space_tech",
    keywords: "planet saturn ring space orbit cosmos",
    bg: "#ede9fe",
    fg: "#4c1d95",
    paths: [
      "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z",
      "M3 15c2 2 14-2 18-6",
    ],
  },
  {
    id: "satellite",
    label: "Orbiting Satellite",
    category: "scifi_space_tech",
    keywords: "satellite orbit space signal solar",
    bg: "#e0f2fe",
    fg: "#075985",
    paths: [
      "M9 9l6 6",
      "M4 8l4-4 3 3-4 4-3-3ZM13 17l4-4 3 3-4 4-3-3Z",
      "M6 18a4 4 0 0 1 4 4",
    ],
  },
  {
    id: "ufo_saucer",
    label: "Star Cruiser",
    category: "scifi_space_tech",
    keywords: "ufo saucer starship cruiser galaxy",
    bg: "#ccfbf1",
    fg: "#115e59",
    paths: [
      "M7 11a5 4 0 0 1 10 0",
      "M3 12h18c-1 2.5-4.5 4-9 4s-8-1.5-9-4Z",
      "M8 18l-1 2M12 18v2M16 18l1 2",
    ],
  },
  {
    id: "circuit_chip",
    label: "AI Circuit",
    category: "scifi_space_tech",
    keywords: "circuit chip cpu silicon ai compute",
    bg: "#cffafe",
    fg: "#0e7490",
    paths: [
      "M7 7h10v10H7V7Z",
      "M10 10h4v4h-4v-4Z",
      "M9 4v3M15 4v3M9 17v3M15 17v3M4 9h3M4 15h3M17 9h3M17 15h3",
    ],
  },
  {
    id: "telescope",
    label: "Stargazer Telescope",
    category: "scifi_space_tech",
    keywords: "telescope astronomy stars sky observe",
    bg: "#dbeafe",
    fg: "#1e40af",
    paths: [
      "M4 11l14-5 2 4-14 5-2-4Z",
      "M11 13l-3 7M11 13l4 7M11 13v7",
    ],
  },

  // 5. Science & Discovery (8)
  {
    id: "atom",
    label: "Atomic Orbit",
    category: "science_discovery",
    keywords: "atom physics nucleus electron science",
    bg: "#e0f2fe",
    fg: "#0284c7",
    paths: [
      "M12 12.5a.5.5 0 1 0 0-1 .5.5 0 0 0 0 1Z",
      "M5 12c0-2.2 3.1-4 7-4s7 1.8 7 4-3.1 4-7 4-7-1.8-7-4Z",
      "M8.5 6C10.4 4.9 13.7 7 15.6 10.4s1.9 7.1 0 8.2-5.2-1-7.1-4.4-1.9-7.1 0-8.2Z",
    ],
  },
  {
    id: "microscope",
    label: "Lab Microscope",
    category: "science_discovery",
    keywords: "microscope biology lab cells zoom",
    bg: "#dcfce7",
    fg: "#15803d",
    paths: [
      "M10 4h3l-1 7h-2l1-7Z",
      "M8 14h8M14 8a5 5 0 0 1 0 10H6",
      "M5 20h14",
    ],
  },
  {
    id: "beaker",
    label: "Chemistry Flask",
    category: "science_discovery",
    keywords: "beaker flask chemistry potion experiment lab",
    bg: "#d1fae5",
    fg: "#047857",
    paths: [
      "M9 3h6M10 3v6l-5 8a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-8V3",
      "M7 15h10",
    ],
  },
  {
    id: "dna_helix",
    label: "DNA Helix",
    category: "science_discovery",
    keywords: "dna helix genetics biology strand",
    bg: "#f3e8ff",
    fg: "#7e22ce",
    paths: [
      "M7 4c0 5 10 5 10 10s-10 5-10 6",
      "M17 4c0 5-10 5-10 10s10 5 10 6",
      "M8 7h8M8 17h8",
    ],
  },
  {
    id: "magnet",
    label: "Horseshoe Magnet",
    category: "science_discovery",
    keywords: "magnet horseshoe force poles physics",
    bg: "#fee2e2",
    fg: "#b91c1c",
    paths: [
      "M6 4h3v7a3 3 0 0 0 6 0V4h3v7a6 6 0 0 1-12 0V4Z",
      "M6 7h3M15 7h3",
    ],
  },
  {
    id: "prism_light",
    label: "Light Prism",
    category: "science_discovery",
    keywords: "prism light spectrum optics triangle",
    bg: "#fef3c7",
    fg: "#b45309",
    paths: [
      "M12 4L4 19h16L12 4Z",
      "M2 12l6-1M15 10l7-2M16 13l6 1",
    ],
  },
  {
    id: "gears",
    label: "Engineering Gears",
    category: "science_discovery",
    keywords: "gears engineering mechanics machine cog",
    bg: "#e2e8f0",
    fg: "#334155",
    paths: [
      "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
      "M12 4v2M12 18v2M4 12h2M18 12h2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M17.7 6.3l-1.4 1.4M7.7 16.3l-1.4 1.4",
    ],
  },
  {
    id: "globe",
    label: "World Globe",
    category: "science_discovery",
    keywords: "globe world earth geography planet",
    bg: "#dbeafe",
    fg: "#1d4ed8",
    paths: [
      "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z",
      "M4 12h16M12 4c2.5 2.5 2.5 13.5 0 16M12 4c-2.5 2.5-2.5 13.5 0 16",
    ],
  },

  // 6. Exploration & Nature (8)
  {
    id: "compass",
    label: "Explorer Compass",
    category: "exploration_nature",
    keywords: "compass north navigate explorer direction",
    bg: "#fef3c7",
    fg: "#92400e",
    paths: [
      "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z",
      "M15 9l-2 5-5 2 2-5 5-2Z",
    ],
  },
  {
    id: "mountain",
    label: "Mountain Peak",
    category: "exploration_nature",
    keywords: "mountain peak summit climb outdoor",
    bg: "#dcfce7",
    fg: "#166534",
    paths: [
      "M3 19L10 6l4 7 3-4 4 10H3Z",
      "M8 10l2 2 2-2",
    ],
  },
  {
    id: "magnifying_glass",
    label: "Detective Lens",
    category: "exploration_nature",
    keywords: "magnifying glass detective clue search lens",
    bg: "#e0e7ff",
    fg: "#3730a3",
    paths: [
      "M11 17a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z",
      "M15.5 15.5L20 20",
    ],
  },
  {
    id: "treasure_map",
    label: "Quest Map",
    category: "exploration_nature",
    keywords: "treasure map quest trail adventure route",
    bg: "#fef9c3",
    fg: "#854d0e",
    paths: [
      "M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2V6Z",
      "M9 4v14M15 6v14",
    ],
  },
  {
    id: "campfire",
    label: "Story Campfire",
    category: "exploration_nature",
    keywords: "campfire flame story outdoor warm logs",
    bg: "#ffedd5",
    fg: "#c2410c",
    paths: [
      "M12 4c2 3 4 5 4 8a4 4 0 0 1-8 0c0-3 2-5 4-8Z",
      "M5 19l14-3M5 16l14 3",
    ],
  },
  {
    id: "oak_tree",
    label: "Mighty Oak",
    category: "exploration_nature",
    keywords: "oak tree forest nature leaf growth",
    bg: "#dcfce7",
    fg: "#15803d",
    paths: [
      "M12 4a6 6 0 0 0-5 9.3A4 4 0 0 0 9 16h6a4 4 0 0 0 2-2.7A6 6 0 0 0 12 4Z",
      "M12 16v5M9 21h6",
    ],
  },
  {
    id: "sunburst",
    label: "Warm Sun",
    category: "exploration_nature",
    keywords: "sunburst sun bright warm daylight",
    bg: "#fef08a",
    fg: "#a16207",
    paths: [
      "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
      "M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1",
    ],
  },
  {
    id: "ocean_wave",
    label: "Ocean Wave",
    category: "exploration_nature",
    keywords: "ocean wave sea water surf tide",
    bg: "#e0f2fe",
    fg: "#0369a1",
    paths: [
      "M3 12c2-2 4-2 6 0s4 2 6 0 4-2 6 0",
      "M3 17c2-2 4-2 6 0s4 2 6 0 4-2 6 0",
    ],
  },

  // 7. Arts, Music & Creativity (8)
  {
    id: "palette",
    label: "Artist Palette",
    category: "arts_music_creativity",
    keywords: "palette artist paint color studio",
    bg: "#fce7f3",
    fg: "#9d174d",
    paths: [
      "M12 3a9 9 0 0 0 0 18c1.5 0 2.5-1 2.5-2.5 0-.7-.3-1.3-.7-1.8-.4-.4-.6-1-.6-1.7 0-1.4 1.1-2.5 2.5-2.5H17a4 4 0 0 0 4-4c0-3-4-5.5-9-5.5Z",
      "M8 10h.5M10 7h.5M14 7h.5",
    ],
  },
  {
    id: "music_note",
    label: "Melody Note",
    category: "arts_music_creativity",
    keywords: "music note song melody rhythm",
    bg: "#ede9fe",
    fg: "#6d28d9",
    paths: [
      "M9 17V6l10-2v11",
      "M7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM17 17a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
    ],
  },
  {
    id: "headphones",
    label: "Studio Headphones",
    category: "arts_music_creativity",
    keywords: "headphones audio music listen studio",
    bg: "#e0e7ff",
    fg: "#4338ca",
    paths: [
      "M4 14v-2a8 8 0 0 1 16 0v2",
      "M4 14h2a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H4v-5ZM18 14h2v5h-2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1Z",
    ],
  },
  {
    id: "theater_masks",
    label: "Storyteller Masks",
    category: "arts_music_creativity",
    keywords: "theater masks drama stage storyteller",
    bg: "#fae8ff",
    fg: "#86198f",
    paths: [
      "M4 5h10v7a5 5 0 0 1-10 0V5Z",
      "M14 9h6v6a4 4 0 0 1-6 3.5",
      "M7 9h1M10 9h1M7.5 12.5c1 .8 2 .8 3 0",
    ],
  },
  {
    id: "camera",
    label: "Creative Lens",
    category: "arts_music_creativity",
    keywords: "camera photo lens picture film",
    bg: "#f1f5f9",
    fg: "#334155",
    paths: [
      "M4 8h3l2-2h6l2 2h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z",
      "M12 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    ],
  },
  {
    id: "origami_bird",
    label: "Origami Crane",
    category: "arts_music_creativity",
    keywords: "origami bird crane paper craft fold",
    bg: "#cffafe",
    fg: "#0e7490",
    paths: [
      "M3 9l7 3 9-7-5 10 5 5-9-3-4 3 1-6-4-5Z",
    ],
  },
  {
    id: "paintbrush",
    label: "Paintbrush",
    category: "arts_music_creativity",
    keywords: "paintbrush art draw sketch canvas",
    bg: "#ffedd5",
    fg: "#c2410c",
    paths: [
      "M18 4l2 2-8 8-2-2 8-8Z",
      "M10 12c-2 0-3.5 1.5-3.5 3.5 0 1.2-.8 2-2 2.5 2 .5 5.5 0 5.5-3 0-1 .5-2 2-1",
    ],
  },
  {
    id: "sparkles",
    label: "Creative Sparkles",
    category: "arts_music_creativity",
    keywords: "sparkles stars shine magic creative",
    bg: "#fef9c3",
    fg: "#a16207",
    paths: [
      "M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5Z",
      "M18 15l1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2Z",
    ],
  },

  // 8. Sports, Games & Strategy (8)
  {
    id: "chess_knight",
    label: "Strategy Knight",
    category: "sports_games_strategy",
    keywords: "chess knight strategy board game tactics",
    bg: "#e2e8f0",
    fg: "#1e293b",
    paths: [
      "M7 19h10M8 16h8",
      "M9 16l1-5-3-1 2-5 4 1 3 3-2 7",
    ],
  },
  {
    id: "trophy",
    label: "Champion Trophy",
    category: "sports_games_strategy",
    keywords: "trophy cup champion winner gold",
    bg: "#fef3c7",
    fg: "#b45309",
    paths: [
      "M7 4h10v5a5 5 0 0 1-10 0V4Z",
      "M7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3",
      "M12 14v5M8 19h8",
    ],
  },
  {
    id: "puzzle_piece",
    label: "Puzzle Master",
    category: "sports_games_strategy",
    keywords: "puzzle piece logic brainteaser fit",
    bg: "#dbeafe",
    fg: "#1d4ed8",
    paths: [
      "M6 7h4a2 2 0 1 1 4 0h4v4a2 2 0 1 1 0 4v4H6V7Z",
    ],
  },
  {
    id: "soccer_ball",
    label: "Soccer Ball",
    category: "sports_games_strategy",
    keywords: "soccer ball football sport team field",
    bg: "#dcfce7",
    fg: "#166534",
    paths: [
      "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z",
      "M12 9l3 2-1 3.5h-4L9 11l3-2Z",
    ],
  },
  {
    id: "basketball",
    label: "Basketball",
    category: "sports_games_strategy",
    keywords: "basketball court hoop sport orange",
    bg: "#ffedd5",
    fg: "#c2410c",
    paths: [
      "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z",
      "M4 12h16M12 4v16M6.5 6.5c3 2.5 3 8.5 0 11M17.5 6.5c-3 2.5-3 8.5 0 11",
    ],
  },
  {
    id: "gamepad",
    label: "Quest Controller",
    category: "sports_games_strategy",
    keywords: "gamepad controller video game quest play",
    bg: "#ede9fe",
    fg: "#5b21b6",
    paths: [
      "M6 8h12a3 3 0 0 1 3 3l-1 5a2 2 0 0 1-3.5 1L14 14h-4l-2.5 3A2 2 0 0 1 4 16l-1-5a3 3 0 0 1 3-3Z",
      "M8 10v3M6.5 11.5h3M15.5 11h.5M17 12.5h.5",
    ],
  },
  {
    id: "target_bullseye",
    label: "Bullseye Target",
    category: "sports_games_strategy",
    keywords: "target bullseye archery focus goal",
    bg: "#fee2e2",
    fg: "#b91c1c",
    paths: [
      "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z",
      "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
      "M12 12.5a.5.5 0 1 0 0-1 .5.5 0 0 0 0 1Z",
    ],
  },
  {
    id: "stopwatch",
    label: "Speed Coach",
    category: "sports_games_strategy",
    keywords: "stopwatch timer speed coach clock",
    bg: "#cffafe",
    fg: "#0e7490",
    paths: [
      "M10 3h4M12 3v3",
      "M12 20a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z",
      "M12 10v3l2 2",
    ],
  },
];

const PRESET_BY_ID: Record<string, TutorAvatarPreset> = Object.fromEntries(
  TUTOR_AVATAR_PRESETS.map((item) => [item.id, item]),
);

export function getTutorAvatarPreset(id?: string | null): TutorAvatarPreset {
  const key = (id ?? "").trim();
  return PRESET_BY_ID[key] ?? PRESET_BY_ID[DEFAULT_AVATAR_PRESET];
}
