"""Idempotent seed: four students and the lesson blocks.

Running this twice does not duplicate rows. An existing plan is left as edited,
except Fractions, which is rewritten in place into blocks. The lesson id stays
the same, so classes that already point at it still open.
"""

import copy

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.flow import topic_in_use
from app.models import Checkpoint, LessonPlan, Student, Topic
from app.queries import checkpoint_in_use

STUDENTS = [
    {"slug": "iron-man", "display_name": "Iron Man", "age": 10},
    {"slug": "storm", "display_name": "Storm", "age": 10},
    {"slug": "spider-man", "display_name": "Spider-Man", "age": 11},
    {"slug": "wolverine", "display_name": "Wolverine", "age": 16},
]

PREAMBLE = (
    "You are a warm, patient math tutor for a child who is about 8 to 10 years old. "
    "Use everyday objects, short sentences, and encouragement. One step at a time."
)

def _rows(*rows: tuple[str, str, int]) -> list[dict]:
    return [{"id": row_id, "text": text, "weight": weight} for row_id, text, weight in rows]


def _hints(nudge: str, analogy: str, scaffold: str) -> dict:
    return {"nudge": nudge, "analogy": analogy, "scaffold": scaffold}


TOPICS = [
    {
        "title": "Parts of a whole",
        "learning_goal": (
            "A fraction names equal parts of a whole. The denominator is how many equal "
            "parts the whole was split into. The numerator is how many of those parts we mean."
        ),
        "tutor_instructions": (
            "Use one pizza, then one chocolate bar. Do not give the answer before they try. "
            "The chocolate-bar block is a choice widget: the taps are already graded."
        ),
        "checkpoints": [
            {
                "kind": "discovery",
                "objective": "A fraction names equal parts of one whole.",
                "tutor_prompt": (
                    "A pizza is cut into 4 equal slices. You eat 1 slice. What fraction did you "
                    "eat, and what does the bottom number mean?"
                ),
                "rubric": "1/4, and the bottom number is the 4 equal slices.",
                "pass_criteria": "Says 1/4 or one fourth, and knows the bottom number counts the equal slices.",
                "rubric_rows": _rows(
                    ("fourths", "Says 1/4 or one fourth.", 60),
                    ("denominator", "Says the bottom number is the 4 equal slices.", 40),
                ),
                "hint_ladder": _hints(
                    "How many equal slices is the whole pizza?",
                    "The bottom number is the number of equal slices. The top is how many you ate.",
                    "The pizza has 4 equal slices and you ate 1, so it is 1/4. The bottom number is the denominator.",
                ),
                "pass_score": 70,
            },
            {
                "kind": "quiz",
                "objective": "Name the fraction for part of a chocolate bar.",
                "tutor_prompt": "A chocolate bar has 3 equal pieces and you have 2 of them. Pick the fraction.",
                "rubric": "The choice 2/3 is correct. The written line should say the bottom number is the 3 equal pieces.",
                "pass_criteria": "Chooses 2/3.",
                "rubric_rows": _rows(
                    ("choice", "The choice is 2/3.", 70),
                    ("why", "The explanation says the denominator is the 3 equal pieces.", 30),
                ),
                "hint_ladder": _hints(
                    "The bottom number is how many equal pieces the bar was split into.",
                    "If a bar is 3 equal squares and you hold 2, you hold two of the three.",
                    "You have 2 of 3 equal pieces, which is 2/3.",
                ),
                "pass_score": 70,
                "quiz": {
                    "type": "single",
                    "prompt": "What fraction of the bar do you have?",
                    "choices": [
                        {"id": "a", "text": "2/3", "misconception": ""},
                        {
                            "id": "b",
                            "text": "3/2",
                            "misconception": "That puts the whole bar on top. The bottom number is how many equal pieces.",
                        },
                        {
                            "id": "c",
                            "text": "1/3",
                            "misconception": "The top number is how many pieces you have, not how many are left.",
                        },
                        {
                            "id": "d",
                            "text": "2/5",
                            "misconception": "The bottom number is the equal pieces of this bar, which is 3.",
                        },
                    ],
                    "answer": "a",
                    "explain": True,
                    "misconception": "Check which number counts the equal pieces.",
                },
            },
            {
                "kind": "teach_back",
                "objective": "Teach the bot what the numerator and the denominator mean.",
                "tutor_prompt": (
                    "Pretend I don't know fractions. Explain what the numerator and the denominator "
                    "mean, using the pizza."
                ),
                "rubric": "Denominator is how many equal parts. Numerator is how many of those parts we mean.",
                "pass_criteria": "Both words are explained with the pizza.",
                "rubric_rows": _rows(
                    ("denominator", "The denominator is how many equal parts.", 50),
                    ("numerator", "The numerator is how many of those parts we mean.", 50),
                ),
                "hint_ladder": _hints(
                    "Which number tells how many slices the pizza was cut into?",
                    "The bottom number names the equal slices. The top number names how many you mean.",
                    "Denominator: 4 equal slices. Numerator: the 1 slice you ate.",
                ),
                "pass_score": 70,
            },
        ],
    },
    {
        "title": "Same denominator",
        "learning_goal": (
            "When two fractions have the same denominator, the larger numerator is the larger amount."
        ),
        "tutor_instructions": (
            "Keep the denominator the same. Picture equal slices. Do not teach cross-multiplying."
        ),
        "checkpoints": [
            {
                "kind": "discovery",
                "objective": "Compare fractions that share a denominator.",
                "tutor_prompt": "Which is more pizza, 1/4 or 3/4, and why?",
                "rubric": "3/4, because the slices are the same size and 3 is more than 1.",
                "pass_criteria": "Chooses 3/4 and gives a reason about more equal parts.",
                "rubric_rows": _rows(
                    ("choice", "Chooses 3/4.", 60),
                    ("reason", "Says the slices match, so more slices is more pizza.", 40),
                ),
                "hint_ladder": _hints(
                    "Are the slices the same size in both fractions?",
                    "Same size slices: the bigger top number is more pizza.",
                    "3/4 is more than 1/4 because you have three of the same slices instead of one.",
                ),
                "pass_score": 70,
            },
            {
                "kind": "teach_back",
                "objective": "Explain how to compare fractions with the same denominator.",
                "tutor_prompt": "Teach me how to tell which is bigger, 2/5 or 4/5, without a trick.",
                "rubric": "4/5, because both are fifths and 4 is more than 2.",
                "pass_criteria": "Says 4/5 and why the equal parts make the numerator decide.",
                "rubric_rows": _rows(
                    ("choice", "Says 4/5 is bigger.", 50),
                    ("reason", "Says the fifths are the same size and 4 is more than 2.", 50),
                ),
                "hint_ladder": _hints(
                    "What does the 5 on the bottom tell you about the pieces?",
                    "Both fractions are fifths. Compare how many fifths.",
                    "4/5 is bigger because four same-size pieces is more than two.",
                ),
                "pass_score": 70,
            },
        ],
    },
]

