"""The binding vocabulary is enforced, not merely documented (DEFECTS.md F27).

`GLOSSARY.md` retired a set of words on 2026-07-21 and the very next build package
reintroduced two of them. The diagnosis is in the glossary and is worth restating here,
because it is what shapes this check:

**The read-only exception is also the primary input.** Retired words legitimately survive in
`spec/v2/plan.md`, which is *also* the document read immediately before writing each function
— `contracts:40`'s signature is literally `parts: list[SubTaskSpec]`. Ranked by proximity to
the moment of typing, the exception beats the rule. And naming happens at the point of least
attention: the thought goes into the algorithm, the parameter name is incidental typing. No
amount of care fixes either. A check that runs every time does.

Two deliberate design choices:

- **The banned list is parsed out of `GLOSSARY.md`**, never duplicated here. A second copy
  drifts, and a vocabulary rule with two sources of truth is the bug it exists to prevent.
- **It enforces the glossary's own stated rule and not a stricter one.** That rule bans
  seven words as *identifiers* and deliberately omits `component`, `unit` and `chunk`, which
  are pervasive in legitimate prose and in `components:N`. Inventing a harsher rule here
  would put the check and the document out of step, which is the same failure again.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = ROOT / "GLOSSARY.md"
SCANNED = ("engine", "tests")


def _banned() -> set[str]:
    """The words from the glossary's own "No identifier contains ..." rule."""
    for line in GLOSSARY.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("- No identifier contains"):
            return {w.lower() for w in re.findall(r"`([a-z_]+)`", line)} - {"session_id"}
    raise AssertionError(
        "GLOSSARY.md has no 'No identifier contains ...' rule to enforce. The check parses "
        "the glossary rather than carrying its own copy, so the rule going missing must "
        "fail loudly rather than silently disabling the check."
    )


def _exceptions() -> set[str]:
    """The recorded exceptions, as `path:identifier`. Each carries a reason in the
    glossary — adding one is a visible act, not a quiet edit to a deny-list."""
    text = GLOSSARY.read_text(encoding="utf-8")
    block = re.search(r"```vocabulary-exceptions\n(.*?)```", text, re.DOTALL)
    if not block:
        return set()
    return {
        line.split("—")[0].strip()
        for line in block.group(1).splitlines()
        if ":" in line and not line.startswith(" ")
    }


def _tokens(identifier: str) -> set[str]:
    """Split an identifier into words: `PartsDontCover` -> parts, dont, cover.

    Tokenised rather than substring-matched so `partial`, `party` and `department` are not
    false positives — the rule is about the *word*, not the letters.
    """
    pieces = re.split(r"[_\W]+", re.sub(r"(?<!^)(?=[A-Z])", "_", identifier))
    return {p.lower() for p in pieces if p}


def _identifiers(source: str):
    """Every name a Python file defines or binds: classes, functions, parameters,
    assignments. Docstrings and comments are prose and are out of scope — the glossary
    allows retired words in prose when quoting the frozen plan."""
    for pattern in (
        r"^\s*(?:class|def)\s+(\w+)",           # definitions
        r"^\s*(\w+)\s*(?::[^=\n]+)?=[^=]",      # assignments and annotated assignments
        r"\bfor\s+(\w+)\s+in\b",                # loop variables
    ):
        for match in re.finditer(pattern, source, re.MULTILINE):
            yield match.group(1)
    for signature in re.finditer(r"def\s+\w+\s*\(([^)]*)\)", source, re.DOTALL):
        for param in signature.group(1).split(","):
            name = param.split(":")[0].split("=")[0].strip().lstrip("*")
            if name.isidentifier():
                yield name


def _violations() -> list[str]:
    banned, allowed, found = _banned(), _exceptions(), []
    for directory in SCANNED:
        for path in sorted((ROOT / directory).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            source = path.read_text(encoding="utf-8")
            for identifier in _identifiers(source):
                hits = {
                    word for word in banned
                    if word in _tokens(identifier) or f"{word}s" in _tokens(identifier)
                }
                if hits and f"{rel}:{identifier}" not in allowed:
                    found.append(f"{rel}:{identifier} contains {', '.join(sorted(hits))}")
    return sorted(set(found))


def test_no_identifier_uses_a_retired_word():
    """The rule the glossary states, mechanically applied.

    When this fails, the fix is to rename — not to add an exception. An exception is for a
    word that is genuinely a *quotation* of the read-only frozen plan, and it costs a
    recorded reason in `GLOSSARY.md` that the owner sees.
    """
    violations = _violations()
    assert not violations, (
        "retired vocabulary in identifiers (GLOSSARY.md is binding):\n  "
        + "\n  ".join(violations)
        + "\n\nRename them. If a name is genuinely quoting the read-only frozen plan, add it "
          "to the vocabulary-exceptions block in GLOSSARY.md with a reason."
    )


def test_the_check_can_actually_fail():
    """A check that cannot fail is F23's disease — it runs, passes, and means nothing.

    This is the test the vocabulary check itself would have needed to be trustworthy on
    day one, so it is written on day one.
    """
    assert "parts" in _tokens("PartsDontCover")
    assert "part" not in _tokens("partial_state")     # not a substring match
    assert "part" not in _tokens("third_party")
    assert "stage" in _tokens("stage_gate")
    assert "session" in _tokens("session_id")
    assert _banned(), "the banned list parsed empty"


def test_every_exception_carries_a_reason():
    """D8 and requirements:79's shape: the accounting can be changed, but not silently.
    An exception without a reason is a deny-list entry nobody has to justify."""
    text = GLOSSARY.read_text(encoding="utf-8")
    block = re.search(r"```vocabulary-exceptions\n(.*?)```", text, re.DOTALL)
    if block is None:
        pytest.skip("no exceptions recorded")
    for line in block.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            assert "—" in line, f"exception without a recorded reason: {line}"
