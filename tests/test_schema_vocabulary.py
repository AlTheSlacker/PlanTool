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
    # `approved_at` stood here until schema 11. It meant "terms: the owner settled a
    # definition the planner proposed", and it left with the only column that ever used it
    # — the glossary is the owner's to write, so there is no proposal to settle. A declared
    # role outliving its column is a citation to nothing, which is what
    # `test_every_declared_timestamp_role_has_a_column` below now catches.
    "detached_at": "label_attachments: the attachment was taken off its target; the row "
                   "stays as the record that it was once there",
}

#: Suffixes whose vocabulary is closed: the declared types a column with that suffix may
#: have, and what the suffix means. Only `_at` is enumerated by name; these are checked for
#: shape, because their stems are legitimately per-table (`brief_id`, `task_id`) while their
#: *role* must be uniform. The codebase already made this distinction — `gap_key`,
#: `warning_key`, `idempotency.key` — and three columns did not follow it: `rule_id`,
#: `lease_id`, `session_id` were opaque strings wearing the spelling of an integer key.
#: `gap_overlay` carried `gap_key` and `rule_id` side by side, meaning the same kind of thing.
#:
#: **This map was decorative until v3 change 2.** The check below read it for its message
#: text and hardcoded the suffixes it actually tested, so `_by` — declared here since the
#: file was written — was checked nowhere, and adding a suffix to this map added a docstring
#: rather than a check. It now drives the check that quotes it: a declared shape is enforced
#: by being declared, which is this project's own standing lesson sitting inside the file
#: written to enforce vocabulary mechanically.
SHAPES = {
    "_id": (("INTEGER",), "an integer key of a row in this database — never a string"),
    "_key": (("TEXT",), "an opaque or externally-supplied string identifier"),
    "_ref": (("TEXT",), "a `table:ordinal` row reference as text — never an integer"),
    # Two types, declared rather than assumed. `plan_rows.superseded_by` is a row ref and
    # `briefs.superseded_by` is a brief id, so "what caused this" is spelled both ways
    # already; `findings.resolve_by` is neither — it is the stage ordinal of the gate that
    # locks until the finding is resolved, and the schema records that it keeps the name
    # deliberately. A check that admits both is weaker than one that admits one, and it is
    # what is true.
    "_by": (("INTEGER", "TEXT"), "who or what caused this — an id, a ref, or (resolve_by) "
                                 "the gate ordinal it answers to"),
    # Declared by v3 change 4, which supplies the third occurrence. The schema already held
    # two names for one concept — `gap_overlay.root_ref` and `scope_attachments.target_root`
    # are both *the lineage root of the row this record is keyed to*, spelt two ways — and
    # `SHAPES` had no entry for `_root`, so `target_root` had never been checked by
    # anything. `label_attachments.target_root` is the third, which is the moment this map
    # either does its job or becomes the thing it exists to prevent. Declaring it does not
    # rename either existing column; it makes the next one a deliberate act. Renaming
    # `root_ref` is a separate change's work.
    "_root": (("TEXT",), "the lineage root of a target row, as a `table:ordinal` ref"),
}