READING_PREAMBLE = (
    "You are a warm, patient reading tutor for a child who is about 8 to 10 years old. "
    "Use short sentences and one short passage at a time."
)

READING_TOPICS = [
    {
        "title": "Main idea",
        "learning_goal": (
            "The main idea is what a short passage is mostly about, not one small detail."
        ),
        "tutor_instructions": (
            "Read one short passage in the chat. Ask only about the main idea. "
            "Do not start a second story."
        ),
        "checkpoints": [
            {
                "kind": "teach",
                "tutor_prompt": (
                    "Read this passage, then ask what it is mostly about: 'A fox looked for a "
                    "den before the snow. She tried a hollow log, then a pile of leaves, and "
                    "curled up where the wind could not reach.' The main idea is that the fox "
                    "finds a warm place to sleep. When the student says that, call "
                    "advance_checkpoint. If they name only the log or the leaves, say those are "
                    "details and ask again."
                ),
                "rubric": "",
                "pass_criteria": (
                    "The student says the passage is mostly about the fox finding a warm place to sleep."
                ),
            },
            {
                "kind": "practice",
                "tutor_prompt": (
                    "Read this and let them try: 'Mina packed an apple, a sandwich, and a note "
                    "from her dad. She checked the list twice so nothing would be left on the "
                    "table.' The main idea is that Mina makes sure her lunch is packed. Hints are "
                    "allowed. First hint: what did Mina do in the whole passage? When they say "
                    "she packed her lunch, call record_checkpoint_result with passed true and "
                    "short feedback, then advance_checkpoint."
                ),
                "rubric": "The main idea is Mina packing her lunch so she does not forget anything.",
                "pass_criteria": "The student says Mina is packing her lunch.",
            },
            {
                "kind": "quiz",
                "tutor_prompt": (
                    "Scored quiz. Read this and do not say the main idea first: 'The streetlights "
                    "blinked on. Cars slowed, and people opened umbrellas as the rain got louder.' "
                    "Ask what the passage is mostly about. Grade with the rubric, call "
                    "record_checkpoint_result, and call advance_checkpoint only if they passed."
                ),
                "rubric": (
                    "Pass, score 100: the passage is mostly about rain starting and people getting "
                    "ready for it. Score 50 and passed false if they mention only umbrellas or "
                    "only cars. Score 0 and passed false if they invent a different story."
                ),
                "pass_criteria": "The main idea is that rain is starting and people get ready for it.",
            },
        ],
    },
]

