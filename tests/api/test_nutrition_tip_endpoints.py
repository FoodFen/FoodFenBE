"""Public GET /nutrition-tips (active only, no auth) and admin CRUD under /admin/nutrition-tips."""

import pytest
import pytest_asyncio

_ADMIN = "/admin/nutrition-tips"


@pytest_asyncio.fixture
async def admin(make_user):
    headers, _ = await make_user("admin@example.com", admin=True)
    return headers


async def _create(client, admin, vi="Ăn rau", en="Eat greens", **extra):
    resp = await client.post(_ADMIN, json={"textVi": vi, "textEn": en, **extra}, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_public_list_is_empty_without_tips_and_needs_no_auth(client):
    resp = await client.get("/nutrition-tips")

    assert (resp.status_code, resp.json()) == (200, {"items": []})


async def test_public_list_hides_inactive_and_only_exposes_texts(client, admin):
    shown = await _create(client, admin, "Hiện", "Shown")
    await _create(client, admin, "Ẩn", "Hidden", isActive=False)

    resp = await client.get("/nutrition-tips")

    assert resp.json() == {"items": [{"id": shown["id"], "textVi": "Hiện", "textEn": "Shown"}]}


async def test_admin_crud_round_trip(client, admin):
    created = await _create(client, admin)
    assert created["isActive"] is True
    assert set(created) == {"id", "textVi", "textEn", "isActive", "createdAt", "updatedAt"}

    patched = await client.patch(f"{_ADMIN}/{created['id']}", json={"textEn": "Eat more greens", "isActive": False}, headers=admin)
    assert patched.status_code == 200
    assert (patched.json()["textEn"], patched.json()["textVi"], patched.json()["isActive"]) == ("Eat more greens", "Ăn rau", False)

    listed = (await client.get(_ADMIN, headers=admin)).json()["items"]
    assert [t["id"] for t in listed] == [created["id"]]  # inactive ones are listed for the admin

    assert (await client.delete(f"{_ADMIN}/{created['id']}", headers=admin)).status_code == 204
    assert (await client.get(_ADMIN, headers=admin)).json() == {"items": []}


async def test_admin_list_is_newest_first(client, admin):
    first = await _create(client, admin, "một", "one")
    second = await _create(client, admin, "hai", "two")

    ids = [t["id"] for t in (await client.get(_ADMIN, headers=admin)).json()["items"]]

    assert ids == [second["id"], first["id"]]


async def test_empty_text_is_a_coded_422_with_camel_field(client, admin):
    resp = await client.post(_ADMIN, json={"textVi": "  ", "textEn": "ok"}, headers=admin)

    assert resp.status_code == 422
    assert (resp.json()["code"], resp.json()["field"]) == ("text_required", "textVi")


async def test_too_long_text_on_patch_is_a_coded_422(client, admin):
    tip = await _create(client, admin)

    resp = await client.patch(f"{_ADMIN}/{tip['id']}", json={"textEn": "x" * 301}, headers=admin)

    assert resp.status_code == 422
    assert (resp.json()["code"], resp.json()["field"]) == ("text_too_long", "textEn")


async def test_unknown_id_is_404_for_patch_and_delete(client, admin):
    missing = "00000000-0000-4000-8000-000000000000"

    assert (await client.patch(f"{_ADMIN}/{missing}", json={"isActive": False}, headers=admin)).status_code == 404
    assert (await client.delete(f"{_ADMIN}/{missing}", headers=admin)).status_code == 404


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", _ADMIN, None),
        ("post", _ADMIN, {"textVi": "a", "textEn": "b"}),
        ("patch", f"{_ADMIN}/00000000-0000-4000-8000-000000000000", {"isActive": False}),
        ("delete", f"{_ADMIN}/00000000-0000-4000-8000-000000000000", None),
    ],
)
async def test_non_admin_403_anonymous_401(client, make_user, method, path, body):
    user, _ = await make_user("user@example.com")
    kwargs = {"json": body} if body else {}

    assert (await getattr(client, method)(path, headers=user, **kwargs)).status_code == 403
    assert (await getattr(client, method)(path, **kwargs)).status_code == 401
