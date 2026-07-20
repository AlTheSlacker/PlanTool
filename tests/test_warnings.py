"""warning-service (components:7)."""

import pytest

from engine.models import RowRef
from engine.warnings import AlreadyResolved, CriticalPoint, WarningNotFound


def raise_one(warns, key="gap:x", message="an open gap nobody has closed"):
    return warns.raise_warning(key, "open_gap", message, source_ref=RowRef("decisions", 1))


# --- raising is idempotent (the mechanism DEFECTS.md F9 records as invented) -------


def test_re_raising_the_same_key_re_presents_one_warning(warns):
    """requirements:22 — re-present until resolved, not accumulate duplicates."""
    first = raise_one(warns)
    second = raise_one(warns)
    assert first.id == second.id
    assert len(warns.all_warnings()) == 1


def test_re_raising_refreshes_the_wording_of_an_active_warning(warns):
    raise_one(warns)
    updated = raise_one(warns, message="the same gap, now with sharper wording")
    assert "sharper wording" in updated.message


# --- contracts:23 -----------------------------------------------------------------


def test_active_warnings_are_returned_without_a_context(warns):
    raise_one(warns)
    assert [w.warning_key for w in warns.active_warnings()] == ["gap:x"]


def test_a_suppressed_warning_leaves_the_ordinary_listing(warns):
    warning = raise_one(warns)
    warns.suppress_warning(warning.id, "accepted for now; revisit at freeze")
    assert warns.active_warnings() == []


def test_a_suppressed_warning_resurfaces_at_a_critical_point(warns):
    """requirements:23 — finalization, red-team entry, and handoff."""
    warning = raise_one(warns)
    warns.suppress_warning(warning.id, "accepted for now")
    for point in (CriticalPoint.FINALIZATION, CriticalPoint.RED_TEAM_ENTRY,
                  CriticalPoint.HANDOFF):
        surfaced = warns.active_warnings(point)
        assert [w.warning_key for w in surfaced] == ["gap:x"]
        assert surfaced[0].resurfaced is True
        assert "suppressed" in surfaced[0].present()


def test_a_revision_is_a_resurfacing_point_too(warns):
    """requirements:55 — a revision touching a suppressed warning re-adjudicates it."""
    warning = raise_one(warns)
    warns.suppress_warning(warning.id, "later")
    assert warns.active_warnings(CriticalPoint.REVISION)


def test_an_unknown_critical_point_is_refused(warns):
    with pytest.raises(ValueError):
        warns.active_warnings("some_other_moment")


def test_a_resolved_warning_never_resurfaces(warns):
    warning = raise_one(warns)
    warns.resolve_warning(warning.id, RowRef("decisions", 2))
    assert warns.active_warnings() == []
    assert warns.active_warnings(CriticalPoint.FINALIZATION) == []


# --- contracts:24 -----------------------------------------------------------------


def test_suppression_records_the_owners_reason(warns):
    warning = raise_one(warns)
    suppressed = warns.suppress_warning(warning.id, "the risk is understood and accepted")
    assert suppressed.state == "suppressed"
    assert "understood" in suppressed.reason


def test_suppression_without_a_reason_is_refused(warns):
    warning = raise_one(warns)
    with pytest.raises(WarningNotFound):
        warns.suppress_warning(warning.id, "   ")


def test_a_resolved_warning_cannot_be_suppressed(warns):
    warning = raise_one(warns)
    warns.resolve_warning(warning.id, RowRef("decisions", 2))
    with pytest.raises(AlreadyResolved):
        warns.suppress_warning(warning.id, "too late")


def test_an_unknown_warning_id_is_named(warns):
    with pytest.raises(WarningNotFound):
        warns.suppress_warning(404, "reason")


# --- contracts:25 -----------------------------------------------------------------


def test_resolution_links_the_row_whose_fix_resolved_it(warns):
    warning = raise_one(warns)
    resolved = warns.resolve_warning(warning.id, "requirements:7")
    assert resolved.state == "resolved"
    assert resolved.resolved_by == RowRef("requirements", 7)


def test_re_raising_does_not_reactivate_a_suppressed_warning(warns):
    """Otherwise suppression would be meaningless: the next gate would undo it."""
    warning = raise_one(warns)
    warns.suppress_warning(warning.id, "accepted")
    raise_one(warns)
    assert warns.get(warning.id).state == "suppressed"
