"""Exercise a question-shaped answer through the same HTTP writes as the tutor."""

from uuid import UUID, uuid4

from app.database import SessionLocal
from app.models import KcSession
from app.studio import DELETE_PASSWORD
from tests.test_kc import _ready, _spec, _storm, client
from tests.test_tentative_answers import CPI


def test_confirmed_cpi_question_advances_once_and_saves_the_learners_answer():
    code = f"zz-cpi-{uuid4().hex[:8]}"
    created = client.post("/kc/courses", json={
        "code": code, "title": "Measuring inflation", "description": "Calculating changes in the CPI.",
        "audience": "12-14", "kind": "mastery",
    })
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    try:
        course = _ready(created.json(), [_spec(f"{code}-rate", "Inflation rate", blocks=[CPI])])
        opened = client.post("/kc/tutor/sessions", json={
            "student_id": str(_storm().id), "course_id": course_id, "kc_id": course["components"][0]["id"],
        })
        assert opened.status_code == 200, opened.text
        session = opened.json()
        assert session["active_substep"] == "recall"
        path = f"/kc/tutor/sessions/{session['id']}"
        spoken = client.post(f"{path}/speech", json={"content": CPI["data"]["recall_prompt"]})
        assert spoken.status_code == 200, spoken.text

        answer = "Is it the new CPI minus the old CPI, divided by the old CPI, then times 100?"
        turn_id = str(uuid4())
        posted = client.post(f"{path}/turn", json={
            "turn_id": turn_id, "revision": spoken.json()["revision"], "answer": answer,
        })
        assert posted.status_code == 200, posted.text
        # The controlled grader recognizes this formula but obeys an explicit instruction to skip scoring it.
        reply = "Yes. You measured the change against the starting index. Why use a basket of goods?"
        grade = {"decision": "advance", "substep_passed": True, "reply": reply}
        if "This typed line is unscored help" in posted.json()["system_prompt"]:
            grade = {"decision": "stay", "substep_passed": False, "reply": CPI["data"]["recall_prompt"]}
        decision = client.post(f"{path}/decision", json={
            "turn_id": turn_id, **grade,
        })
        assert decision.status_code == 200, decision.text
        assert decision.json()["active_substep"] == "elaborate_why"
        assert decision.json()["reply"] == reply

        reloaded = client.get(path)
        assert reloaded.status_code == 200, reloaded.text
        assert reloaded.json()["active_substep"] == "elaborate_why"
        messages = [(message["role"], message["content"]) for message in reloaded.json()["messages"]]
        assert messages[-2:] == [("user", answer), ("assistant", reply)]
        with SessionLocal() as db:
            saved = db.get(KcSession, UUID(session["id"]))
            requirements = {row["key"]: row for row in saved.active_block_state["requirements"]}
            assert (requirements["recall"]["observation"], requirements["recall"]["attempts"]) == ("independent", 1)
            assert (requirements["elaborate_why"]["observation"], requirements["elaborate_why"]["attempts"]) == ("open", 0)
    finally:
        removed = client.post(f"/kc/courses/{course_id}/delete", json={"password": DELETE_PASSWORD})
        assert removed.status_code == 200, removed.text
