"""Versioned methodology content assets.

requirements:71 — the package list, per-package interview scripts, the engineer's mandate,
per-package mechanical gate criteria and the gap-derivation rules ship as versioned
content assets carrying a content-revision stamp, with an update path from one revision
to the next.

decisions:61 — the successor *vendors* the PlanTool rev-2 methodology rather than
inventing one at build time. findings:4 is the red-team finding that forced this: the
methodology is the product's core IP and its hardest design problem, and an executor
made to invent it mid-build is the exact milestone-time re-planning failure the tool
exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ASSETS = Path(__file__).parent
DEFAULT_REVISION = 3

#: The oldest revision this loader will load. Earlier revisions are retained on disk as
#: frozen provenance and are deliberately not loadable.
#:
#: rev 2 is the PlanTool v1 methodology vendored verbatim (decisions:61, the answer to the
#: findings:4 red-team finding) — both the red-team artifact and the source text rev 3 was
#: derived from. It is written in v1's vocabulary (`stages:`, not the `packages:` this
#: loader reads) and its scripts name v1's retired tool surface, so a plan cannot be
#: authored under it through the v2 surface. It is kept byte-faithful on purpose and must
#: never be edited.
#:
#: So requirements:71's revision-migration path ("migrate a plan from one revision to the
#: next") is forward-only: rev 3 is the earliest loadable baseline and there is nothing
#: loadable behind it. This is the owner's decision of 2026-07-23 — option (b) of the
#: rev-2-unloadable fork: declare the provenance frozen and make the refusal honest,
#: rather than teach the loader to read `stages:` into a revision nothing can author under.
#: See DEFECTS.md F43.
EARLIEST_LOADABLE_REVISION = 3


class MethodologyUnavailable(Exception):
    """A content asset is missing or unreadable.

    Surfaced to callers as GuidanceUnreadable: never answer from partial methodology
    (uc_extensions:4).
    """


class RevisionNotLoadable(MethodologyUnavailable):
    """A revision below EARLIEST_LOADABLE_REVISION was requested (DEFECTS.md F43).

    Not an integrity failure — the content is intact and on disk. The revision is retained
    as frozen provenance and intentionally not loaded. A distinct type because the truth
    matters here: a raw ``KeyError`` implied a bug, a plain "could not be read" would imply
    corruption, and this says what is actually so — the refusal is deliberate. A migration
    caller can catch this specifically to know it has reached the frozen baseline rather
    than a broken asset.
    """


@dataclass(frozen=True, slots=True)
class Package:
    number: int
    name: str
    mode: str  # elicit | synthesize | verify
    script_file: str
    tables: tuple[str, ...]

    @property
    def is_elicit(self) -> bool:
        """Elicit packages carry mandatory divergence rounds (requirements:16)."""
        return self.mode == "elicit"


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    priority: int
    package: int | None
    type: str
    ask: str
    spec: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Criterion:
    """One mechanical gate check (requirements:20).

    `problem` and `fix` are templates: a hole formats them, so the wording that reaches
    the agent is methodology content rather than engine code.
    """

    id: str
    package: int
    type: str
    problem: str
    fix: str
    cross_check: bool
    spec: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Methodology:
    revision: int
    revision_stamp: str
    vendored_from: str
    root: Path
    mandate_file: str
    packages: tuple[Package, ...]
    rules: tuple[Rule, ...]
    criteria: tuple[Criterion, ...]
    auxiliary: dict[str, str]
    #: Child row type -> mandatory owning parent row type. See the manifest's own
    #: comment: these names belong to the methodology, never to the engine.
    containment: dict[str, str]

    def criteria_for(self, package: int) -> tuple[Criterion, ...]:
        """This package's criteria in file order — requirements:46's determinism starts
        here."""
        return tuple(c for c in self.criteria if c.package == package)

    def package(self, number: int) -> Package:
        for package in self.packages:
            if package.number == number:
                return package
        raise KeyError(number)

    @property
    def package_range(self) -> tuple[int, int]:
        numbers = [s.number for s in self.packages]
        return min(numbers), max(numbers)

    def read(self, filename: str) -> str:
        path = self.root / filename
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise MethodologyUnavailable(
                f"methodology asset {filename!r} could not be read"
            ) from exc
        if not text.strip():
            raise MethodologyUnavailable(f"methodology asset {filename!r} is empty")
        return text


@lru_cache(maxsize=4)
def load(revision: int = DEFAULT_REVISION) -> Methodology:
    if revision < EARLIEST_LOADABLE_REVISION:
        raise RevisionNotLoadable(
            f"methodology revision {revision} precedes the earliest loadable baseline "
            f"(revision {EARLIEST_LOADABLE_REVISION}); earlier revisions are retained as "
            f"frozen provenance and are not loaded — requirements:71's migration path is "
            f"forward-only from there"
        )
    root = ASSETS / f"rev{revision}"
    manifest_path = root / "manifest.yaml"
    rules_path = root / "gap_rules.yaml"
    criteria_path = root / "gate_criteria.yaml"
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        rules_doc = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
        criteria_doc = yaml.safe_load(criteria_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MethodologyUnavailable(
            f"methodology revision {revision} is not installed"
        ) from exc
    except yaml.YAMLError as exc:
        raise MethodologyUnavailable(
            f"methodology revision {revision} is malformed"
        ) from exc

    packages = tuple(
        Package(
            number=entry["number"],
            name=entry["name"],
            mode=entry["mode"],
            script_file=entry["script"],
            tables=tuple(entry.get("tables") or ()),
        )
        for entry in manifest["packages"]
    )
    rules = tuple(
        Rule(
            id=entry["id"],
            priority=entry["priority"],
            package=entry.get("package"),
            type=entry["type"],
            ask=" ".join(entry["ask"].split()),
            spec=entry,
        )
        for entry in rules_doc["rules"]
    )
    criteria = tuple(
        Criterion(
            id=entry["id"],
            package=block["package"],
            type=entry["type"],
            problem=" ".join(entry["problem"].split()),
            fix=" ".join(entry["fix"].split()),
            cross_check=bool(entry.get("cross_check")),
            spec=entry,
        )
        for block in criteria_doc["packages"]
        for entry in block["criteria"]
    )
    return Methodology(
        revision=manifest["revision"],
        revision_stamp=manifest["revision_stamp"],
        vendored_from=manifest["vendored_from"],
        root=root,
        mandate_file=manifest["mandate"],
        packages=packages,
        rules=rules,
        criteria=criteria,
        auxiliary=manifest.get("auxiliary") or {},
        containment=dict(manifest.get("containment") or {}),
    )
