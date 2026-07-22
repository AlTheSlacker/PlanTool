"""guidance (components:4) and the vendored methodology assets."""

import pytest

from engine.guidance import Guidance, GuidanceUnreadable, UnknownPackage
from engine.methodology import DEFAULT_REVISION, load


@pytest.fixture
def guidance():
    return Guidance()


def test_mandate_is_served(guidance):
    text = guidance.get_mandate()
    assert "engineer's mandate" in text.lower()
    assert len(text) > 1000


def test_mandate_carries_the_divergence_clause(guidance):
    """decisions:36 — the countermeasure to the recorded interview friction."""
    text = guidance.get_mandate().lower()
    assert "divergence before drafts" in text
    assert "before" in text and "draft" in text


def test_mandate_carries_the_challenge_duty(guidance):
    """'agreeable form-filling is this tool's defining failure mode'."""
    assert "challenge duty" in guidance.get_mandate().lower()


def test_every_package_has_a_readable_script(guidance):
    low, high = load().package_range
    for package in range(low, high + 1):
        script = guidance.get_package_script(package)
        assert script.text.strip()
        assert script.package == package


def test_elicit_packages_require_divergence(guidance):
    """requirements:16 — elicit packages present divergence prompts and solicit
    owner-generated candidates before agent drafts."""
    for package in (1, 2, 3):
        script = guidance.get_package_script(package)
        assert script.mode == "elicit"
        assert script.divergence_required is True

    for package in (4, 5, 6):
        assert guidance.get_package_script(package).divergence_required is False


def test_elicit_scripts_actually_contain_the_divergence_round(guidance):
    """The flag is only worth having if the vendored content backs it."""
    for package in (1, 2, 3):
        text = guidance.get_package_script(package).text.lower()
        assert "divergence" in text


def test_unknown_package_names_the_valid_range(guidance):
    with pytest.raises(UnknownPackage) as exc:
        guidance.get_package_script(99)
    assert exc.value.detail["valid_range"] == "1-8"


def test_script_carries_the_revision_stamp(guidance):
    """requirements:71 — content assets carry a content-revision stamp."""
    script = guidance.get_package_script(2)
    assert script.revision_stamp == load(DEFAULT_REVISION).revision_stamp


def test_each_revision_stamp_names_its_own_revision():
    """A stamp that does not identify its revision is not a stamp (DEFECTS.md F31).

    `rev3/manifest.yaml` was created by copying rev 2's, stamp included, so both revisions
    answered `plantool-rev2-2026-07-15` and nothing could tell them apart — which defeats the
    migration path `requirements:71` added the stamp to enable. The old version of the test
    above asserted that literal against whichever revision was default, so it agreed with the
    copy and reported success for eighteen days. Assert the *relationship*, never the value.

    Only rev 3 is asserted here, because rev 2 is frozen v1 provenance written in v1's
    vocabulary (`stages:`, not `packages:`) and this loader cannot read it. That is worth
    knowing on its own: `requirements:71` promises a path that migrates a plan from one
    revision to the next, and there is currently exactly one loadable revision to migrate
    between. Bound to the M6 gate with rev 3's outstanding half.
    """
    stamp = load(DEFAULT_REVISION).revision_stamp
    assert f"rev{DEFAULT_REVISION}" in stamp, stamp


def test_missing_revision_is_unreadable():
    with pytest.raises(GuidanceUnreadable):
        Guidance(revision=99)


def test_redteam_brief_is_available(guidance):
    assert "red" in guidance.get_auxiliary("redteam").lower()
