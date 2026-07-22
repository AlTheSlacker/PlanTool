"""Column names are drawn from a declared vocabulary, not invented per table.

The schema had **eight** names for "when this row came into existence" — `created_at`,
`taken_at`, `stored_at`, `acquired_at`, `raised_at`, `frozen_at`, `composed_at`,
`captured_at` — each perfectly sensible where it was written, and collectively the same
two-names-for-one-thing disease `GLOSSARY.md` exists to prevent. `GLOSSARY.md`'s own sweep
never saw them because it was hunting structural nouns.

**Why this check and not another careful sweep.** F27 is the standing evidence: the M5b
vocabulary sweep was done by reading, declared complete, and left 20 violations that a
ten-line check found in 0.1 seconds. A rename without an enforcement mechanism restores the
starting conditions and waits.

**What it can and cannot do**, stated honestly because the boundary matters:

- It catches a *new spelling of a known role* — a fresh `*_at` or `*_id` name. That is where
  nearly all of the observed damage came from, because these suffixes mark exactly the
  columns that recur across tables.
- It cannot catch a genuinely new concept given a name that duplicates an existing one in
  meaning while sharing no lexical structure. Nothing mechanical can, without judgment. What
  it *does* do is make the moment of invention visible: a name outside the declared set stops
  the suite and has to be justified out loud, which is the same move the product makes when
  it refuses to let an omission be silent.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "engine" / "schema.py"

#: Every `*_at` column in the schema, and what each means. A new one is a deliberate act:
#: add it here with its meaning, or reuse the one that already says this.
#:
#: `created_at` and `updated_at` are the general pair. The rest name a *specific transition*
#: in a lifecycle — they are not creation wearing a costume, which is precisely what the
#: eight retired spellings were.
TIMESTAMP_ROLES = {
    "created_at": "when the row came into existence — the only word for this",
    "updated_at": "when a mutable row last changed; absent on immutable tables by design",
    "superseded_at": "requirements:61 — stamped once when a replacement is written",
    "retired_at": "withdrawn from live reads with a recorded reason",
    "resolved_at": "state_machines — an open thing reached its terminal state",
    "concluded_at": "spikes:  the experiment produced its outcome",
    "approved_at": "terms: the owner settled a definition the planner proposed",
}

#: Suffixes whose vocabulary is closed, mapped to their declared members. Only `_at` is
#: enumerated by name; the others are checked for shape, because their stems are
#: legitimately per-table (`package_id`, `subtask_id`) while their *role* must be uniform.
#: The codebase already made this distinction — `gap_key`, `warning_key`, `idempotency.key`
#: — and three columns did not follow it: `rule_id`, `lease_id`, `session_id` were opaque
#: strings wearing the spelling of an integer key. `gap_overlay` carried `gap_key` and
#: `rule_id` side by side, meaning the same kind of thing.
SHAPES = {
    "_id": "an integer key of a row in this database — never a string",
    "_key": "an opaque or externally-supplied string identifier",
    "_ref": "a `table:ordinal` row reference as text — never an integer",
    "_by": "who or what caused this, as an id or ref",
}


def _columns() -> list[tuple[str, str, str]]:
    """(table, column, declared type) for every column in the schema."""
    source = SCHEMA.read_text(encoding="utf-8")
    out = []
    for table in re.finditer(
        r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", source, re.DOTALL
    ):
        for line in table.group(2).splitlines():
            line = line.split("--")[0].strip()
            match = re.match(r"^(\w+)\s+(INTEGER|TEXT|REAL|BLOB|NUMERIC)\b", line)
            if match:
                out.append((table.group(1), match.group(1), match.group(2)))
    return out


def test_every_timestamp_column_is_a_declared_role():
    """A new `*_at` spelling must be a deliberate addition, not a local invention."""
    undeclared = sorted({
        f"{table}.{column}"
        for table, column, _ in _columns()
        if column.endswith("_at") and column not in TIMESTAMP_ROLES
    })
    assert not undeclared, (
        "undeclared timestamp columns:\n  " + "\n  ".join(undeclared)
        + "\n\nEither reuse the role that already means this — `created_at` covers every "
          "'when was this written' — or add the new one to TIMESTAMP_ROLES with what "
          "distinguishes it. Eight spellings of `created_at` is how this schema got here."
    )


def test_creation_is_spelled_one_way():
    """The specific regression. `composed_at`, `captured_at` and friends all meant
    `created_at` and each looked reasonable in its own table."""
    banned = ("taken_at", "stored_at", "acquired_at", "raised_at",
              "frozen_at", "composed_at", "captured_at", "renewed_at")
    found = sorted({
        f"{table}.{column}" for table, column, _ in _columns() if column in banned
    })
    assert not found, f"creation spelled a second way: {found}"


def test_id_and_ref_columns_keep_their_types():
    """`_id` is an integer key of a row here, `_key` is an opaque string, `_ref` is a
    `table:ordinal` reference. Mixing them is how a join silently matches nothing — the
    failure mode behind F20 and F24 — and the type is what makes the distinction checkable
    rather than a matter of taste."""
    wrong = []
    for table, column, kind in _columns():
        if column.endswith("_id") and kind != "INTEGER":
            wrong.append(
                f"{table}.{column} is {kind}, expected INTEGER ({SHAPES['_id']}). "
                f"An opaque string identifier is spelled `_key` here."
            )
        for suffix in ("_key", "_ref"):
            if column.endswith(suffix) and kind != "TEXT":
                wrong.append(
                    f"{table}.{column} is {kind}, expected TEXT ({SHAPES[suffix]})"
                )
    assert not wrong, "\n  ".join(wrong)


def test_every_table_records_when_its_rows_were_created():
    """The owner's question — "I said something yesterday, find it" — is unanswerable for a
    table with no creation stamp. `gap_overlay` and `claim_tracks` each had `updated_at`
    alone, so they could say when a dismissal was last touched and never when it was made.

    Pure junction tables are exempt: they carry no independent existence and are written
    and read with their parent.
    """
    junctions = {
        "conflict_refs", "claim_refs", "finding_refs", "subtask_deps",
        "source_sections", "brief_rows",
    }
    tables = {table for table, _, _ in _columns()}
    stamped = {table for table, column, _ in _columns() if column == "created_at"}
    missing = sorted(tables - stamped - junctions)
    assert not missing, (
        f"tables with no created_at: {missing}. Every table whose rows have independent "
        "existence records when they came into it."
    )


def test_the_check_can_actually_fail():
    """F23's disease: a check that cannot fail runs, passes, and means nothing."""
    columns = _columns()
    assert len(columns) > 100, f"the schema parser found only {len(columns)} columns"
    assert any(c == "created_at" for _, c, _ in columns)
    assert {t for t, _, _ in columns} >= {"plan_rows", "subtasks", "briefs"}
