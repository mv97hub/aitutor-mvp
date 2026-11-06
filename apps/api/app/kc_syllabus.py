"""Syllabus for the KC Course Creator chat.

The chat drafts component titles. It does not write them. A title is a part of
the subject, the way the quest draft names sections of a subject instead of
slicing the course description. Kind decides how full the list is. A requested
count is honored with those parts, not with pieces of one sentence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_COMPONENTS = 16
_KINDS = ("mastery", "time_boxed", "curiosity")
_NUMBER_WORDS = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_NUMBER = (
    r"(\d{1,2}|twenty|nineteen|eighteen|seventeen|sixteen|fifteen|fourteen|"
    r"thirteen|twelve|eleven|ten|nine|eight|seven|six|five|four|three|two)"
)
_INSTRUCTION = re.compile(
    r"\b(?:please|draft|make|build|cover|give|want|need|include|explain|tell|ask|"
    r"write|create|minimum|component|components|mastery|master|curiosity|curious|"
    r"syllabus|minutes|minute|mins|min|time[\s-]?box)\b",
    re.IGNORECASE,
)
_THIN_TITLE = re.compile(
    r"^(?:course|new course|untitled|draft|zz|zz course)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Outline:
    name: str
    matchers: tuple[str, ...]
    mastery: tuple[str, ...]
    essentials: tuple[str, ...]
    curiosity: tuple[str, ...]
    deeper: tuple[str, ...]


def _pack(
    name: str,
    mastery: tuple[str, ...],
    essentials: tuple[str, ...],
    curiosity: tuple[str, ...],
    deeper: tuple[str, ...],
    matchers: tuple[str, ...] = (),
) -> Outline:
    outline = Outline(name, matchers, mastery, essentials, curiosity, deeper)
    _vet(outline)
    return outline


def _vet(outline: Outline) -> None:
    for label, group in (
        ("mastery", outline.mastery),
        ("essentials", outline.essentials),
        ("curiosity", outline.curiosity),
        ("deeper", outline.deeper),
    ):
        lowered = [item.lower() for item in group]
        if len(lowered) != len(set(lowered)):
            raise RuntimeError(f"Duplicate title in {outline.name} {label}")
        if any(not item.strip() for item in group):
            raise RuntimeError(f"Empty title in {outline.name} {label}")
    if len(outline.mastery) < 12 or len(outline.essentials) < 6 or len(outline.curiosity) < 6:
        raise RuntimeError(f"{outline.name} is too short to be a syllabus")
    if len(outline.curiosity) >= len(outline.mastery) or len(outline.essentials) >= len(outline.mastery):
        raise RuntimeError(f"{outline.name} does not get fuller for mastery")
    if len(outline.deeper) < 4:
        raise RuntimeError(f"{outline.name} cannot grow to a requested count")
    known = {item.lower() for item in (*outline.mastery, *outline.deeper)}
    for title in outline.essentials:
        if title.lower() not in known:
            raise RuntimeError(f"{outline.name} essential is not part of the subject: {title}")
    combined = [item.lower() for item in (*outline.mastery, *outline.deeper)]
    if len(combined) != len(set(combined)) or len(combined) < MAX_COMPONENTS:
        raise RuntimeError(f"{outline.name} repeats itself when the count grows")


def _g(*lines: str) -> tuple[str, ...]:
    return lines


_GEOMETRY = _pack(
    "Euclidean geometry",
    _g(
        "Points, lines, and angles",
        "Triangle angle sum",
        "Find the missing angle",
        "What congruence means",
        "Corresponding parts",
        "The included angle",
        "SAS versus SSA",
        "Angle-side-angle",
        "Side-side-side",
        "Why SSA fails",
        "Writing a congruence proof",
        "Fix a faulty congruence plan",
    ),
    _g(
        "Triangle angle sum",
        "Find the missing angle",
        "What congruence means",
        "SAS versus SSA",
        "Why SSA fails",
        "Fix a faulty congruence plan",
    ),
    _g(
        "Two triangles that look the same",
        "The angle hiding between the sides",
        "The test that locks one triangle",
        "The test that only looks like it locks",
        "Why the third side can swing two ways",
        "What you can actually claim",
    ),
    _g(
        "The exterior angle theorem",
        "The isosceles triangle theorem",
        "What congruence does not say about size",
        "Two triangles in one diagram",
    ),
    ("euclidean", "geometry", "congruent", "congruence", "triangle", "sas", "ssa"),
)

_PYTHAGORAS = _pack(
    "the Pythagorean theorem",
    _g(
        "The sides of a right triangle",
        "The hypotenuse",
        "What the Pythagorean theorem says",
        "Finding a missing hypotenuse",
        "Finding a missing leg",
        "Checking whether a triangle is right",
        "Why the two squares add",
        "Pythagorean triples",
        "Distance on a coordinate grid",
        "A diagram that hides the right angle",
        "Where the theorem does not apply",
        "Fix a faulty use of the theorem",
    ),
    _g(
        "What the Pythagorean theorem says",
        "Finding a missing hypotenuse",
        "Finding a missing leg",
        "Checking whether a triangle is right",
        "Why the two squares add",
        "Fix a faulty use of the theorem",
    ),
    _g(
        "A triangle with a square corner",
        "The longest side",
        "Why the two small squares add to the big one",
        "A triple that keeps showing up",
        "The triangle that looks right and is not",
        "What the theorem refuses to do",
    ),
    _g(
        "A proof without algebra",
        "The converse of the theorem",
        "A ladder against a wall",
        "When a side is longer than the hypotenuse",
    ),
    ("pythagorean", "pythagoras"),
)

_MACRO = _pack(
    "macroeconomics",
    _g(
        "Scarcity",
        "Opportunity cost",
        "Production possibilities",
        "Demand and price",
        "Supply",
        "Equilibrium",
        "A shift versus a movement",
        "Price elasticity",
        "A binding price ceiling",
        "A price floor",
        "Add up GDP",
        "Fix a faulty policy plan",
    ),
    _g(
        "Scarcity",
        "Opportunity cost",
        "Demand and price",
        "A binding price ceiling",
        "Add up GDP",
        "Fix a faulty policy plan",
    ),
    _g(
        "Why you cannot have everything",
        "The next best thing given up",
        "What happens when more people want the same goods",
        "The rule that empties the shelves",
        "The number that tries to add up an economy",
        "A plan that forgets the cost",
    ),
    _g(
        "Nominal and real GDP",
        "Inflation and the price level",
        "Unemployment and the labor force",
        "Fiscal policy and what it crowds out",
    ),
    ("macroeconomic", "macro", "opportunity cost", "price ceiling", "scarcity", "gdp", "supply and demand"),
)

_ROME = _pack(
    "ancient Rome",
    _g(
        "Rome before the Republic",
        "Republic before Empire",
        "What a republic is",
        "Consuls and a limited term",
        "Senate and assemblies",
        "Where a general's command ended",
        "Crossing the Rubicon",
        "What the crossing started",
        "From civil war to one ruler",
        "The titles of the emperor",
        "Why one man could not stay a citizen",
        "Titles are not a republic",
    ),
    _g(
        "Republic before Empire",
        "What a republic is",
        "Senate and assemblies",
        "Crossing the Rubicon",
        "What the crossing started",
        "Titles are not a republic",
    ),
    _g(
        "A city that refused kings",
        "Offices that had to be shared",
        "The river a general was not allowed to cross",
        "The day an army entered Italy",
        "Titles that dressed one man as the state",
        "What the Republic lost that day",
    ),
    _g(
        "The assemblies and who could vote",
        "Proscriptions after the civil war",
        "Augustus and the old titles",
        "What the Empire kept from the Republic",
    ),
    ("ancient rome", "roman republic", "roman empire", "rubicon", "caesar", "rome"),
)

_PHOTOSYNTHESIS = _pack(
    "photosynthesis",
    _g(
        "What a leaf takes in",
        "Chlorophyll",
        "The chloroplast",
        "Light-dependent reactions",
        "Splitting water",
        "ATP and NADPH",
        "The Calvin cycle",
        "Where the carbon in glucose comes from",
        "Why oxygen is released",
        "Limiting factors",
        "Photosynthesis and respiration",
        "Trace one carbon atom from air to sugar",
    ),
    _g(
        "What a leaf takes in",
        "Chlorophyll",
        "Light-dependent reactions",
        "The Calvin cycle",
        "Where the carbon in glucose comes from",
        "Why oxygen is released",
    ),
    _g(
        "A leaf that makes its own food",
        "The light that splits water",
        "The gas that becomes the sugar",
        "The oxygen that was never the goal",
        "What the leaf is doing in the dark",
        "Follow one carbon atom",
    ),
    _g(
        "The electron transport chain in the chloroplast",
        "Why a plant in the dark loses mass",
        "C3 and C4 plants",
        "A faulty account of where the mass comes from",
    ),
    ("photosynthesis", "chlorophyll", "calvin cycle", "chloroplast"),
)

_FRACTIONS = _pack(
    "fractions",
    _g(
        "What a fraction names",
        "Numerator and denominator",
        "Fractions on the number line",
        "Equivalent fractions",
        "Simplifying a fraction",
        "Comparing fractions",
        "Adding with the same denominator",
        "A common denominator",
        "Adding with different denominators",
        "Subtracting fractions",
        "Multiplying fractions",
        "Dividing by a fraction",
    ),
    _g(
        "What a fraction names",
        "Equivalent fractions",
        "Adding with the same denominator",
        "A common denominator",
        "Adding with different denominators",
        "Multiplying fractions",
    ),
    _g(
        "A piece of one whole",
        "Fractions that look different and name the same amount",
        "Why the denominators have to agree",
        "What multiplying a fraction does to the whole",
        "Why dividing by a fraction can make a larger number",
        "A share that is not a whole number of pieces",
    ),
    _g(
        "Mixed numbers",
        "Fractions and decimals",
        "Fractions and percents",
        "A word problem that mixes the operations",
    ),
    ("fraction", "numerator", "denominator"),
)

_ALGEBRA = _pack(
    "linear equations",
    _g(
        "What a variable stands for",
        "An expression versus an equation",
        "Keeping both sides equal",
        "Solving a one-step equation",
        "Solving a two-step equation",
        "Variables on both sides",
        "The distributive property in an equation",
        "Checking a solution",
        "A word problem into an equation",
        "No solution and infinitely many",
        "Where the method stops applying",
        "Fix a faulty solve",
    ),
    _g(
        "What a variable stands for",
        "Keeping both sides equal",
        "Solving a two-step equation",
        "Checking a solution",
        "A word problem into an equation",
        "Fix a faulty solve",
    ),
    _g(
        "A number hiding behind a letter",
        "The move that has to happen on both sides",
        "A solution that fails the original equation",
        "The story a word problem is actually telling",
        "An equation with no number that works",
        "What the letter was doing all along",
    ),
    _g(
        "Equations with parentheses",
        "Clearing a fraction in an equation",
        "Graphing the solution on a number line",
        "A system of two equations",
    ),
    ("linear equation", "algebra", "solve for"),
)

_NEWTON = _pack(
    "Newton's laws",
    _g(
        "Force and mass",
        "The first law and inertia",
        "The second law",
        "Calculating acceleration",
        "The third law and force pairs",
        "Why the pairs do not cancel",
        "Weight versus mass",
        "Friction",
        "A free-body diagram",
        "Net force",
        "A situation that mixes two laws",
        "Fix a faulty force plan",
    ),
    _g(
        "The first law and inertia",
        "The second law",
        "Calculating acceleration",
        "The third law and force pairs",
        "Why the pairs do not cancel",
        "Fix a faulty force plan",
    ),
    _g(
        "Why a passenger lurches when the bus stops",
        "The push that changes the motion",
        "The equal push that does not undo it",
        "The force people forget to draw",
        "A diagram that lies about the motion",
        "What the laws will not let you claim",
    ),
    _g(
        "Normal force",
        "Tension",
        "Inclined planes",
        "Action-reaction and a rocket",
    ),
    ("newton", "inertia", "f = ma", "force and mass"),
)

_WATER = _pack(
    "the water cycle",
    _g(
        "Where water on Earth sits",
        "Evaporation",
        "Condensation",
        "Clouds",
        "Precipitation",
        "Collection and runoff",
        "Transpiration",
        "Why the cycle has no first step",
        "What a drought interrupts",
        "Groundwater",
        "Energy from the sun driving the cycle",
        "Trace one drop",
    ),
    _g(
        "Evaporation",
        "Condensation",
        "Precipitation",
        "Collection and runoff",
        "Why the cycle has no first step",
        "Trace one drop",
    ),
    _g(
        "A puddle that disappears",
        "The cloud that used to be the ocean",
        "The drop that comes back down",
        "The plant that breathes water out",
        "The year the rain does not return",
        "The same drop, still moving",
    ),
    _g(
        "Humidity",
        "The water table",
        "Infiltration versus runoff",
        "A watershed",
    ),
    ("water cycle", "transpiration"),
)

_CELLS = _pack(
    "the cell",
    _g(
        "What a cell is",
        "Prokaryotic and eukaryotic cells",
        "The cell membrane",
        "Nucleus and DNA",
        "Mitochondria and energy",
        "Ribosomes and protein",
        "Plant cells and the chloroplast",
        "How materials cross the membrane",
        "Osmosis",
        "Mitosis",
        "Why cell structure limits cell size",
        "Trace one protein from instruction to membrane",
    ),
    _g(
        "What a cell is",
        "The cell membrane",
        "Nucleus and DNA",
        "Mitochondria and energy",
        "How materials cross the membrane",
        "Mitosis",
    ),
    _g(
        "The smallest thing that is alive",
        "A wall that chooses what gets in",
        "The instructions in the nucleus",
        "The organelle that pays for the work",
        "A cell about to become two",
        "Why a cell cannot just keep growing",
    ),
    _g(
        "The endoplasmic reticulum",
        "Active transport",
        "Stem cells and specialization",
        "A faulty picture of the animal cell",
    ),
    ("eukaryotic", "prokaryotic", "cell membrane", "mitosis", "organelle", "cell"),
)

_WWII = _pack(
    "the Second World War",
    _g(
        "The unsettled peace after 1918",
        "How the dictatorships came to power",
        "Appeasement",
        "The invasion of Poland",
        "The fall of France",
        "The Battle of Britain",
        "The Eastern Front",
        "Pearl Harbor and a world war",
        "The Holocaust",
        "Stalingrad, Midway, and D-Day",
        "Why the Axis lost",
        "The peace that followed",
    ),
    _g(
        "The unsettled peace after 1918",
        "Appeasement",
        "The invasion of Poland",
        "The Holocaust",
        "Stalingrad, Midway, and D-Day",
        "Why the Axis lost",
    ),
    _g(
        "A peace that left the next war waiting",
        "The bargain that was meant to stop a march",
        "The morning Poland was invaded",
        "A war that stopped being only European",
        "The murder the war was also for",
        "The day the maps had to be redrawn",
    ),
    _g(
        "The home front and rationing",
        "Occupation and resistance",
        "The atomic bombings",
        "What the settlement of 1945 did not settle",
    ),
    ("world war ii", "world war 2", "world war two", "holocaust", "pearl harbor"),
)

_FRENCH = _pack(
    "the French Revolution",
    _g(
        "The old regime",
        "The three estates",
        "Why the treasury broke",
        "The Tennis Court Oath",
        "The fall of the Bastille",
        "The Declaration of the Rights of Man",
        "From reform to a republic",
        "The Terror",
        "Why Napoleon could take the state",
        "What the Revolution changed",
        "What the Revolution did not change",
        "A faulty telling of the Revolution",
    ),
    _g(
        "The three estates",
        "Why the treasury broke",
        "The fall of the Bastille",
        "From reform to a republic",
        "The Terror",
        "Why Napoleon could take the state",
    ),
    _g(
        "A kingdom that could not pay its bills",
        "The oath in the tennis court",
        "The morning the Bastille fell",
        "The rights written down and the rights withheld",
        "The year the revolution turned on itself",
        "The soldier who picked up the state",
    ),
    _g(
        "The women's march on Versailles",
        "The civil constitution of the clergy",
        "War and the revolution",
        "The Directory",
    ),
    ("french revolution", "bastille", "estates-general", "robespierre"),
)

_AMERICAN = _pack(
    "the American Revolution",
    _g(
        "The colonies inside the empire",
        "Taxation without representation",
        "Protest, boycott, and tea",
        "From protest to war",
        "The Declaration of Independence",
        "Why a militia was not an army",
        "The alliance with France",
        "The home front",
        "Yorktown",
        "The Treaty of Paris",
        "What independence did not settle",
        "A faulty telling of the break with Britain",
    ),
    _g(
        "Taxation without representation",
        "From protest to war",
        "The Declaration of Independence",
        "The alliance with France",
        "Yorktown",
        "What independence did not settle",
    ),
    _g(
        "Subjects who started to call the taxes someone else's",
        "The night of the tea",
        "A letter that made the quarrel a new country",
        "An army that needed a winter and an ally",
        "The siege that ended the fighting",
        "The people the new country did not free",
    ),
    _g(
        "The Articles of Confederation",
        "Loyalists",
        "The revolutionary war at sea",
        "Slavery and the revolution",
    ),
    ("american revolution", "declaration of independence", "continental congress", "yorktown"),
)

_CLIMATE = _pack(
    "climate change",
    _g(
        "Weather versus climate",
        "The greenhouse effect",
        "Carbon dioxide and the other gases",
        "Where the extra carbon comes from",
        "How temperature and carbon track",
        "Ice, water vapor, and feedbacks",
        "The oceans as a store of heat",
        "What a climate model is claiming",
        "Mitigation and adaptation",
        "A trend versus a single hot year",
        "What the record does not yet settle",
        "A plan that treats a symptom as the cause",
    ),
    _g(
        "Weather versus climate",
        "The greenhouse effect",
        "Where the extra carbon comes from",
        "How temperature and carbon track",
        "Mitigation and adaptation",
        "A plan that treats a symptom as the cause",
    ),
    _g(
        "A hot day that is not a climate",
        "The blanket the atmosphere already was",
        "The carbon that used to be underground",
        "The ice that makes the warming faster",
        "The choice between cutting the cause and living with it",
        "The forecast that is not a promise about next Tuesday",
    ),
    _g(
        "Sea level",
        "Permafrost",
        "Climate and extreme weather",
        "A carbon budget",
    ),
    ("climate change", "greenhouse", "global warming"),
)

_PLATES = _pack(
    "plate tectonics",
    _g(
        "The crust is not one piece",
        "Continental and oceanic crust",
        "Convection in the mantle",
        "Divergent boundaries",
        "Convergent boundaries",
        "Transform boundaries",
        "Earthquakes at a boundary",
        "Volcanoes and subduction",
        "Evidence from fit, fossils, and the seafloor",
        "Why a mountain range sits where it does",
        "Hot spots",
        "A faulty map of a moving coast",
    ),
    _g(
        "The crust is not one piece",
        "Divergent boundaries",
        "Convergent boundaries",
        "Earthquakes at a boundary",
        "Evidence from fit, fossils, and the seafloor",
        "Why a mountain range sits where it does",
    ),
    _g(
        "A coast that is not where it used to be",
        "The seam where the seafloor is born",
        "The seam where the seafloor is destroyed",
        "The shake that marks a boundary",
        "The fossil that turns up on two continents",
        "The mountain that is still growing",
    ),
    _g(
        "Magnetic stripes on the seafloor",
        "The Ring of Fire",
        "Continental drift before the mechanism",
        "A boundary that is not a country border",
    ),
    ("plate tectonics", "subduction", "pangaea", "seafloor spreading"),
)

_CIRCUITS = _pack(
    "electric circuits",
    _g(
        "Charge",
        "Current",
        "Voltage",
        "Resistance",
        "Ohm's law",
        "A series circuit",
        "A parallel circuit",
        "Calculating current",
        "Why a short circuit is dangerous",
        "Power",
        "A meter on the wrong part of the circuit",
        "Fix a faulty circuit",
    ),
    _g(
        "Current",
        "Voltage",
        "Resistance",
        "Ohm's law",
        "A series circuit",
        "A parallel circuit",
    ),
    _g(
        "A loop that has to close",
        "The push around the loop",
        "The part that slows the flow",
        "The bulb that goes out and takes the others with it",
        "The bulb that stays lit when its neighbor dies",
        "The wire that should never have been a shortcut",
    ),
    _g(
        "Schematic symbols",
        "Kirchhoff's laws at a simple junction",
        "Batteries in series",
        "A household circuit and a fuse",
    ),
    ("ohm", "electric circuit", "series circuit", "parallel circuit", "voltage"),
)

_DIGESTION = _pack(
    "digestion",
    _g(
        "Why food has to change form",
        "The path from mouth to intestine",
        "Mechanical and chemical digestion",
        "Enzymes",
        "The stomach",
        "Absorption in the small intestine",
        "What the large intestine is for",
        "Why the stomach does not digest itself",
        "The liver and bile",
        "The pancreas",
        "What is not absorbed",
        "Trace one meal",
    ),
    _g(
        "Why food has to change form",
        "Mechanical and chemical digestion",
        "Enzymes",
        "Absorption in the small intestine",
        "Why the stomach does not digest itself",
        "Trace one meal",
    ),
    _g(
        "A sandwich that is not yet something a cell can use",
        "The teeth and the acid doing different jobs",
        "The enzyme that fits one kind of food",
        "The long tube where the food actually enters the blood",
        "The organ that does not eat itself",
        "What never needed to be absorbed",
    ),
    _g(
        "Peristalsis",
        "Villi",
        "The role of fiber",
        "A faulty claim that the stomach does all the work",
    ),
    ("digestive", "digestion", "peristalsis", "small intestine"),
)

_PYTHON = _pack(
    "Python",
    _g(
        "What a Python program runs",
        "Values and types",
        "Variables and assignment",
        "Expressions",
        "Conditionals",
        "Loops",
        "Functions",
        "Lists",
        "Debugging a wrong result",
        "A program that combines two of these",
        "Edge cases and bad input",
        "Fix a faulty program",
    ),
    _g(
        "Values and types",
        "Variables and assignment",
        "Conditionals",
        "Loops",
        "Functions",
        "Fix a faulty program",
    ),
    _g(
        "A file the computer reads from the top",
        "A name that holds a value",
        "The branch the program did not take",
        "The loop that ran one time too many",
        "The function that hid a mistake",
        "The input nobody tried",
    ),
    _g(
        "Dictionaries",
        "Reading an error message",
        "Returning a value versus printing it",
        "A test for one function",
    ),
    ("python",),
)

OUTLINES = (
    _PYTHAGORAS,
    _GEOMETRY,
    _MACRO,
    _ROME,
    _PHOTOSYNTHESIS,
    _FRACTIONS,
    _ALGEBRA,
    _NEWTON,
    _WATER,
    _CELLS,
    _WWII,
    _FRENCH,
    _AMERICAN,
    _CLIMATE,
    _PLATES,
    _CIRCUITS,
    _DIGESTION,
    _PYTHON,
)


def _lines(subject: str, patterns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(pattern.format(subject=subject) for pattern in patterns)


def _family_outline(family: str, subject: str) -> Outline:
    subject = subject.replace("{", "").replace("}", "")
    if family == "history":
        mastery = _lines(
            subject,
            (
                "{subject} before the familiar story",
                "Who held power when {subject} began",
                "The pressure that built up around {subject}",
                "The decision that changed {subject}",
                "What that decision set in motion for {subject}",
                "Who gained and who lost because of {subject}",
                "The turning point in the story of {subject}",
                "How the outcome of {subject} was locked in",
                "What people still misread about {subject}",
                "How the parts of the {subject} story depend on each other",
                "What the story of {subject} did not settle",
                "A faulty telling of {subject}",
            ),
        )
        essentials = (
            mastery[1],
            mastery[2],
            mastery[3],
            mastery[4],
            mastery[6],
            mastery[10],
        )
        curiosity = _lines(
            subject,
            (
                "The world just before {subject}",
                "The moment {subject} stopped being ordinary",
                "The choice in {subject} that could have gone the other way",
                "What followed for {subject}",
                "The part the usual story of {subject} leaves out",
                "The question {subject} still asks",
            ),
        )
        deeper = _lines(
            subject,
            (
                "A later generation of {subject}",
                "{subject} set beside a story it is confused with",
                "What changed in {subject} when one condition changed",
                "Pulling the story of {subject} together",
            ),
        )
    elif family == "science":
        mastery = _lines(
            subject,
            (
                "The phenomenon {subject} names",
                "The parts inside {subject}",
                "What goes into {subject} and what comes out",
                "The step-by-step of {subject}",
                "The rule {subject} follows",
                "A case that fits {subject}",
                "A case that only looks like {subject}",
                "Why {subject} happens",
                "What changes when one part of {subject} changes",
                "Where {subject} stops applying",
                "{subject} set beside the idea it is confused with",
                "Trace one case through {subject}",
            ),
        )
        essentials = (mastery[0], mastery[2], mastery[3], mastery[4], mastery[7], mastery[11])
        curiosity = _lines(
            subject,
            (
                "The first thing you can notice about {subject}",
                "The hidden step inside {subject}",
                "The case of {subject} that breaks the obvious guess",
                "Why {subject} has to work that way",
                "What {subject} leaves behind",
                "One case of {subject} followed all the way through",
            ),
        )
        deeper = _lines(
            subject,
            (
                "The measurement that tests {subject}",
                "A limit of {subject}",
                "Energy in {subject}",
                "A faulty diagram of {subject}",
            ),
        )
    elif family == "math":
        mastery = _lines(
            subject,
            (
                "What {subject} names",
                "The parts of {subject}",
                "The relationship {subject} states",
                "A worked case of {subject}",
                "The move students skip in {subject}",
                "A case that looks like {subject} and is not",
                "Why the method of {subject} works",
                "Checking a result in {subject}",
                "{subject} inside a larger problem",
                "Where the method of {subject} does not apply",
                "What a novice misreads in {subject}",
                "Fix a faulty use of {subject}",
            ),
        )
        essentials = (mastery[0], mastery[2], mastery[3], mastery[6], mastery[7], mastery[11])
        curiosity = _lines(
            subject,
            (
                "The question {subject} is quietly asking",
                "The move that makes {subject} work",
                "The case that looks like {subject} and fails",
                "Why that move is allowed",
                "A result in {subject} that should bother you",
                "Using {subject} on a problem that did not announce itself",
            ),
        )
        deeper = _lines(
            subject,
            (
                "A second method for {subject}",
                "{subject} on a diagram",
                "The units in {subject}",
                "A proof of the rule behind {subject}",
            ),
        )
    elif family == "literature":
        mastery = _lines(
            subject,
            (
                "The situation at the start of {subject}",
                "Who wants what in {subject}",
                "The constraint on those wants in {subject}",
                "The choice that turns {subject}",
                "What the language of {subject} is doing",
                "A scene in {subject} that only seems to say one thing",
                "How the plot of {subject} is built",
                "A motif that keeps returning in {subject}",
                "Why the ending of {subject} follows",
                "The character who misreads {subject}",
                "What {subject} refuses to settle",
                "Pulling the argument of {subject} together",
            ),
        )
        essentials = (mastery[0], mastery[1], mastery[3], mastery[4], mastery[8], mastery[10])
        curiosity = _lines(
            subject,
            (
                "The trouble already present at the start of {subject}",
                "The want that drives {subject}",
                "The scene in {subject} that changes the rest",
                "The line in {subject} that means two things",
                "The ending {subject} was walking toward",
                "The question {subject} leaves in the room",
            ),
        )
        deeper = _lines(
            subject,
            (
                "The setting as a pressure in {subject}",
                "A minor character who changes {subject}",
                "The form of {subject}",
                "A reading of {subject} that the text will not support",
            ),
        )
    elif family == "computing":
        mastery = _lines(
            subject,
            (
                "What a program is doing in {subject}",
                "Values and names in {subject}",
                "Decisions in {subject}",
                "Repetition in {subject}",
                "Functions in {subject}",
                "Collections in {subject}",
                "Tracing a wrong result in {subject}",
                "Input the program did not expect in {subject}",
                "A small program that uses two ideas from {subject}",
                "What {subject} does not do for you",
                "Edge cases in {subject}",
                "Fix a faulty program about {subject}",
            ),
        )
        essentials = (mastery[0], mastery[1], mastery[2], mastery[3], mastery[4], mastery[11])
        curiosity = _lines(
            subject,
            (
                "The instruction {subject} actually follows",
                "The name that held the wrong value in {subject}",
                "The branch {subject} did not take",
                "The loop in {subject} that ran once too often",
                "The function in {subject} that hid the mistake",
                "The input nobody tried in {subject}",
            ),
        )
        deeper = _lines(
            subject,
            (
                "Reading an error from {subject}",
                "Returning a value in {subject}",
                "A test for one piece of {subject}",
                "Data and code kept apart in {subject}",
            ),
        )
    else:
        mastery = _lines(
            subject,
            (
                "The question {subject} answers",
                "The objects {subject} studies",
                "The core claim of {subject}",
                "How a practitioner of {subject} works",
                "A standard case of {subject}",
                "The distinction {subject} depends on",
                "Why the core claim of {subject} holds",
                "Where {subject} stops applying",
                "{subject} on a new case",
                "What a novice gets wrong about {subject}",
                "How the parts of {subject} depend on each other",
                "A faulty account of {subject}",
            ),
        )
        essentials = (mastery[0], mastery[1], mastery[2], mastery[3], mastery[6], mastery[8])
        curiosity = _lines(
            subject,
            (
                "The puzzle that makes {subject} worth opening",
                "The first thing {subject} asks you to see",
                "The move inside {subject} that changes the picture",
                "Where that move in {subject} leads",
                "What a newcomer gets wrong about {subject}",
                "The question {subject} leaves open",
            ),
        )
        deeper = _lines(
            subject,
            (
                "A boundary case of {subject}",
                "{subject} set beside the idea it is confused with",
                "What changes when one part of {subject} changes",
                "Pulling {subject} together",
            ),
        )
    return _pack(subject, mastery, essentials, curiosity, deeper)


def _has(text: str, phrase: str) -> bool:
    suffix = "" if phrase.endswith("s") else "s?"
    return re.search(rf"\b{re.escape(phrase)}{suffix}\b", text) is not None


def _match_outline(text: str) -> Outline | None:
    best: Outline | None = None
    best_key = (0, 0)
    for outline in OUTLINES:
        matched = [phrase for phrase in outline.matchers if _has(text, phrase)]
        if not matched:
            continue
        key = (max(len(phrase) for phrase in matched), sum(len(phrase) for phrase in matched))
        if key > best_key:
            best = outline
            best_key = key
    return best


def _family(text: str) -> str:
    if re.search(r"\b(?:python|javascript|algorithm|programming|coding)\b", text):
        return "computing"
    if re.search(r"\b(?:novel|poem|play|shakespeare|hamlet|stanza|protagonist)\b", text):
        return "literature"
    if re.search(r"\b(?:algebra|equation|fraction|percent|ratio|theorem|arithmetic|geometry)\b", text):
        return "math"
    if re.search(
        r"\b(?:history|historical|founding|founded|revolution|empire|ancient|century|war|king|"
        r"queen|dynasty|republic|timeline)\b",
        text,
    ):
        return "history"
    if re.search(
        r"\b(?:energy|force|atom|molecule|cell|organism|planet|climate|circuit|reaction|"
        r"photosynthesis|gravity|evolution|biology|physics|chemistry)\b",
        text,
    ):
        return "science"
    return "default"


def _trim(subject: str) -> str:
    subject = re.sub(r"\s+", " ", subject).strip(" .,:;\"'")
    words = subject.split()
    if len(words) > 6:
        subject = " ".join(words[:6])
    if len(subject) > 42:
        shortened = subject[:42].rsplit(" ", 1)[0].strip()
        subject = shortened or subject[:42].strip()
    return subject or "this subject"


def _substantive_title(title: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", (title or "").strip())
    if not cleaned or _THIN_TITLE.match(cleaned):
        return None
    lowered = cleaned.lower()
    if lowered.startswith("zz ") or lowered.startswith("zz-"):
        return None
    return cleaned


def _subject_phrase(title: str, description: str) -> str:
    for source in (title, description):
        match = re.search(r"\bhistory of\s+([^.,;]+)", source or "", flags=re.IGNORECASE)
        if match:
            return _trim(match.group(1))
    substantive = _substantive_title(title)
    if substantive:
        stripped = re.sub(r"^(?:the|an|a)\s+", "", substantive, count=1, flags=re.IGNORECASE)
        return _trim(stripped)
    text = re.sub(r"\s+", " ", (description or "").strip())
    text = re.sub(
        r"^(?:please\s+)?(?:create|make|build|design)\s+(?:me\s+)?(?:a|an)\s+(?:short\s+|brief\s+)?course\s+(?:about|on|for)\s+",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^(?:a|an)\s+(?:short\s+|brief\s+)?course\s+(?:about|on|for)\s+",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    if not text or re.match(
        r"^(?:tell|explain|find|name|describe|understand|learn|include|place|show|compare)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return "this subject"
    subject = re.split(r"[.!?]\s+|\s+\b(?:include|including)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    return _trim(subject)


def _pasted_titles(message: str) -> list[str] | None:
    lines: list[str] = []
    for raw in (message or "").splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", raw).strip()
        if line:
            lines.append(line)
    if len(lines) < 2:
        return None
    if any(len(line) > 80 or len(line.split()) > 8 or "?" in line for line in lines):
        return None
    if _INSTRUCTION.search(message or ""):
        return None
    return lines[:40]


def _number(token: str) -> int | None:
    lowered = token.lower()
    if lowered.isdigit():
        value = int(lowered)
    else:
        value = _NUMBER_WORDS.get(lowered, 0)
    if value < 2:
        return None
    return value


def _count_request(message: str) -> tuple[str, int] | None:
    text = (message or "").lower()
    text = re.sub(r"\b\d{1,3}\s*(?:minutes|minute|mins|min)\b", " ", text)
    text = re.sub(r"\b\d{1,2}\s*-\s*\d{1,2}\b", " ", text)
    patterns = (
        ("min", rf"\b(?:minimum of|at least|no fewer than|no less than|at a minimum(?: of)?)\s+{_NUMBER}\b"),
        ("min", rf"\b{_NUMBER}\s+or more\b"),
        ("exact", rf"\b(?:exactly|only|just)\s+{_NUMBER}\b"),
        ("exact", rf"\b{_NUMBER}\s+(?:components?|parts?|sections?|items?)\b"),
        ("exact", rf"\b{_NUMBER}\b"),
    )
    for kind, pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = _number(match.group(1))
        if value is not None:
            return kind, value
    return None


def _explicit_kind(message: str) -> str | None:
    text = (message or "").lower()
    hits: list[tuple[int, str]] = []
    for kind, pattern in (
        ("time_boxed", r"\btime[\s-]?box"),
        ("curiosity", r"\bcuriosit|\bcurious path\b"),
        ("mastery", r"\bmastery\b|\bbe a master\b|\bas a master\b|\bmaster of\b"),
    ):
        match = re.search(pattern, text)
        if match:
            hits.append((match.start(), kind))
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def _resolve_kind(message: str, course_kind: str) -> str:
    explicit = _explicit_kind(message)
    if explicit:
        return explicit
    if re.search(r"\b\d{1,3}\s*(?:minutes|minute|mins|min)\b", (message or "").lower()):
        return "time_boxed"
    if course_kind in _KINDS:
        return course_kind
    return "mastery"


def _minutes(message: str, course_minutes: int | None) -> int | None:
    match = re.search(r"\b(\d{1,3})\s*(?:minutes|minute|mins|min)\b", (message or "").lower())
    if match:
        value = int(match.group(1))
        if value > 0:
            return value
    if isinstance(course_minutes, int) and course_minutes > 0:
        return course_minutes
    return None


def _span(minutes: int | None) -> int:
    """One component for every five minutes, at least three, and only as many as earn a place."""
    if minutes is None:
        return 4
    return max(3, min(MAX_COMPONENTS, minutes // 5))


def _unique(titles: list[str]) -> list[str]:
    seen: set[str] = set()
    chosen: list[str] = []
    for title in titles:
        cleaned = title.strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        chosen.append(cleaned)
    return chosen


def _pool(outline: Outline, kind: str) -> list[str]:
    if kind == "curiosity":
        primary = outline.curiosity
    elif kind == "time_boxed":
        primary = outline.essentials
    else:
        primary = outline.mastery
    return _unique([*primary, *outline.mastery, *outline.deeper])


def _natural(outline: Outline, kind: str, minutes: int | None) -> list[str]:
    if kind == "curiosity":
        return _unique(list(outline.curiosity))
    if kind == "time_boxed":
        span = _span(minutes)
        if span <= len(outline.essentials):
            return list(outline.essentials[:span])
        return _unique([*outline.mastery, *outline.deeper])[:span]
    return _unique(list(outline.mastery))


def _choose(outline: Outline, kind: str, minutes: int | None, count: tuple[str, int] | None) -> list[str]:
    pool = _pool(outline, kind)
    natural = _natural(outline, kind, minutes)
    if count is None:
        chosen = natural
    elif count[0] == "min":
        chosen = natural if len(natural) >= count[1] else pool[: count[1]]
    else:
        chosen = pool[: count[1]]
    chosen = _unique(chosen)[:MAX_COMPONENTS]
    if len(chosen) < 2 and len(pool) >= 2:
        chosen = pool[:2]
    return chosen


def _reply(
    *,
    kind: str,
    minutes: int | None,
    subject: str,
    titles: list[str],
    count: tuple[str, int] | None,
    sized_to_minutes: bool,
) -> str:
    n = len(titles)
    if kind == "time_boxed" and minutes:
        scope = f"a time-boxed course of {minutes} minutes"
    elif kind == "time_boxed":
        scope = "a time-boxed course"
    elif kind == "curiosity":
        scope = "a curiosity course"
    else:
        scope = "a mastery course"
    if kind == "curiosity":
        relation = f"It follows a path through {subject}."
    elif kind == "mastery":
        relation = f"It is the fuller breakdown of {subject}."
    elif sized_to_minutes:
        relation = f"It follows the structure of {subject} and is sized to the minutes."
    else:
        relation = f"It follows the structure of {subject}."
    asked = ""
    if count is not None:
        limit = "at least " if count[0] == "min" else ""
        asked = f" You asked for {limit}{count[1]}."
        if n < count[1]:
            asked += " These are the components that earn a place."
    return f"Draft of {n} components for {scope}. {relation}{asked} Nothing is saved until you push it."


def plan_component_titles(
    *,
    title: str,
    description: str,
    kind: str,
    minutes: int | None,
    message: str,
) -> tuple[list[str], str]:
    """Component titles for one draft. This does not write."""
    pasted = _pasted_titles(message)
    if pasted:
        return pasted, (
            f"Draft of {len(pasted)} components from the titles you listed. "
            "Nothing is saved until you push it."
        )
    text = f"{title or ''} {description or ''}".lower()
    outline = _match_outline(text)
    subject = _subject_phrase(title, description)
    if outline is None:
        outline = _family_outline(_family(text), subject)
        label = outline.name
    else:
        label = _substantive_title(title) or outline.name
        label = _trim(re.sub(r"^(?:the|an|a)\s+", "", label, count=1, flags=re.IGNORECASE))
    resolved = _resolve_kind(message, kind)
    resolved_minutes = _minutes(message, minutes)
    count = _count_request(message)
    titles = _choose(outline, resolved, resolved_minutes, count)
    sized = resolved == "time_boxed" and count is None and resolved_minutes is not None
    return titles, _reply(
        kind=resolved,
        minutes=resolved_minutes if resolved == "time_boxed" else None,
        subject=label,
        titles=titles,
        count=count,
        sized_to_minutes=sized,
    )
