"""Restaurant / Dish invariants and moderation transitions. No I/O."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.entities.user import User
from src.domain.enums import ModerationStatus, ReviewDecision, UserRole
from src.domain.exceptions import InvalidRestaurantAttributeException

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


def _restaurant(**overrides) -> Restaurant:
    fields = dict(
        user_id=1, name=" Quán Ngon ", address="1 Lê Lợi", phone="0901234567",
        opening_hours="7:00-21:00", latitude=10.7769, longitude=106.7009,
    )
    return Restaurant.create(**{**fields, **overrides})


def _dish(**overrides) -> Dish:
    fields = dict(
        restaurant_id=uuid4(), name="Phở bò", price=Decimal("55000"), serving_g=500,
        kcal=450, protein_g=30.0, carbs_g=55.0, fat_g=12.0,
    )
    return Dish.create(**{**fields, **overrides})


def test_new_restaurant_is_pending_and_stripped():
    r = _restaurant(description="  ")
    assert r.status == ModerationStatus.PENDING
    assert r.name == "Quán Ngon"
    assert r.description is None
    assert r.rejection_reason is None


@pytest.mark.parametrize("field,value", [
    ("latitude", 90.1), ("latitude", -90.1), ("longitude", 180.1), ("longitude", -180.1),
    ("name", "  "), ("address", ""), ("phone", " "), ("opening_hours", ""),
])
def test_restaurant_rejects_bad_fields(field, value):
    with pytest.raises(InvalidRestaurantAttributeException):
        _restaurant(**{field: value})


@pytest.mark.parametrize("field,value", [
    ("price", Decimal("-1")), ("serving_g", 0), ("kcal", -1), ("protein_g", -0.1),
    ("carbs_g", -1.0), ("fat_g", -1.0), ("fiber_g", -1.0), ("name", " "),
])
def test_dish_rejects_bad_fields(field, value):
    with pytest.raises(InvalidRestaurantAttributeException):
        _dish(**{field: value})


def test_reject_requires_reason_and_leaves_entity_unchanged():
    r = _restaurant()
    with pytest.raises(InvalidRestaurantAttributeException):
        r.review(ReviewDecision.REJECTED, "  ", NOW)
    assert r.status == ModerationStatus.PENDING
    assert r.reviewed_at is None


def test_review_sets_and_clears_reason_and_is_idempotent():
    d = _dish()
    d.review(ReviewDecision.REJECTED, " kcal too low ", NOW)
    assert (d.status, d.rejection_reason, d.reviewed_at) == (ModerationStatus.REJECTED, "kcal too low", NOW)
    d.review(ReviewDecision.APPROVED, "ignored", NOW)
    d.review(ReviewDecision.APPROVED, None, NOW)
    assert (d.status, d.rejection_reason) == (ModerationStatus.APPROVED, None)


def test_editing_any_dish_returns_it_to_pending():
    d = _dish()
    d.review(ReviewDecision.APPROVED, None, NOW)
    d.mark_edited(NOW)
    assert d.status == ModerationStatus.PENDING
    assert d.updated_at == NOW


def test_editing_approved_restaurant_keeps_it_approved():
    r = _restaurant()
    r.review(ReviewDecision.APPROVED, None, NOW)
    r.mark_edited(NOW)
    assert r.status == ModerationStatus.APPROVED


def test_editing_rejected_restaurant_resubmits_it():
    r = _restaurant()
    r.review(ReviewDecision.REJECTED, "no address proof", NOW)
    r.mark_edited(NOW)
    assert (r.status, r.rejection_reason) == (ModerationStatus.PENDING, None)


def test_rejected_without_reason_cannot_be_constructed():
    with pytest.raises(InvalidRestaurantAttributeException):
        Restaurant(
            id=uuid4(), user_id=1, name="x", address="x", phone="x", opening_hours="x",
            latitude=0, longitude=0, status=ModerationStatus.REJECTED,
        )


def test_user_defaults_to_user_role():
    user = User.create(email="a@b.co")
    assert user.role == UserRole.USER and not user.is_admin
    assert User(email="a@b.co", role=UserRole.ADMIN).is_admin
