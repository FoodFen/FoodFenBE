"""Admin quiz content: topics and questions CRUD under /admin, plus how it shows in the public quiz."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio

TOPICS = "/admin/quiz-topics"
QUESTIONS = "/admin/quizzes"


@pytest_asyncio.fixture
async def admin(make_user):
    headers, _ = await make_user("admin@example.com", admin=True)
    return headers


@pytest_asyncio.fixture
async def player(make_user):
    headers, _ = await make_user("player@example.com")
    return headers


async def _topic(client, admin, slug="macros", label="Macros", **extra) -> dict:
    resp = await client.post(TOPICS, json={"slug": slug, "label": label, **extra}, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _body(topic_id: str, text="Which?", correct="a", **extra) -> dict:
    return {
        "topicId": topic_id,
        "question": text,
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "correctOptionId": correct,
        "explanation": "because",
        **extra,
    }


async def _question(client, admin, topic_id: str, text="Which?", **extra) -> dict:
    resp = await client.post(QUESTIONS, json=_body(topic_id, text, **extra), headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _full_topic(client, admin, slug="macros", n=5) -> tuple[dict, list[dict]]:
    topic = await _topic(client, admin, slug, slug.title())
    return topic, [await _question(client, admin, topic["id"], f"{slug} {i}") for i in range(n)]


async def _daily(client, player) -> dict:
    day = datetime.now(UTC).date().isoformat()
    resp = await client.get("/quizzes/daily", params={"date": day}, headers=player)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", TOPICS),
        ("post", TOPICS),
        ("patch", f"{TOPICS}/{uuid4()}"),
        ("post", QUESTIONS),
        ("patch", f"{QUESTIONS}/{uuid4()}"),
        ("delete", f"{QUESTIONS}/{uuid4()}"),
    ],
)
async def test_non_admin_is_forbidden(client, player, method, path):
    resp = await client.request(method, path, json={}, headers=player)
    assert resp.status_code == 403


async def test_topic_create_list_rename_deactivate(client, admin):
    created = await _topic(client, admin, "vitamins-minerals", "Vitamin")
    assert created == {
        "id": created["id"], "slug": "vitamins-minerals", "label": "Vitamin", "active": True,
        "activeQuestionCount": 0,
    }
    await _question(client, admin, created["id"])
    await _question(client, admin, created["id"], active=False)

    patched = await client.patch(
        f"{TOPICS}/{created['id']}", json={"label": "Vitamin & khoáng", "active": False}, headers=admin
    )
    assert patched.status_code == 200
    assert patched.json() == {**created, "label": "Vitamin & khoáng", "active": False, "activeQuestionCount": 1}

    items = (await client.get(TOPICS, headers=admin)).json()["items"]
    assert items == [patched.json()]  # inactive topics are listed too


async def test_topic_list_is_sorted_by_folded_label(client, admin):
    await _topic(client, admin, "b", "Đường")
    await _topic(client, admin, "a", "Zinc")
    await _topic(client, admin, "c", "Alpha")
    items = (await client.get(TOPICS, headers=admin)).json()["items"]
    assert [t["label"] for t in items] == ["Alpha", "Đường", "Zinc"]


async def test_topic_slug_is_unique_even_when_inactive_and_immutable(client, admin):
    topic = await _topic(client, admin, "macros", active=False)
    dup = await client.post(TOPICS, json={"slug": "macros", "label": "Other"}, headers=admin)
    assert dup.status_code == 409 and dup.json()["error"] == "quiz_topic_slug_taken"
    patched = await client.patch(f"{TOPICS}/{topic['id']}", json={"slug": "other"}, headers=admin)
    assert patched.status_code == 200 and patched.json()["slug"] == "macros"


@pytest.mark.parametrize(
    ("body", "code", "field"),
    [
        ({"slug": "Bad Slug", "label": "L"}, "invalid_slug", "slug"),
        ({"slug": "ok", "label": "  "}, "label_required", "label"),
        ({"slug": "ok", "label": "x" * 65}, "label_too_long", "label"),
    ],
)
async def test_topic_validation_is_a_coded_422(client, admin, body, code, field):
    resp = await client.post(TOPICS, json=body, headers=admin)
    assert resp.status_code == 422
    assert (resp.json()["code"], resp.json()["field"]) == (code, field)


async def test_unknown_topic_patch_is_404(client, admin):
    assert (await client.patch(f"{TOPICS}/{uuid4()}", json={"label": "x"}, headers=admin)).status_code == 404


async def test_question_create_appears_in_the_admin_list_with_every_field(client, admin):
    topic = await _topic(client, admin)
    created = await _question(client, admin, topic["id"], "Which?", correctOptionId="b", explanation="why")
    assert created == {
        "id": created["id"], "question": "Which?", "topic": "Macros", "topicId": topic["id"],
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "correctOptionId": "b", "explanation": "why", "active": True,
    }
    assert (await client.get(QUESTIONS, headers=admin)).json() == [created]


async def test_question_explanation_and_active_default(client, admin):
    topic = await _topic(client, admin)
    body = _body(topic["id"])
    del body["explanation"]
    created = (await client.post(QUESTIONS, json=body, headers=admin)).json()
    assert (created["explanation"], created["active"]) == ("", True)


async def test_question_validation_is_a_coded_422(client, admin):
    topic = await _topic(client, admin)
    wrong_correct = await client.post(QUESTIONS, json=_body(topic["id"], correct="z"), headers=admin)
    assert wrong_correct.status_code == 422
    assert (wrong_correct.json()["code"], wrong_correct.json()["field"]) == (
        "correct_option_invalid", "correctOptionId",
    )
    one_option = {**_body(topic["id"]), "options": [{"id": "a", "text": "A"}]}
    resp = await client.post(QUESTIONS, json=one_option, headers=admin)
    assert (resp.status_code, resp.json()["code"]) == (422, "option_count")
    unknown = await client.post(QUESTIONS, json=_body(str(uuid4())), headers=admin)
    assert (unknown.status_code, unknown.json()["code"], unknown.json()["field"]) == (
        422, "unknown_topic", "topicId",
    )


async def test_question_patch_edits_fields_and_moves_topic(client, admin):
    one, two = await _topic(client, admin, "one", "One"), await _topic(client, admin, "two", "Two")
    q = await _question(client, admin, one["id"])
    resp = await client.patch(
        f"{QUESTIONS}/{q['id']}",
        json={
            "topicId": two["id"], "question": "New?", "active": False,
            "options": [{"id": "a", "text": "A2"}, {"id": "b", "text": "B2"}, {"id": "c", "text": "C2"}],
            "correctOptionId": "c",
        },
        headers=admin,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["topic"], body["topicId"], body["question"], body["active"]) == ("Two", two["id"], "New?", False)
    assert (body["correctOptionId"], body["explanation"], len(body["options"])) == ("c", "because", 3)
    assert (await client.patch(f"{QUESTIONS}/{uuid4()}", json={"active": False}, headers=admin)).status_code == 404
    bad = await client.patch(f"{QUESTIONS}/{q['id']}", json={"correctOptionId": "z"}, headers=admin)
    assert (bad.status_code, bad.json()["code"]) == (422, "correct_option_invalid")


async def test_a_question_in_an_issued_quiz_freezes_its_answer_but_not_its_wording(client, admin, player):
    _, questions = await _full_topic(client, admin)
    await _daily(client, player)
    q = questions[0]["id"]

    assert (await client.patch(f"{QUESTIONS}/{q}", json={"question": "Reworded?"}, headers=admin)).status_code == 200
    reworded = await client.patch(
        f"{QUESTIONS}/{q}",
        json={"options": [{"id": "a", "text": "A!"}, {"id": "b", "text": "B!"}], "explanation": "new", "active": False},
        headers=admin,
    )
    assert reworded.status_code == 200 and reworded.json()["options"][0]["text"] == "A!"

    flipped = await client.patch(f"{QUESTIONS}/{q}", json={"correctOptionId": "b"}, headers=admin)
    assert (flipped.status_code, flipped.json()["error"]) == (409, "quiz_question_in_use")
    other_ids = [{"id": "a", "text": "A"}, {"id": "x", "text": "X"}]
    assert (await client.patch(f"{QUESTIONS}/{q}", json={"options": other_ids}, headers=admin)).status_code == 409
    more = [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}]
    assert (await client.patch(f"{QUESTIONS}/{q}", json={"options": more}, headers=admin)).status_code == 409

    deleted = await client.delete(f"{QUESTIONS}/{q}", headers=admin)
    assert (deleted.status_code, deleted.json()["error"]) == (409, "quiz_question_in_use")


async def test_an_unused_question_can_be_deleted_once(client, admin):
    topic = await _topic(client, admin)
    q = await _question(client, admin, topic["id"])
    assert (await client.patch(f"{QUESTIONS}/{q['id']}", json={"correctOptionId": "b"}, headers=admin)).status_code == 200
    assert (await client.delete(f"{QUESTIONS}/{q['id']}", headers=admin)).status_code == 204
    assert (await client.delete(f"{QUESTIONS}/{q['id']}", headers=admin)).status_code == 404
    assert (await client.get(QUESTIONS, headers=admin)).json() == []


async def test_public_topics_hide_inactive_and_thin_topics(client, admin):
    await _full_topic(client, admin, "full", 5)
    await _full_topic(client, admin, "thin", 4)
    inactive, _ = await _full_topic(client, admin, "off", 5)
    await client.patch(f"{TOPICS}/{inactive['id']}", json={"active": False}, headers=admin)
    _, padded = await _full_topic(client, admin, "padded", 5)
    await client.patch(f"{QUESTIONS}/{padded[0]['id']}", json={"active": False}, headers=admin)  # 4 active left

    resp = await client.get("/quizzes/topics")

    assert resp.json() == {"topics": [{"id": "full", "label": "Full"}]}


async def test_daily_quiz_never_draws_from_an_inactive_topic(client, admin, player):
    _, live = await _full_topic(client, admin, "live", 5)
    off, dead = await _full_topic(client, admin, "dead", 5)
    await client.patch(f"{TOPICS}/{off['id']}", json={"active": False}, headers=admin)

    quiz = await _daily(client, player)

    assert {q["id"] for q in quiz["questions"]} == {q["id"] for q in live}
    assert not {q["id"] for q in quiz["questions"]} & {q["id"] for q in dead}
