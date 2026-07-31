"""The only place the engine creates, formats or parses a timestamp.

**Timestamps here are a record, never a decision.** Nothing in this module measures elapsed
time, because nothing in the engine is allowed to branch on it — see the note where
`age_seconds()` used to be.

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


# `age_seconds()` stood here, answering "how long ago was this?". Deleted 2026-07-22 along
# with its three callers — a lock takeover after ten minutes of silence, a task judged
# abandoned after a day, and a windowed idempotency key. All three let elapsed time decide
# what the program did next, and elapsed time cannot carry that: a clock is not monotonic,
# not shared between machines, and not ordered between two things inside one tick, so every
# bug it causes is intermittent and depends on how fast the machine was that day.
#
# **A timestamp records when something happened. It never decides what happens next.**
# (Owner's rule, 2026-07-21/22.) Control flow needs state the program wrote on purpose and
# can read back the same way every time — a flag, a counter, a recorded transition.
#
# If you find yourself wanting this function back, the thing you actually want is a
# recorded event. `tests/test_clock.py` fails the build if it returns.


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
