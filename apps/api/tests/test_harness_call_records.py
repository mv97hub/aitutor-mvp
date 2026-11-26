"""Download real persisted prompt, token and turn records without calling a provider."""

import uuid

from app.database import SessionLocal
from app.harness import download_chat, download_run, get_chat
from app.models import (
    HarnessChat, HarnessRun, HarnessTurn, KcGoal, KcMessage, KcModelPrompt, KcNode, KcSession,
    Student, TutorTokenUsage,
)


def test_download_links_committed_messages_and_keeps_unverified_records():
    # Roll back the entire synthetic conversation when the session closes.
    with SessionLocal() as db:
        code = f"export-{uuid.uuid4().hex}"
        student = Student(slug=code, display_name="Test child", is_test=True)
        goal = KcGoal(code=code, title="Test course")
        node = KcNode(code=code, title="Test component")
        run = HarnessRun()
        db.add_all([student, goal, node, run])
        db.flush()
        session = KcSession(student_id=student.id, goal_id=goal.id, kc_id=node.id)
        db.add(session)
        db.flush()
        chat = HarnessChat(run_id=run.id, session_id=session.id, tutor_model="configured")
        db.add(chat)
        db.flush()
        ids = [uuid.uuid4() for _ in range(7)]
        opening, first, transition, second, duplicate, unlogged, repeated = ids
        for seq, message_id in enumerate(ids, 1):
            db.add(KcMessage(id=message_id, session_id=session.id, seq=seq, role="assistant", content="Try again."))
        db.flush()
        prompts = [
            (opening, "OPEN-A"), (first, "ANSWER-A"), (transition, "OPEN-B"),
            (second, "ANSWER-B"), (None, "LEGACY"), (duplicate, "DUP-A"), (duplicate, "DUP-B"),
            (repeated, "TWO-TURNS"),
        ]
        for seq, (message, prompt) in enumerate(prompts, 1):
            db.add(KcModelPrompt(session_id=chat.session_id, seq=seq, message_id=message,
                                 system_prompt=prompt, model="gpt-4.1", decision={"decision": "stay", "loop_decision": "advance"},
                                 messages=[{"role": "user", "content": "yes"}]))
        # Deliberately log out of order. The second answer lacks usage.
        for sequence, (message, kind, incoming) in enumerate([
            (transition, "speak", 302), (None, "answer", 901), (duplicate, "answer", 777),
            (first, "answer", 201), (opening, "speak", 101),
        ], 1):
            db.add(TutorTokenUsage(id=uuid.UUID(int=sequence), session_id=chat.session_id,
                                   student_id=student.id, kind=kind, model="gpt-4.1",
                                   message_id=message, input_tokens=incoming, output_tokens=1))
        for seq, (before, after) in enumerate([
            (opening, first), (transition, second), (second, duplicate), (duplicate, unlogged), (None, None),
        ], 1):
            db.add(HarnessTurn(chat_id=chat.id, seq=seq, child_text="yes",
                               session_before={"tutor_message_id": str(before) if before else None,
                                               "block_id": "first" if seq == 1 else "next",
                                               "block_type": "mcq" if seq == 1 else "socratic"},
                               session_after={"tutor_message_id": str(after) if after else None,
                                              "tutor_reply": "Try again.", "block_id": "next", "block_type": "socratic"}))
        db.add(HarnessTurn(chat_id=chat.id, seq=6, child_text="yes",
                           session_before={"tutor_message_id": str(second)},
                           session_after={"tutor_message_id": str(second), "prompt": "STALE",
                                          "tutor_reply": "", "error": "failed", "loop_decision": "advance"}))
        for seq in (7, 8):
            db.add(HarnessTurn(chat_id=chat.id, seq=seq, child_text="yes", session_before={},
                               session_after={"tutor_message_id": str(repeated), "tutor_reply": "Try again."}))
        db.flush()
        transcript = download_chat(db, chat.id)
        assert transcript == download_run(db, run.id)
        detail = get_chat(db, chat.id)
    sections = transcript.split("### ")
    headers = [section.splitlines()[0] for section in sections[1:]]
    assert headers[:10] == ["Opening tutor call before turn 1", "Turn 1", "Opening tutor call before turn 2",
                           "Turn 2", "Turn 3", "Turn 4", "Turn 5", "Turn 6", "Turn 7", "Turn 8"]
    for section, prompt, tokens in zip(sections[1:5], ["OPEN-A", "ANSWER-A", "OPEN-B", "ANSWER-B"],
                                        ["101 in, 1 out", "201 in, 1 out", "302 in, 1 out", "not stored"], strict=True):
        assert f"System prompt: {prompt}\n" in section
        assert f"Tutor tokens: {tokens}\n" in section
    assert "Start of block: Multiple Choice Question" in sections[2]
    assert "End of block: Multiple Choice Question" in sections[2]
    assert "Block after: Socratic Discussion (id:next)" in sections[2]
    assert "Start of block: Socratic Discussion" in sections[4]
    for section in sections[5:11]:
        assert "Tutor call association: unknown" in section
        assert "System prompt: not stored" in section
    assert "Loop decision: not stored" in sections[8]
    assert "Cost: 0.00041\n" in sections[2]
    assert "Cost: blank\n" in sections[4]
    unknown = sections[11]
    assert unknown.startswith("Tutor records without a verified turn")
    assert all(unknown.count(marker) == 1 for marker in ["LEGACY", "DUP-A", "DUP-B", "901 in", "777 in", "TWO-TURNS"])
    assert all(transcript.count(marker) == 1 for marker in ["OPEN-A", "OPEN-B", "ANSWER-A", "ANSWER-B", "777 in"])
    assert detail["turns"][0]["tutor_prompt"] == "ANSWER-A"
    assert detail["turns"][0]["loop_decision"] == "advance"
    assert all(turn["loop_decision"] == "" and turn["tutor_prompt"] == "" for turn in detail["turns"][2:])