#: Every column that records a justification, keyed `table.column`, with the role it plays.
#: A new one is a deliberate act: add it here, or reuse the word that already says this.
#:
#: **Two roles, and keeping them apart is the whole point** (v3 change 2 §2):
#:
#: - **why an act was performed** — `reason`, attached to a transition, written once at the
#:   moment of the act. Where a table holds more than one, the column is prefixed by the
#:   act: `retire_reason`, `supersede_reason`.
#: - **why a row says what it says** — `grounds`, with `alternatives` for what was
#:   considered and rejected. Attached to the content, not to a transition. A row has
#:   grounds from the moment it exists; it acquires a `retire_reason` only if it is retired.
#:
#: **Keyed `table.column` and not by bare column name**, which is what the neighbouring
#: `TIMESTAMP_ROLES` does and would have been the natural thing to copy. The entry *is* the
#: role, and the role differs per table: `behaviour_amendments.reason` names amending,
#: `scope_attachments.reason` names attaching. One key carrying three roles records none of
#: them — and would silently pre-declare `reason` and `retire_reason` for every future
#: table, which is a check that certifies whatever anybody writes.
JUSTIFICATION_ROLES = {
    "plan_rows.grounds": "why this row's content is what it is",
    "plan_rows.alternatives": "what else was considered, and why it lost",
    "plan_rows.retire_reason": "why the row was withdrawn from live reads",
    "plan_rows.supersede_reason": "why the row was abandoned in favour of its replacement",
    "plan_versions.reason": "why the snapshot was taken",
    "gap_overlay.reason": "why the gap was dismissed, or reopened",
    "warnings.reason": "why the warning was suppressed",
    "spikes.block_reason": "requirements:26 — the dependency the experiment cannot reach",
    "tasks.block_reason": "what is stopping the task",
    "behaviour_amendments.reason": "why the behaviour was amended",
    "brief_rows.reason": "why the row was included in, or omitted from, the brief",
    "scope_attachments.reason": "why the attachment was made",
    # `terms.ban_reason` stood here until schema 11 — "why the word was retired" — and left
    # with the banned list. Attaching a label records no reason, deliberately: it is the act
    # the design makes free, so this change adds nothing here and removes one.
    "finding_reallocations.reason": "why the finding now answers to a later gate",
    "findings.reason": "how the finding was closed — for an accepted risk, the owner's "
                       "acceptance. It was `rationale` until schema 9",
    "catalogue.retire_reason": "why the catalogue entry was withdrawn — at planning time a "
                               "design that changed, at build time an absence discovered",
    "catalogue_comparisons.reason": "why this candidate was judged to stand in that "
                                    "relationship to the proposal. It names the act of "
                                    "judging, which is why it is a `reason` and not "
                                    "`grounds`: the comparison row *is* the act and has no "
                                    "content of its own to have grounds for",
    # Declared here *because* it is not one, so the next reader who notices it does not
    # have to re-derive the argument. It holds what was found when the claim was tested;
    # that is evidence, and it was the parameter `fence_claim(rationale)` that was misspelt.
    "technical_claims.evidence": "what was found when the claim was tested — not a "
                                 "justification, and not to be renamed to `reason`",
}

#: Second spellings of a role that already has a word. A deny-list is usually the wrong
#: tool, and the reason it is right here is specific: the failure being prevented is a
#: *second spelling*, and naming the spellings is the only way to catch that mechanically.
#: This file's own docstring says nothing mechanical can catch a duplicate meaning that
#: shares no lexical structure — *without judgment*. These four are the ones already seen.
RETIRED_JUSTIFICATION_WORDS = ("rationale", "justification", "explanation", "why")


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


