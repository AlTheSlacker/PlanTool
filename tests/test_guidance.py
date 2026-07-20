"""guidance (components:4) and the vendored methodology assets."""

import pytest

from engine.guidance import Guidance, GuidanceUnreadable, UnknownStage
from engine.methodology import load


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


def test_every_stage_has_a_readable_script(guidance):
    low, high = load().stage_range
    for stage in range(low, high + 1):
        script = guidance.get_stage_script(stage)
        assert script.text.strip()
        assert script.stage == stage


def test_elicit_stages_require_divergence(guidance):
    """requirements:16 — elicit stages present divergence prompts and solicit
    owner-generated candidates before agent drafts."""
    for stage in (1, 2, 3):
        script = guidance.get_stage_script(stage)
        assert script.mode == "elicit"
        assert script.divergence_required is True

    for stage in (4, 5, 6):
        assert guidance.get_stage_script(stage).divergence_required is False


def test_elicit_scripts_actually_contain_the_divergence_round(guidance):
    """The flag is only worth having if the vendored content backs it."""
    for stage in (1, 2, 3):
        text = guidance.get_stage_script(stage).text.lower()
        assert "divergence" in text


def test_unknown_stage_names_the_valid_range(guidance):
    with pytest.raises(UnknownStage) as exc:
        guidance.get_stage_script(99)
    assert exc.value.detail["valid_range"] == "1-8"


def test_script_carries_the_revision_stamp(guidance):
    """requirements:71 — content assets carry a content-revision stamp."""
    script = guidance.get_stage_script(2)
    assert script.revision_stamp == "plantool-rev2-2026-07-15"


def test_missing_revision_is_unreadable():
    with pytest.raises(GuidanceUnreadable):
        Guidance(revision=99)


def test_redteam_brief_is_available(guidance):
    assert "red" in guidance.get_auxiliary("redteam").lower()
