"""Harness check: the v2 package imports and the frozen spec is present.

These are deliberately trivial. Their job is to prove the M0 groundwork is sound
before M1 starts building against it.
"""

from pathlib import Path

import engine

REPO = Path(__file__).resolve().parent.parent


def test_engine_imports_at_v2():
    assert engine.__version__ == "2.0.0"


def test_frozen_spec_is_present():
    spec = REPO / "spec" / "v2"
    for name in ("plan.md", "plan.yaml", "plan.db"):
        assert (spec / name).is_file(), f"frozen spec missing {name}"


def test_frozen_plan_is_the_expected_one():
    """Guards against the spec being truncated or replaced."""
    plan = (REPO / "spec" / "v2" / "plan.md").read_text(encoding="utf-8")
    assert "brief-composer" in plan
    assert "validation-service" in plan
    assert len(plan) > 150_000


def test_v1_archive_survives():
    assert (REPO / "archive" / "v1" / "engine").is_dir()
