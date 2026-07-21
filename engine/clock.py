"""The only place the engine creates, formats, parses or ages a timestamp.

Owner request, 2026-07-21: wrap the timestamp setter so that moving to a backend with a
native date/time type is a change to one file rather than a search across thirty tables.

**A setter alone does not achieve that**, which is why this module has four functions and
not one. Swap `now()` to return a `datetime` and every *reader* still assumes a string —
`datetime.fromisoformat(stamp)` fails, `stamp[:10]` fails, `ORDER BY` keeps working but on
the wrong thing. The seam has to cover creation *and* interpretation or it is not a seam.
So: nothing outside this module constructs a timestamp, and nothing outside it turns a
stored value back into a `datetime`.

**Why the stored form is ISO-8601 text.** SQLite has five storage classes — NULL, INTEGER,
REAL, TEXT, BLOB — and no date among them. A column declared `DATE` gets NUMERIC affinity
and stores whatever it is handed, so it is a comment rather than a type. The real choice was
ISO-8601 text against integer epoch, and text wins *here* for a specific reason: this
database is a forensic record read directly by humans and by LLMs (`get_rows`,
`plan_status`, and `entities:13`'s "what exactly did the engine see"). `1753086516` teaches
a reader nothing; `2026-07-21T08:48:36+00:00` is self-describing with no conversion step.
The 8-versus-32-bytes saving is the wrong trade for a record whose whole job is being read
later. Nothing is given up: fixed-width UTC means lexicographic order *is* chronological
order, so `ORDER BY` and `BETWEEN` work, and SQLite's own `date()`, `datetime()`,
`julianday()` and `strftime()` all accept this form.

**The invariant that makes that true, and it is load-bearing:** every stored timestamp is
timezone-aware UTC at microsecond precision. Mix in a naive stamp, or a `Z` suffix instead
of `+00:00`, and comparison keeps *succeeding* while being wrong — a silent ordering bug,
which is the missing-denominator shape this build keeps finding (DEFECTS.md F23/F26). An
invariant nothing enforces is not an invariant (F27), so `tests/test_clock.py` checks both
the format and that no other module generates or parses one.
"""

from __future__ import annotations

from datetime import UTC, datetime

#: What a stored timestamp looks like, for documentation and for the check that enforces it.
#: Timezone-aware UTC, microsecond precision, ISO-8601 — e.g. 2026-07-21T08:48:36.647123+00:00
STORAGE_PRECISION = "microseconds"


def now() -> str:
    """The current instant, in storage form.

    `requirements:48` — every entry carries a creation timestamp. Every `created_at` in the
    schema is written from here and from nowhere else, which is what makes the format
    uniform by construction rather than by convention.
    """
    return datetime.now(UTC).isoformat(timespec=STORAGE_PRECISION)


def parse(value: str | datetime) -> datetime:
    """A stored timestamp as an aware `datetime`.

    Accepts a `datetime` unchanged so that a backend with a native date/time type needs no
    change at any call site — this is the half of the seam a setter alone would miss.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.fromisoformat(value)


def age_seconds(value: str | datetime) -> float:
    """How long ago `value` was. Empty means "never", which ages as zero rather than
    raising: an unset timestamp is a fact about the row, not a corrupt one."""
    if not value:
        return 0.0
    return (datetime.now(UTC) - parse(value)).total_seconds()


def is_storage_form(value: str) -> bool:
    """Whether `value` is in the exact form `now()` produces.

    Used by the check rather than by the engine. It is deliberately strict about the
    timezone: a naive stamp sorts *before* every aware one at the same instant, so mixing
    the two silently reorders history.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None and value == parsed.isoformat(
        timespec=STORAGE_PRECISION
    )
