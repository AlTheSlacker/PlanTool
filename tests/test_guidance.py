"""guidance (components:4) and the vendored methodology assets."""

import pytest

from engine.guidance import Guidance, GuidanceUnreadable, UnknownStage
from engine.methodology import (
    ASSETS,
    DEFAULT_REVISION,
    EARLIEST_LOADABLE_REVISION,
    RevisionNotLoadable,
    load,
)


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
    assert exc.value.detail["valid_range"] == f"1-{load(DEFAULT_REVISION).stage_range[1]}"


def test_script_carries_the_revision_stamp(guidance):
    """requirements:71 — content assets carry a content-revision stamp."""
    script = guidance.get_stage_script(2)
    assert script.revision_stamp == load(DEFAULT_REVISION).revision_stamp


def test_each_revision_stamp_names_its_own_revision():
    """A stamp that does not identify its revision is not a stamp (DEFECTS.md F31).

    `rev3/manifest.yaml` was created by copying rev 2's, stamp included, so both revisions
    answered `plantool-rev2-2026-07-15` and nothing could tell them apart — which defeats the
    migration path `requirements:71` added the stamp to enable. The old version of the test
    above asserted that literal against whichever revision was default, so it agreed with the
    copy and reported success for eighteen days. Assert the *relationship*, never the value.

    Only rev 3 is asserted here, because rev 2 is frozen v1 provenance written in v1's
    vocabulary (`stages:`, not `stages:`) and this loader will not read it. That is
    resolved deliberately, not merely observed: rev 2 is declared frozen provenance and
    rev 3 is the earliest loadable baseline, so `requirements:71`'s migration path is
    forward-only. See DEFECTS.md F43 and the frozen-provenance tests below.
    """
    stamp = load(DEFAULT_REVISION).revision_stamp
    assert f"rev{DEFAULT_REVISION}" in stamp, stamp


@pytest.mark.parametrize("revision", (2, 3))
def test_frozen_provenance_revisions_are_not_loadable(revision):
    """Retained as frozen provenance, refusing to load honestly by their own type rather
    than with a raw KeyError from meeting the wrong key (DEFECTS.md F43).

    rev 3 joined rev 2 there in v3 change 1: it is keyed `packages:` while the loader
    reads `stages:` again, and its stage-6 script names three tools that no longer exist,
    so serving it would raise at the door.
    """
    with pytest.raises(RevisionNotLoadable) as exc:
        load(revision)
    message = str(exc.value)
    assert f"revision {EARLIEST_LOADABLE_REVISION}" in message
    assert "forward-only" in message


def test_rev2_is_still_verbatim_v1_provenance():
    """Option (b), not (a): the loader refuses rev 2; it does not rewrite rev 2's content.
    The asset stays byte-faithful v1 — still `stages:`, never migrated to `packages:`."""
    manifest = (ASSETS / "rev2" / "manifest.yaml").read_text(encoding="utf-8")
    assert "\nstages:" in manifest
    assert "\npackages:" not in manifest


def test_rev3_is_kept_as_it_was_written():
    """The same rule applied to the revision this change superseded: it is retained, not
    rewritten, so a plan stamped rev 3 can still be read by a person."""
    manifest = (ASSETS / "rev3" / "manifest.yaml").read_text(encoding="utf-8")
    assert "\npackages:" in manifest
    assert (ASSETS / "rev3" / "package6_architecture.md").exists()


def test_earliest_loadable_baseline_actually_loads():
    """The floor is not above the default — the earliest loadable revision loads."""
    assert EARLIEST_LOADABLE_REVISION <= DEFAULT_REVISION
    assert load(EARLIEST_LOADABLE_REVISION).revision == EARLIEST_LOADABLE_REVISION


def test_frozen_provenance_revision_is_refused_by_guidance():
    """The deliberate refusal survives the guidance boundary as itself — not relabelled
    GuidanceUnreadable, which would frame an intentional policy as an integrity failure."""
    with pytest.raises(RevisionNotLoadable):
        Guidance(revision=2)


def test_missing_revision_is_unreadable():
    with pytest.raises(GuidanceUnreadable):
        Guidance(revision=99)


def test_redteam_brief_is_available(guidance):
    assert "red" in guidance.get_auxiliary("redteam").lower()


def test_a_stages_core_content_checks_name_tables_the_manifest_declares():
    """DEFECTS.md F48 (and F11 before it) — every table a stage's own core-content checks
    read must be a table that stage declares it fills.

    F11 migrated stage 1's checks off v1's `decisions`-with-a-`Goal:`-prefix shape onto
    first-class `goals`/`non_goals`/`stack` tables, but left the script and the manifest
    naming the old ones. A planner who followed the script filed where the gate could not
    look, so the "nothing recorded yet" gap never cleared. This is the mechanical check F11
    asked for and nobody wrote until F48: a stage-scoped `empty_table`/`missing_field` gap
    rule, or a `non_empty` gate criterion, names the table that stage fills — and it must be
    one the manifest lists for that stage.

    Cross-checks (`traced`/`untraced`) are excluded on purpose: they read *other* stages'
    tables by design — a stage-2 gate reads stage-1 `goals` to check coverage — so a
    superset rule over them would be wrong, not stricter."""
    m = load()
    core_gap_types = {"empty_table", "missing_field"}
    for stage in m.stages:
        declared = set(stage.tables)
        read = {
            rule.spec["table"]
            for rule in m.rules
            if rule.stage == stage.number and rule.type in core_gap_types
        } | {
            criterion.spec["table"]
            for criterion in m.criteria_for(stage.number)
            if criterion.type == "non_empty"
        }
        missing = read - declared
        assert not missing, (
            f"stage {stage.number} core checks read {sorted(missing)} "
            f"but its manifest tables are {sorted(declared)}"
        )
