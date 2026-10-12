"""AdPackage invariants. Pure domain."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.domain.entities.ad_package import AdPackage
from src.domain.exceptions import InvalidAdPackageException


def test_create_is_active_with_decimal_price():
    p = AdPackage.create(days=7, price_vnd=99000)
    assert (p.days, p.price_vnd, p.active) == (7, Decimal("99000"), True)


@pytest.mark.parametrize("days,price", [(0, 1), (-1, 1), (7, 0), (7, -5)])
def test_create_rejects_non_positive(days, price):
    with pytest.raises(InvalidAdPackageException):
        AdPackage.create(days=days, price_vnd=price)


def test_update_changes_only_what_is_given():
    p = AdPackage.create(days=7, price_vnd=99000)
    p.update(price_vnd=120000)
    p.update(active=False)
    assert (p.days, p.price_vnd, p.active) == (7, Decimal("120000"), False)


def test_update_rejects_bad_values_and_leaves_the_package_unchanged():
    p = AdPackage.create(days=7, price_vnd=99000)
    with pytest.raises(InvalidAdPackageException):
        p.update(days=0)
    assert p.days == 7
