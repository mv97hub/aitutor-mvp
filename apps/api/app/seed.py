"""Idempotent seed: four students and one fractions lesson.

Running this twice does not duplicate rows. Existing rows are left as edited.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Checkpoint, LessonPlan, Student, Topic

STUDENTS = [
    {"slug": "iron-man", "display_name": "Iron Man"},
    {"slug": "storm", "display_name": "Storm"},
    {"slug": "spider-man", "display_name": "Spider-Man"},
    {"slug": "wolverine", "display_name": "Wolverine"},
]

PREAMBLE = (
    "You are a warm, patient math tutor for a child who is about 8 to 10 years old. "
    "Use everyday objects, short sentences, and encouragement. One step at a time."
)

TOPICS = [
    {
        "title": "Parts of a whole",
        "learning_goal": (
            "A fraction names equal parts of a whole. The denominator is how many equal "
            "parts the whole was split into. The numerator is how many of those parts we mean."
        ),
        "tutor_instructions": (
            "Use one pizza or one chocolate bar. Do not introduce different denominators. "
            "Explain, then ask one short question, then wait."
        ),
        "checkpoints": [
            {
                "kind": "teach",
                "tutor_prompt": (
                    "Explain that a fraction is part of a whole, using a pizza cut into equal "
                    "slices. Teach the words numerator and denominator. Then ask this check "
                    "question and wait: a pizza is cut into 4 equal slices and the student eats "
                    "1 slice. What fraction did they eat? When they say 1/4 (or one fourth) and "
                    "can say the denominator is 4, the teach step is complete: call "
                    "advance_checkpoint. If they mix it up, explain once more with the same pizza "
                    "and ask again. Do not move on until they show they understand."
                ),
                "rubric": "",
                "pass_criteria": (
                    "The student says 1/4 or one fourth, and knows the bottom number is how many "
                    "equal slices the pizza was cut into."
                ),
            },
            {
                "kind": "practice",
                "tutor_prompt": (
                    "Stay on this guided problem: a chocolate bar has 3 equal pieces and the "
                    "student has 2 of them. What fraction do they have? Hints are allowed. First "
                    "hint: the denominator is the number of equal pieces. Second hint: the "
                    "numerator is how many they have. When they answer 2/3, call "
                    "record_checkpoint_result with a passing score and short feedback, then call "
                    "advance_checkpoint. If they miss, give one hint and let them try again. Do "
                    "not record a pass until 2/3 is clear."
                ),
                "rubric": (
                    "The correct fraction is 2/3. The denominator 3 is the equal pieces. The "
                    "numerator 2 is the pieces they have."
                ),
                "pass_criteria": "The student says 2/3 or two thirds.",
            },
            {
                "kind": "quiz",
                "tutor_prompt": (
                    "This is a scored quiz. Ask only this question and do not hint at the answer "
                    "first: a granola bar is split into 8 equal pieces and Maya eats 3. What "
                    "fraction did she eat, and which number is the numerator? After they answer, "
                    "grade with the rubric. Call record_checkpoint_result with a score from 0 to "
                    "100, feedback in one or two sentences, and passed true or false. If they "
                    "pass, congratulate them and call advance_checkpoint. If they do not pass, "
                    "they may try once more, then grade again. Do not say 3/8 until after their "
                    "first try. Never skip this quiz."
                ),
                "rubric": (
                    "Full credit, passed true, score 100: the fraction is 3/8 and the numerator "
                    "is 3. Partial, passed false, score 50: the fraction is 3/8 but the numerator "
                    "is missing or wrong, or they swap the numbers to 8/3. No credit, passed "
                    "false, score 0: a different fraction. Pass only when the fraction is 3/8 and "
                    "the numerator is 3."
                ),
                "pass_criteria": "The answer is 3/8 and the numerator is 3.",
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
                "kind": "teach",
                "tutor_prompt": (
                    "Explain that if the slices are the same size, more slices is more pizza. "
                    "Example: 1/4 is less than 3/4. Then ask: which is more, 1/4 or 3/4, and why? "
                    "When they choose 3/4 because 3 is more than 1 and the slices match, call "
                    "advance_checkpoint."
                ),
                "rubric": "",
                "pass_criteria": (
                    "The student chooses 3/4 and gives a reason about more equal parts."
                ),
            },
            {
                "kind": "practice",
                "tutor_prompt": (
                    "Ask: which is bigger, 2/5 or 4/5? Hints are allowed. Pass when they say 4/5 "
                    "because both are fifths and 4 is more than 2. Then call "
                    "record_checkpoint_result with passed true and advance_checkpoint."
                ),
                "rubric": "The correct choice is 4/5, with a reason that the parts are the same size.",
                "pass_criteria": "The student chooses 4/5 and says why.",
            },
            {
                "kind": "quiz",
                "tutor_prompt": (
                    "Scored quiz. Ask: which is bigger, 2/6 or 5/6, and how do you know? Do not "
                    "say the answer first. Grade with the rubric, call record_checkpoint_result, "
                    "and call advance_checkpoint only if they passed."
                ),
                "rubric": (
                    "Pass, score 100, only if they choose 5/6 and explain that the denominators "
                    "match so the larger numerator is bigger. If they choose 5/6 with no reason, "
                    "score 60 and passed false. If they choose 2/6, score 0 and passed false."
                ),
                "pass_criteria": (
                    "5/6, because the sixths are the same size and 5 is greater than 2."
                ),
            },
        ],
    },
]


def seed(db: Session) -> dict[str, int]:
    created_students = 0
    for spec in STUDENTS:
        exists = db.scalar(select(Student).where(Student.slug == spec["slug"]))
        if exists is None:
            db.add(Student(**spec))
            created_students += 1
    db.flush()

    created_plans = 0
    plan = db.scalar(select(LessonPlan).where(LessonPlan.slug == "fractions"))
    if plan is None:
        already_active = db.scalar(
            select(LessonPlan.id).where(LessonPlan.is_active.is_(True))
        )
        plan = LessonPlan(
            slug="fractions",
            title="Fractions",
            preamble=PREAMBLE,
            is_active=already_active is None,
        )
        db.add(plan)
        db.flush()
        for topic_index, topic_spec in enumerate(TOPICS, start=1):
            topic = Topic(
                lesson_plan_id=plan.id,
                title=topic_spec["title"],
                learning_goal=topic_spec["learning_goal"],
                tutor_instructions=topic_spec["tutor_instructions"],
                position=topic_index,
            )
            db.add(topic)
            db.flush()
            for checkpoint_index, checkpoint_spec in enumerate(
                topic_spec["checkpoints"], start=1
            ):
                db.add(
                    Checkpoint(
                        topic_id=topic.id,
                        kind=checkpoint_spec["kind"],
                        tutor_prompt=checkpoint_spec["tutor_prompt"],
                        rubric=checkpoint_spec["rubric"] or None,
                        pass_criteria=checkpoint_spec["pass_criteria"] or None,
                        position=checkpoint_index,
                    )
                )
        created_plans = 1
    db.commit()
    return {"students_created": created_students, "lesson_plans_created": created_plans}


def main() -> None:
    db = SessionLocal()
    try:
        result = seed(db)
    finally:
        db.close()
    print(
        "students_created={students_created} lesson_plans_created={lesson_plans_created}".format(
            **result
        )
    )


if __name__ == "__main__":
    main()
