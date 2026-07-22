"""The timestamp seam (`engine/clock.py`) and the invariant it exists to hold.

Two things are checked here, and the second matters more than the first.

1. The stored form is what it claims: timezone-aware UTC, microsecond precision, ISO-8601.
2. **Nothing outside `clock.py` creates or interprets a timestamp.** That is what makes the
   format uniform by construction rather than by convention, and it is what makes moving to
   a backend with a native date/time type a change to one file.

The second check exists because of DEFECTS.md F27: an invariant nothing enforces is not an
invariant, and this one fails *silently* when it breaks. A naive stamp mixed in with aware
ones still compares without error — it just sorts before every aware stamp at the same
instant, quietly reordering history. That is the same class as F23 and F26: a check that
runs, succeeds, and means nothing.
"""

import re
from pathlib import Path

from engine import clock

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"

#: The ways a timestamp can be conjured or decoded. Anything here outside clock.py is a
#: second source of truth for the one thing that has to stay uniform.
CONSTRUCTORS = (
    r"\bdatetime\.now\(",
    r"\bdatetime\.utcnow\(",
    r"\.isoformat\(",
    r"\bdatetime\.fromisoformat\(",
    r"\bdatetime\.strptime\(",
    r"\btime\.time\(\)",
    r"CURRENT_TIMESTAMP",
)


def test_the_stored_form_is_aware_utc_at_fixed_precision():
    stamp = clock.now()
    assert clock.is_storage_form(stamp), stamp
    assert clock.parse(stamp).tzinfo is not None
    assert stamp.endswith("+00:00"), (
        "the offset must be explicit and identical on every stamp, or lexicographic order "
        "stops matching chronological order"
    )


def test_a_naive_or_differently_precise_stamp_is_not_storage_form():
    """The check must be able to fail — F23's disease is a check that cannot."""
    assert not clock.is_storage_form("2026-07-21T08:48:36.647123")      # naive
    assert not clock.is_storage_form("2026-07-21T08:48:36+00:00")       # second precision
    assert not clock.is_storage_form("2026-07-21")
    assert not clock.is_storage_form("not a date")


def test_parse_accepts_a_datetime_so_the_seam_survives_a_backend_change():
    """The half a setter-only wrapper would miss. On a backend with a native date/time
    type `now()` returns a datetime and every call site must keep working untouched."""
    from datetime import UTC, datetime

    native = datetime.now(UTC)
    assert clock.parse(native) == native
    assert clock.parse(clock.now()).tzinfo is not None


def test_the_clock_cannot_measure_elapsed_time():
    """`age_seconds()` was deleted on 2026-07-22 with its three callers. A timestamp
    records when something happened and never decides what happens next, so the engine has
    no business asking how long ago anything was. This fails if the function returns."""
    assert not hasattr(clock, "age_seconds")


def test_only_clock_creates_or_interprets_a_timestamp():
    """One owner, enforced. Without this the seam is a convention, and F27 is the standing
    evidence for what conventions are worth."""
    offenders = []
    for path in sorted(ENGINE.rglob("*.py")):
        if path.name == "clock.py":
            continue
        source = path.read_text(encoding="utf-8")
        # Comments and docstrings discuss these names legitimately; only code counts.
        code = "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("#")
        )
        for pattern in CONSTRUCTORS:
            for match in re.finditer(pattern, code):
                line = code[: match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{line} {pattern}")
    assert not offenders, (
        "timestamps must be created and parsed only in engine/clock.py:\n  "
        + "\n  ".join(offenders)
        + "\n\nUse clock.now() or clock.parse(). A second way to make a timestamp is a "
          "second format waiting to happen, and the failure is silent."
    )