SCIENCE_PREAMBLE = (
    "You are a warm, patient science tutor for a child who is about 8 to 10 years old. "
    "Use ice, water, and steam. Short sentences. One step at a time."
)

SCIENCE_TOPICS = [
    {
        "title": "Solids, liquids, and gases",
        "learning_goal": (
            "A solid keeps its shape, a liquid pours, and a gas spreads out to fill the space."
        ),
        "tutor_instructions": (
            "Use ice, a puddle, and steam. Do not teach molecules or chemical formulas."
        ),
        "checkpoints": [
            {
                "kind": "teach",
                "tutor_prompt": (
                    "Explain three states with things they can picture: an ice cube keeps its "
                    "shape, so it is a solid; juice pours, so it is a liquid; steam spreads "
                    "through the air, so it is a gas. Then ask: a puddle of water is which state, "
                    "and why? When they say liquid because it pours or takes the shape of the "
                    "puddle, call advance_checkpoint. If they say solid or gas, explain the puddle "
                    "once more and ask again."
                ),
                "rubric": "",
                "pass_criteria": "The student says a puddle is a liquid and gives a reason about pouring or shape.",
            },
            {
                "kind": "practice",
                "tutor_prompt": (
                    "Ask: is a rock a solid, a liquid, or a gas? Hints are allowed. First hint: "
                    "does a rock keep its shape when you set it down? When they say solid because "
                    "it keeps its shape, call record_checkpoint_result with passed true and short "
                    "feedback, then advance_checkpoint."
                ),
                "rubric": "A rock is a solid because it keeps its shape.",
                "pass_criteria": "The student says a rock is a solid and mentions its shape.",
            },
            {
                "kind": "quiz",
                "tutor_prompt": (
                    "Scored quiz. Ask: steam from a kettle is which state, and how do you know? "
                    "Do not say gas first. Grade with the rubric, call record_checkpoint_result, "
                    "and call advance_checkpoint only if they passed."
                ),
                "rubric": (
                    "Pass, score 100, only if they say gas and explain that steam spreads or has "
                    "no shape you can hold. If they say gas with no reason, score 50 and passed "
                    "false. If they say liquid or solid, score 0 and passed false."
                ),
                "pass_criteria": "Steam is a gas because it spreads out and does not keep a shape.",
            },
        ],
    },
]

SUPER_PREAMBLE = (
    "You are a warm writing tutor for a child who is about 9 to 11. "
    "Talk about prompts: the job, who it is for, and what good looks like. Short sentences."
)

