"""Versioned methodology content assets.

requirements:71 — the stage list, per-stage interview scripts, the engineer's mandate,
per-stage mechanical gate criteria and the gap-derivation rules ship as versioned
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
DEFAULT_REVISION = 2


class MethodologyUnavailable(Exception):
    """A content asset is missing or unreadable.

    Surfaced to callers as GuidanceUnreadable: never answer from partial methodology
    (uc_extensions:4).
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
    )
