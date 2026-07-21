"""Idempotency keys have one owner, and a hand-built key fails the suite.

`decisions:43` promises that a replayed key returns the original receipt and never
duplicates. Twenty-one call sites each built their key by hand as a formatted string with
`now()` appended for uniqueness — which cancels the only thing the key does. The replay
path was unreachable from most of the engine while appearing to be in force.

Extraction alone would not have stopped a twenty-second site: nobody copied the mistake,
they each independently did the obvious thing. So the convention is a check.
"""

import ast
from pathlib import Path

import pytest

from engine.clock import now
from engine.idempotency import InvalidIdempotencyKey, key, within

ENGINE = Path(__file__).resolve().parent.parent / "engine"


def _write_atomic_keys():
    """(file, line, key-argument node) for every write_atomic call in the engine."""
    found = []
    for path in sorted(ENGINE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "write_atomic"):
                continue
            argument = None
            if len(node.args) >= 2:
                argument = node.args[1]
            for kw in node.keywords:
                if kw.arg == "idempotency_key":
                    argument = kw.value
            if argument is not None:
                found.append((path.name, argument.lineno, argument))
    return found


def test_no_hand_built_idempotency_keys():
    """The regression. An f-string here is how the timestamp got into all 21 of them.

    Honest limit: this catches a key *literal* at the call site, which is the form the
    defect took. A key assembled into a local variable first would slip past — that is
    what review is for, and `key()` still refuses the timestamp at runtime.
    """
    offenders = [
        f"{name}:{line}"
        for name, line, node in _write_atomic_keys()
        if isinstance(node, (ast.JoinedStr, ast.Constant))
    ]
    assert not offenders, (
        "idempotency keys built by hand:\n  " + "\n  ".join(offenders)
        + "\n\nBuild them with engine.idempotency.key(), which names the operation and "
          "refuses a timestamp. A key containing the clock is never equal to itself, so "
          "a repeat is never detected."
    )


def test_the_check_can_actually_fail():
    """F23's disease: a check that cannot fail runs, passes and means nothing."""
    found = _write_atomic_keys()
    assert len(found) > 15, f"the scanner found only {len(found)} write_atomic calls"
    assert any(isinstance(n, ast.Call) for _, _, n in found)


def test_a_timestamp_is_refused():
    """The exact bug: `now()` appended to make the key unique."""
    with pytest.raises(InvalidIdempotencyKey, match="timestamp"):
        key("compose", 7, now())


def test_a_datetime_is_refused():
    """The same mistake after a backend swap gives the clock a native type."""
    from engine.clock import parse

    with pytest.raises(InvalidIdempotencyKey, match="timestamp"):
        key("compose", parse(now()))


def test_an_empty_element_is_refused():
    """A missing id silently merges two operations into one — worse than a crash."""
    with pytest.raises(InvalidIdempotencyKey):
        key("compose", 7, "")


def test_the_same_operation_gives_the_same_key():
    """The entire contract."""
    assert key("compose", 7, 2) == key("compose", 7, 2)
    assert key("compose", 7, 2) != key("compose", 7, 3)


def test_a_windowed_key_collapses_repeats_and_a_plain_one_does_not():
    """The deliberate fallback, for operations with no natural discriminator. The window
    is *in* the key, so choosing it is visible — unlike appending now(), which chose a
    window of zero by accident."""
    assert within("sweep", seconds=3600) == within("sweep", seconds=3600)
    assert within("sweep", seconds=3600) != within("sweep", seconds=1800)