SUPER_TOPICS = [
    {
        "title": "A prompt that helps",
        "learning_goal": "A strong prompt says the job, the audience, and what good looks like.",
        "tutor_instructions": (
            "Stay on one story prompt about a dog who is afraid of rain. "
            "The spot-the-flaw and ordering blocks grade themselves."
        ),
        "checkpoints": [
            {
                "kind": "discovery",
                "objective": "Name the job, the reader, and what good looks like.",
                "tutor_prompt": (
                    "You want a story about a dog who is afraid of rain, for a 9 year old, with a "
                    "happy ending. What would you type so a bot knows the job, who it is for, and "
                    "what good looks like?"
                ),
                "rubric": "Names the job, the 9 year old reader, and a happy ending.",
                "pass_criteria": "The reply includes the job, the audience, and what good looks like.",
                "rubric_rows": _rows(
                    ("job", "Asks for a story about a dog who is afraid of rain.", 40),
                    ("audience", "Says it is for a 9 year old.", 30),
                    ("good", "Says what good looks like, such as a happy ending.", 30),
                ),
                "hint_ladder": _hints(
                    "What do you want the bot to make?",
                    "A prompt can say: write a story, for a 9 year old, and end it happily.",
                    "Job: a story about a dog afraid of rain. Audience: a 9 year old. Good: a happy ending.",
                ),
                "pass_score": 70,
            },
            {
                "kind": "quiz",
                "objective": "Spot the prompt that leaves the job, the reader, and the finish line out.",
                "tutor_prompt": "Read the three prompts. One of them has the flaw. Pick that one.",
                "rubric": "The flaw is the prompt that never names the job, the reader, or what good looks like.",
                "pass_criteria": "Selects the empty prompt.",
                "rubric_rows": _rows(
                    ("flaw", "Selects the prompt that says only 'Write something good.'", 100),
                ),
                "hint_ladder": _hints(
                    "Which prompt never says what to make?",
                    "A strong prompt names the job, the reader, and the finish line. One of these names none of them.",
                    "'Write something good' is the flaw. It has no job, no reader, and no finish line.",
                ),
                "pass_score": 70,
                "quiz": {
                    "type": "flaw",
                    "prompt": "Which prompt has the flaw?",
                    "choices": [
                        {
                            "id": "clear",
                            "text": "Write a 6 sentence story for a 9 year old about a dog who is afraid of rain. End with the dog stepping outside.",
                            "misconception": "That prompt names the job, the reader, and the ending.",
                        },
                        {
                            "id": "empty",
                            "text": "Write something good.",
                            "misconception": "This prompt never says the job, the reader, or what good looks like.",
                        },
                        {
                            "id": "thin",
                            "text": "Write a story.",
                            "misconception": "A job without an audience or a finish line is thin, but it still names the job.",
                        },
                    ],
                    "answer": "empty",
                    "explain": True,
                    "misconception": "Look for the prompt that leaves out the job, the reader, and the finish line.",
                },
            },
            {
                "kind": "quiz",
                "objective": "Order the parts of a prompt.",
                "tutor_prompt": "Put the parts of a super prompt in the order you would give them.",
                "rubric": "Job, then audience, then what good looks like.",
                "pass_criteria": "The order is job, audience, then what good looks like.",
                "rubric_rows": _rows(
                    ("order", "The order is the job, then who it is for, then what good looks like.", 100),
                ),
                "hint_ladder": _hints(
                    "What should the bot hear first: the job, or the ending?",
                    "Tell the bot what to make, then who it is for, then what good looks like.",
                    "Order: the job, then the 9 year old, then the happy ending.",
                ),
                "pass_score": 70,
                "quiz": {
                    "type": "order",
                    "prompt": "Put these prompt parts in the order you would give them.",
                    "choices": [
                        {"id": "good", "text": "What good looks like: a happy ending, in 6 sentences.", "misconception": ""},
                        {"id": "job", "text": "The job: write a story about a dog who is afraid of rain.", "misconception": ""},
                        {"id": "who", "text": "Who it is for: a 9 year old.", "misconception": ""},
                    ],
                    "answer": ["job", "who", "good"],
                    "explain": False,
                    "misconception": "Start with the job, then who it is for, then what good looks like.",
                },
            },
            {
                "kind": "teach_back",
                "objective": "Teach the three parts of a super prompt.",
                "tutor_prompt": "Teach me the three parts of a super prompt, in your own words.",
                "rubric": "Job, audience, and what good looks like.",
                "pass_criteria": "Names all three parts.",
                "rubric_rows": _rows(
                    ("job", "The job is what you want made.", 34),
                    ("audience", "The audience is who it is for.", 33),
                    ("good", "What good looks like is how you will know it worked.", 33),
                ),
                "hint_ladder": _hints(
                    "What are you asking the bot to make?",
                    "Three parts: the job, who reads it, and what good looks like.",
                    "Job, audience, and a finish line you can check.",
                ),
                "pass_score": 70,
            },
        ],
    },
]

SHIFTS_PREAMBLE = (
    "You are a patient math tutor for a student who is about 15 to 17. "
    "Use precise language and short steps. This lesson is function shifts, not elementary arithmetic."
)

