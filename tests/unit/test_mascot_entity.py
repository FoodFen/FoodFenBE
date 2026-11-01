"""Mascot invariants. Pure domain."""

from __future__ import annotations

import pytest

from src.domain.entities.mascot import Mascot
from src.domain.enums import MascotState
from src.domain.exceptions import (
    InvalidMascotException,
    MascotDefaultLockedException,
    MascotMissingIdleImageException,
)

IDLE = {MascotState.IDLE: "https://img/idle.png"}


def test_create_defaults_to_inactive_with_trimmed_name():
    m = Mascot.create("mochi", "  Mochi ", 300)
    assert (m.id, m.name, m.coin_cost, m.active, m.images) == ("mochi", "Mochi", 300, False, {})


@pytest.mark.parametrize("slug", ["", "Mochi", "has space", "a" * 33, "dấu", "a/b"])
def test_create_rejects_a_bad_slug(slug):
    with pytest.raises(InvalidMascotException):
        Mascot.create(slug, "Name", 0)


@pytest.mark.parametrize("name", ["", "   ", "x" * 41])
def test_create_rejects_a_bad_name(name):
    with pytest.raises(InvalidMascotException):
        Mascot.create("mochi", name, 0)


@pytest.mark.parametrize("cost", [-1, 1_000_001])
def test_create_rejects_a_cost_out_of_range(cost):
    with pytest.raises(InvalidMascotException):
        Mascot.create("mochi", "Mochi", cost)


def test_active_needs_an_idle_image():
    with pytest.raises(MascotMissingIdleImageException):
        Mascot.create("mochi", "Mochi", 0, active=True)
    with pytest.raises(MascotMissingIdleImageException):
        Mascot.create("mochi", "Mochi", 0, active=True, images={MascotState.HAPPY: "https://img/h.png"})
    assert Mascot.create("mochi", "Mochi", 0, active=True, images=IDLE).active


@pytest.mark.parametrize("slug", ["sprout", "berry", "chili"])
def test_hand_drawn_mascots_may_be_active_without_server_art(slug):
    assert Mascot.create(slug, "X", 100, active=True).active


def test_update_changes_only_what_is_given():
    m = Mascot.create("mochi", "Mochi", 300, images=IDLE)
    m.update(coin_cost=500)
    m.update(active=True)
    m.update(name=" Moo ")
    assert (m.name, m.coin_cost, m.active, m.images) == ("Moo", 500, True, IDLE)


def test_update_merges_images_per_state():
    m = Mascot.create("mochi", "Mochi", 0, images={**IDLE, MascotState.HAPPY: "https://img/h.png"})
    m.update(images={MascotState.HAPPY: None, MascotState.EATING: "https://img/e.png"})
    assert m.images == {MascotState.IDLE: "https://img/idle.png", MascotState.EATING: "https://img/e.png"}
    m.update(images={MascotState.EATING: "https://img/e2.png"})  # idle untouched
    assert m.images[MascotState.IDLE] == "https://img/idle.png"
    m.update(images={MascotState.CONFUSED: None})  # removing an absent state is a no-op
    assert MascotState.CONFUSED not in m.images


def test_update_cannot_remove_idle_from_an_active_mascot_and_changes_nothing():
    m = Mascot.create("mochi", "Mochi", 0, active=True, images=IDLE)
    with pytest.raises(MascotMissingIdleImageException):
        m.update(name="New", images={MascotState.IDLE: None})
    assert (m.name, m.images) == ("Mochi", IDLE)


def test_update_cannot_activate_without_idle_but_can_in_the_same_call_as_adding_it():
    m = Mascot.create("mochi", "Mochi", 0)
    with pytest.raises(MascotMissingIdleImageException):
        m.update(active=True)
    m.update(active=True, images=IDLE)
    assert m.active


def test_body_color_is_optional_and_accepts_rrggbb_as_given():
    assert Mascot.create("mochi", "Mochi", 0).body_color is None
    assert Mascot.create("mochi", "Mochi", 0, body_color="#aBc123").body_color == "#aBc123"


@pytest.mark.parametrize("color", ["red", "#12345", "#GGGGGG", "123456", "#1234567", ""])
def test_create_rejects_a_bad_body_color(color):
    with pytest.raises(InvalidMascotException):
        Mascot.create("mochi", "Mochi", 0, body_color=color)


def test_update_body_color_keep_reset_set():
    m = Mascot.create("mochi", "Mochi", 0, body_color="#112233")
    m.update(name="Moo")
    assert m.body_color == "#112233"
    m.update(body_color="#ABCDEF")
    assert m.body_color == "#ABCDEF"
    m.update(body_color=None)
    assert m.body_color is None


def test_update_with_a_bad_body_color_changes_nothing():
    m = Mascot.create("mochi", "Mochi", 100, body_color="#112233")
    with pytest.raises(InvalidMascotException):
        m.update(name="New", body_color="nope")
    assert (m.name, m.body_color) == ("Mochi", "#112233")


def test_update_rejects_bad_values_and_leaves_the_mascot_unchanged():
    m = Mascot.create("mochi", "Mochi", 100)
    with pytest.raises(InvalidMascotException):
        m.update(name="", coin_cost=5)
    assert (m.name, m.coin_cost) == ("Mochi", 100)


def test_update_does_not_mutate_the_callers_images_dict():
    m = Mascot.create("mochi", "Mochi", 0, images=IDLE)
    m.update(images={MascotState.HAPPY: "https://img/h.png"})
    assert MascotState.HAPPY not in IDLE


def test_default_is_locked():
    d = Mascot.create("default", "Fen", 0, active=True)
    for change in ({"active": False}, {"coin_cost": 1}):
        with pytest.raises(MascotDefaultLockedException):
            d.update(**change)
    d.update(name="Fen 2")  # rename is fine
    with pytest.raises(MascotDefaultLockedException):
        d.ensure_deletable()


def test_other_mascots_are_deletable():
    Mascot.create("mochi", "Mochi", 0).ensure_deletable()
