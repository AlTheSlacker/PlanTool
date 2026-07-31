"""Versioned methodology content assets.

requirements:71 — the stage list, per-stage interview scripts, the engineer's mandate,
per-stage mechanical gate criteria and the gap-derivation rules ship as versioned
content assets carrying a content-revision stamp, with an update path from one revision
to the next.

**`stage` is the interview's ordered step**, and it is the word the assets are keyed by
again from revision 4 (v3 change 1). It was `package` in revisions 3 and 3's manifest,
which collided with the *declared build grouping* of the same name — one word for two
things, and the grouping is the one that died.

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
DEFAULT_REVISION = 4

#: The oldest revision this loader will load. Earlier revisions are retained on disk as
#: frozen provenance and are deliberately not loadable.
#:
#: rev 2 is the PlanTool v1 methodology vendored verbatim (decisions:61, the answer to the
#: findings:4 red-team finding) — both the red-team artifact and the source text rev 3 was
#: derived from. Its scripts name v1's retired tool surface, so a plan cannot be authored
#: under it. It is kept byte-faithful on purpose and must never be edited.
#:
#: **rev 3 joined it on 2026-07-31**, for the same class of reason and by the same rule.
#: It is keyed by `packages:`, and this loader reads `stages:` again from revision 4; its
#: stage-6 script also names three tools that no longer exist, so serving it would raise
#: `UnreachableCall` at the door. Teaching the loader both spellings would be two
#: vocabularies live at once, which is the defect v3 change 1 exists to remove. The refusal
#: is honest and typed instead: `RevisionNotLoadable` says the content is intact and
#: deliberately not loaded.
#:
#: So requirements:71's revision-migration path ("migrate a plan from one revision to the
#: next") is forward-only: rev 4 is the earliest loadable baseline and there is nothing
#: loadable behind it. This is the owner's decision of 2026-07-23 — option (b) of the
#: rev-2-unloadable fork: declare the provenance frozen and make the refusal honest.
#: See DEFECTS.md F43.
EARLIEST_LOADABLE_REVISION = 4


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
class Stage:
    number: int
    name: str
    mode: str  # elicit | synthesize | verify
    script_file: str
    tables: tuple[str, ...]

    @property
    def is_elicit(self) -> bool:
        """Elicit stages carry mandatory divergence rounds (requirements:16)."""
        return self.mode == "elicit"


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    priority: int
    stage: int | None
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
    stage: int
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
    stages: tuple[Stage, ...]
    rules: tuple[Rule, ...]
    criteria: tuple[Criterion, ...]
    auxiliary: dict[str, str]
    #: Child row type -> mandatory owning parent row type. See the manifest's own
    #: comment: these names belong to the methodology, never to the engine.
    containment: dict[str, str]

    def criteria_for(self, stage: int) -> tuple[Criterion, ...]:
        """This stage's criteria in file order — requirements:46's determinism starts
        here."""
        return tuple(c for c in self.criteria if c.stage == stage)

    def stage(self, number: int) -> Stage:
        for stage in self.stages:
            if stage.number == number:
                return stage
        raise KeyError(number)

    @property
    def stage_range(self) -> tuple[int, int]:
        numbers = [s.number for s in self.stages]
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

    stages = tuple(
        Stage(
            number=entry["number"],
            name=entry["name"],
            mode=entry["mode"],
            script_file=entry["script"],
            tables=tuple(entry.get("tables") or ()),
        )
        for entry in manifest["stages"]
    )
    rules = tuple(
        Rule(
            id=entry["id"],
            priority=entry["priority"],
            stage=entry.get("stage"),
            type=entry["type"],
            ask=" ".join(entry["ask"].split()),
            spec=entry,
        )
        for entry in rules_doc["rules"]
    )
    criteria = tuple(
        Criterion(
            id=entry["id"],
            stage=block["stage"],
            type=entry["type"],
            problem=" ".join(entry["problem"].split()),
            fix=" ".join(entry["fix"].split()),
            cross_check=bool(entry.get("cross_check")),
            spec=entry,
        )
        for block in criteria_doc["stages"]
        for entry in block["criteria"]
    )
    return Methodology(
        revision=manifest["revision"],
        revision_stamp=manifest["revision_stamp"],
        vendored_from=manifest["vendored_from"],
        root=root,
        mandate_file=manifest["mandate"],
        stages=stages,
        rules=rules,
        criteria=criteria,
        auxiliary=manifest.get("auxiliary") or {},
        containment=dict(manifest.get("containment") or {}),
    )