SHIFTS_TOPICS = [
    {
        "title": "Shifts of a function",
        "learning_goal": (
            "Adding a number outside the function shifts the graph vertically. "
            "A change inside the parentheses shifts the graph horizontally the other way."
        ),
        "tutor_instructions": (
            "Do not assign this to a younger student. The multiple choice grades itself. "
            "Use the stored misconception when a choice is wrong. Do not regrade the tap."
        ),
        "checkpoints": [
            {
                "kind": "discovery",
                "objective": "Describe a vertical shift.",
                "tutor_prompt": (
                    "The graph of y = f(x) is a parabola opening up with its vertex at the origin. "
                    "What happens to the graph when the equation becomes y = f(x) + 3?"
                ),
                "rubric": "The graph moves up 3.",
                "pass_criteria": "Says the graph shifts up by 3.",
                "rubric_rows": _rows(
                    ("direction", "Says the graph moves up.", 50),
                    ("amount", "Says the shift is 3 units.", 50),
                ),
                "hint_ladder": _hints(
                    "Does the +3 change the input or the output?",
                    "A number added outside the function moves every output by that amount.",
                    "y = f(x) + 3 shifts the graph up 3.",
                ),
                "pass_score": 70,
            },
            {
                "kind": "quiz",
                "objective": "Read a horizontal shift from a point.",
                "tutor_prompt": "A point on y = f(x) is (2, 5). Decide where it goes on y = f(x - 4).",
                "rubric": "(6, 5). A change inside the parentheses moves the input the other way.",
                "pass_criteria": "Chooses (6, 5).",
                "rubric_rows": _rows(
                    ("point", "The image of (2, 5) is (6, 5).", 70),
                    ("why", "The explanation says x - 4 shifts the graph right by 4.", 30),
                ),
                "hint_ladder": _hints(
                    "Is the 4 inside the parentheses or outside the function?",
                    "Inside the parentheses, the graph moves the opposite direction of the sign.",
                    "f(x - 4) shifts right 4, so (2, 5) goes to (6, 5).",
                ),
                "pass_score": 70,
                "quiz": {
                    "type": "single",
                    "prompt": "The graph of y = f(x) has a point at (2, 5). Where does that point go on y = f(x - 4)?",
                    "choices": [
                        {"id": "right", "text": "(6, 5)", "misconception": ""},
                        {
                            "id": "down",
                            "text": "(2, 1)",
                            "misconception": "That subtracts 4 from the output. A change inside the parentheses moves the input, not the height.",
                        },
                        {
                            "id": "left",
                            "text": "(-2, 5)",
                            "misconception": "The graph shifts the opposite direction of the sign inside. x - 4 moves right, not left.",
                        },
                        {
                            "id": "up",
                            "text": "(2, 9)",
                            "misconception": "Adding outside the function changes height. Here the 4 is inside.",
                        },
                    ],
                    "answer": "right",
                    "explain": True,
                    "misconception": "Look at whether the 4 changes the input or the output.",
                },
            },
            {
                "kind": "teach_back",
                "objective": "Explain the direction of an inside shift.",
                "tutor_prompt": "Explain why y = f(x - 4) shifts the graph to the right even though the sign looks negative.",
                "rubric": "The same output now happens at a larger input, so the graph moves right.",
                "pass_criteria": "Explains that the input must be 4 larger to match the old output.",
                "rubric_rows": _rows(
                    ("input", "Says the input has to be 4 larger to get the old output.", 60),
                    ("direction", "Says that is a shift to the right.", 40),
                ),
                "hint_ladder": _hints(
                    "What x makes (x - 4) equal the old input?",
                    "To get the output that used to happen at 2, x - 4 must be 2, so x is 6.",
                    "The graph moves right because each output is delayed until a larger input.",
                ),
                "pass_score": 70,
            },
        ],
    },
]