def test_every_declared_timestamp_role_has_a_column():
    """The other direction, and nothing checked it until v3 change 4.

    `test_every_timestamp_column_is_a_declared_role` iterates columns and looks each up in
    the register. Nothing iterated the register and looked for columns, so a role left
    behind after its column died was invisible **forever** — which is exactly how
    `approved_at` would have survived this change, a citation to nothing sitting in a
    register whose whole purpose is that names are declared deliberately. The same defect
    has bitten this repository once already, in the other register: `GLOSSARY.md` carried an
    exception protecting `PartsDontCover`, an identifier that does not exist.

    It is a few lines against the same `_columns()` helper and it generalises to every
    future change, which is what makes it worth more than the one removal that prompted it.
    """
    declared = {column for _, column, _ in _columns()}
    orphaned = sorted(role for role in TIMESTAMP_ROLES if role not in declared)
    assert not orphaned, (
        f"declared timestamp roles with no column: {orphaned}. A role outliving the column "
        "it was declared for is a citation to nothing — delete it, or say which table now "
        "carries it."
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
    rather than a matter of taste.

    It iterates `SHAPES` rather than restating its keys, so a suffix added to that map is
    enforced by having been added. It hardcoded three of the four until v3 change 2, which
    is why `_by` sat declared and unchecked from the day this file was written.
    """
    wrong = []
    for table, column, kind in _columns():
        for suffix, (allowed, meaning) in SHAPES.items():
            if column.endswith(suffix) and kind not in allowed:
                wrong.append(
                    f"{table}.{column} is {kind}, expected "
                    f"{' or '.join(allowed)} ({meaning})"
                    + (". An opaque string identifier is spelled `_key` here."
                       if suffix == "_id" else "")
                )
    assert not wrong, "\n  ".join(wrong)


def test_every_justification_column_is_a_declared_role():
    """A column recording *why* is one of two roles, and each is declared with the role it
    plays. A new spelling has to be argued for out loud rather than added in one table.

    Matches bare `reason`, `grounds` and `alternatives` as well as the `_reason` suffix: a
    suffix rule alone would not see `findings.reason` at all, which is the column that
    started this.
    """
    undeclared = sorted({
        f"{table}.{column}"
        for table, column, _ in _columns()
        if (column in ("reason", "grounds", "alternatives")
            or column.endswith("_reason"))
        and f"{table}.{column}" not in JUSTIFICATION_ROLES
    })
    assert not undeclared, (
        "undeclared justification columns:\n  " + "\n  ".join(undeclared)
        + "\n\nA justification is one of two roles. If it says why an *act* was performed "
          "it is a `reason`, prefixed by the act where a table holds more than one. If it "
          "says why the row's *content* is what it is, `plan_rows.grounds` already means "
          "that. Add it to JUSTIFICATION_ROLES with the role it plays."
    )


def test_no_column_spells_a_justification_a_second_way():
    """`rationale` was the live one: a parameter name over a column called something else,
    and a second word for what `reason` already meant."""
    found = sorted({
        f"{table}.{column}"
        for table, column, _ in _columns()
        for word in RETIRED_JUSTIFICATION_WORDS
        if column == word or column.endswith(f"_{word}")
    })
    assert not found, (
        f"a justification spelled a second way: {found}. This store has two words for "
        f"this and only two — `reason` for why an act was performed, `grounds` for why a "
        f"row's content is what it is."
    )


def test_the_declared_justification_set_is_the_whole_of_it():
    """The guard against the check going blind — the standing evidence being a check that
    ran green while seeing four names where there were twenty-two.

    The count is stated so that a fixture asserting a number nobody wrote down cannot
    cement whichever number a builder guessed. Sixteen justification columns, plus
    `technical_claims.evidence` declared as the one that is deliberately not one.

    Eighteen until v3 change 4, which drops `terms.ban_reason` with the banned list and adds
    none — the specification said this register was "unchanged at 18: nothing this change
    adds carries a reason", which was true about additions and forgot the deletion. The
    assertion below is what caught it: a declared member whose column has died.

    Sixteen until v3 change 3, which adds `catalogue.retire_reason` and
    `catalogue_comparisons.reason`. Those two are why this register is keyed `table.column`:
    under bare-column keying `reason` and `retire_reason` were already declared, so change 3
    would have added nothing to a check that could never have fired on it.
    """
    assert len(JUSTIFICATION_ROLES) == 17, sorted(JUSTIFICATION_ROLES)
    declared_columns = {key.split(".", 1)[1] for key in JUSTIFICATION_ROLES}
    assert declared_columns == {
        "grounds", "alternatives", "reason", "retire_reason", "supersede_reason",
        "block_reason", "evidence",
    }
    # Every declared member is a column that exists — a register naming a column the schema
    # dropped is a register nobody has read since.
    live = {f"{table}.{column}" for table, column, _ in _columns()}
    assert not sorted(set(JUSTIFICATION_ROLES) - live)


def test_every_table_records_when_its_rows_were_created():
    """The owner's question — "I said something yesterday, find it" — is unanswerable for a
    table with no creation stamp. `gap_overlay` and `claim_tracks` each had `updated_at`
    alone, so they could say when a dismissal was last touched and never when it was made.

    Pure junction tables are exempt: they carry no independent existence and are written
    and read with their parent.
    """
    junctions = {
        "conflict_refs", "claim_refs", "finding_refs", "task_deps",
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
    assert {t for t, _, _ in columns} >= {"plan_rows", "tasks", "briefs"}