LESSONS = [
    {
        "slug": "fractions",
        "title": "Fractions",
        "preamble": PREAMBLE,
        "topics": TOPICS,
        "activate_if_none": True,
        "age_min": 8,
        "age_max": 12,
        "rewrite_in_place": True,
    },
    {
        "slug": "reading",
        "title": "Reading",
        "preamble": READING_PREAMBLE,
        "topics": READING_TOPICS,
        "activate_if_none": False,
        "age_min": 8,
        "age_max": None,
    },
    {
        "slug": "science",
        "title": "Science",
        "preamble": SCIENCE_PREAMBLE,
        "topics": SCIENCE_TOPICS,
        "activate_if_none": False,
        "age_min": 8,
        "age_max": None,
    },
    {
        "slug": "super-prompts",
        "title": "Super prompts",
        "preamble": SUPER_PREAMBLE,
        "topics": SUPER_TOPICS,
        "activate_if_none": False,
        "age_min": 9,
        "age_max": 11,
    },
    {
        "slug": "function-shifts",
        "title": "Function shifts",
        "preamble": SHIFTS_PREAMBLE,
        "topics": SHIFTS_TOPICS,
        "activate_if_none": False,
        "age_min": 15,
        "age_max": 17,
    },
]


def _copy_block(spec: dict) -> dict:
    return {
        "kind": spec["kind"],
        "tutor_prompt": spec["tutor_prompt"],
        "rubric": spec.get("rubric") or None,
        "pass_criteria": spec.get("pass_criteria") or None,
        "objective": spec.get("objective"),
        "rubric_rows": copy.deepcopy(spec.get("rubric_rows") or []),
        "hint_ladder": copy.deepcopy(
            spec.get("hint_ladder") or {"nudge": "", "analogy": "", "scaffold": ""}
        ),
        "pass_score": spec.get("pass_score", 70),
        "quiz": copy.deepcopy(spec.get("quiz")),
    }


def _write_checkpoint(checkpoint: Checkpoint, spec: dict) -> None:
    fields = _copy_block(spec)
    checkpoint.kind = fields["kind"]
    checkpoint.tutor_prompt = fields["tutor_prompt"]
    checkpoint.rubric = fields["rubric"]
    checkpoint.pass_criteria = fields["pass_criteria"]
    checkpoint.objective = fields["objective"]
    checkpoint.rubric_rows = fields["rubric_rows"]
    checkpoint.hint_ladder = fields["hint_ladder"]
    checkpoint.pass_score = fields["pass_score"]
    checkpoint.quiz = fields["quiz"]


def _new_checkpoint(topic: Topic, spec: dict, position: int) -> Checkpoint:
    fields = _copy_block(spec)
    return Checkpoint(topic_id=topic.id, position=position, **fields)


def _add_topics(db: Session, plan: LessonPlan, topics: list[dict]) -> None:
    for topic_index, topic_spec in enumerate(topics, start=1):
        topic = Topic(
            lesson_plan_id=plan.id,
            title=topic_spec["title"],
            learning_goal=topic_spec["learning_goal"],
            tutor_instructions=topic_spec["tutor_instructions"],
            position=topic_index,
        )
        db.add(topic)
        db.flush()
        for checkpoint_index, checkpoint_spec in enumerate(topic_spec["checkpoints"], start=1):
            db.add(_new_checkpoint(topic, checkpoint_spec, checkpoint_index))


def _needs_block_rewrite(plan: LessonPlan) -> bool:
    kinds = {checkpoint.kind for topic in plan.topics for checkpoint in topic.checkpoints}
    return "discovery" not in kinds and "teach_back" not in kinds


def _fill_ages(plan: LessonPlan, spec: dict) -> None:
    if plan.age_min is None and spec.get("age_min") is not None:
        plan.age_min = spec["age_min"]
        plan.age_max = spec.get("age_max")


HELD_BLOCK = {
    "kind": "teach_back",
    "objective": "Explain a fraction you already know.",
    "tutor_prompt": "Tell me one fraction you know, and what the top number and the bottom number mean.",
    "rubric": "Names a fraction and both parts.",
    "pass_criteria": "The student names a fraction and says what each number means.",
    "rubric_rows": [
        {"id": "fraction", "text": "Names a fraction.", "weight": 40},
        {"id": "parts", "text": "Says what the numerator and the denominator mean.", "weight": 60},
    ],
    "hint_ladder": {
        "nudge": "Pick a fraction you have already used, like 1/4.",
        "analogy": "The bottom number is the equal pieces. The top number is how many of them you mean.",
        "scaffold": "1/4 means 1 piece out of 4 equal pieces. 1 is the numerator and 4 is the denominator.",
    },
    "pass_score": 70,
}


def _sync_checkpoints(db: Session, topic: Topic, specs: list[dict]) -> None:
    existing = sorted(topic.checkpoints, key=lambda item: item.position)
    for index, checkpoint_spec in enumerate(specs):
        if index < len(existing):
            _write_checkpoint(existing[index], checkpoint_spec)
            continue
        position = index + 1
        taken = {item.position for item in existing}
        while position in taken:
            position += 1
        created = _new_checkpoint(topic, checkpoint_spec, position)
        topic.checkpoints.append(created)
        db.add(created)
    for extra in existing[len(specs) :]:
        if checkpoint_in_use(db, extra.id):
            _write_checkpoint(extra, HELD_BLOCK)
            continue
        topic.checkpoints.remove(extra)
        db.delete(extra)
    db.flush()


def _rewrite_plan_in_place(db: Session, plan: LessonPlan, spec: dict) -> None:
    """Replace block text on the same lesson, topic, and checkpoint rows."""
    plan.title = spec["title"]
    plan.preamble = spec["preamble"]
    plan.age_min = spec.get("age_min")
    plan.age_max = spec.get("age_max")
    topics = sorted(plan.topics, key=lambda item: item.position)
    for index, topic_spec in enumerate(spec["topics"]):
        if index < len(topics):
            topic = topics[index]
            topic.title = topic_spec["title"]
            topic.learning_goal = topic_spec["learning_goal"]
            topic.tutor_instructions = topic_spec["tutor_instructions"]
        else:
            topic = Topic(
                lesson_plan_id=plan.id,
                title=topic_spec["title"],
                learning_goal=topic_spec["learning_goal"],
                tutor_instructions=topic_spec["tutor_instructions"],
                position=index + 1,
            )
            plan.topics.append(topic)
            db.add(topic)
            db.flush()
            topics.append(topic)
        _sync_checkpoints(db, topic, topic_spec["checkpoints"])
    for extra in topics[len(spec["topics"]) :]:
        if topic_in_use(db, extra):
            for checkpoint in list(extra.checkpoints):
                _write_checkpoint(checkpoint, HELD_BLOCK)
            continue
        plan.topics.remove(extra)
        db.delete(extra)
    db.flush()


def _insert_plan(db: Session, spec: dict) -> str:
    existing = db.scalar(
        select(LessonPlan)
        .where(LessonPlan.slug == spec["slug"])
        .options(selectinload(LessonPlan.topics).selectinload(Topic.checkpoints))
    )
    if existing is not None:
        if spec.get("rewrite_in_place") and _needs_block_rewrite(existing):
            _rewrite_plan_in_place(db, existing, spec)
            return "rewritten"
        _fill_ages(existing, spec)
        return "kept"
    already_active = db.scalar(select(LessonPlan.id).where(LessonPlan.is_active.is_(True)))
    plan = LessonPlan(
        slug=spec["slug"],
        title=spec["title"],
        preamble=spec["preamble"],
        age_min=spec.get("age_min"),
        age_max=spec.get("age_max"),
        is_active=bool(spec["activate_if_none"]) and already_active is None,
    )
    db.add(plan)
    db.flush()
    _add_topics(db, plan, spec["topics"])
    return "created"


def seed(db: Session) -> dict[str, int]:
    created_students = 0
    for spec in STUDENTS:
        exists = db.scalar(select(Student).where(Student.slug == spec["slug"]))
        if exists is None:
            db.add(Student(slug=spec["slug"], display_name=spec["display_name"], age=spec["age"]))
            created_students += 1
        elif exists.age is None:
            exists.age = spec["age"]
    db.flush()

    outcomes = [_insert_plan(db, spec) for spec in LESSONS]
    db.commit()
    return {
        "students_created": created_students,
        "lesson_plans_created": outcomes.count("created"),
        "lesson_plans_rewritten": outcomes.count("rewritten"),
    }


def main() -> None:
    db = SessionLocal()
    try:
        result = seed(db)
    finally:
        db.close()
    print(
        "students_created={students_created} lesson_plans_created={lesson_plans_created} "
        "lesson_plans_rewritten={lesson_plans_rewritten}".format(**result)
    )


if __name__ == "__main__":
    main()
