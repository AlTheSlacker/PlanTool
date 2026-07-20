"""guidance (components:4).

Serves the engineer's mandate and per-stage interview scripts, including the mandatory
divergence rounds for elicit stages.

Contracts: contracts:17 get_mandate, contracts:65 get_stage_script.

This component holds no methodology of its own — it serves the vendored content assets
(decisions:61). If it ever starts generating guidance, findings:4 has come back.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.errors import PlanToolError
from engine.methodology import Methodology, MethodologyUnavailable, load


class GuidanceUnreadable(PlanToolError):
    """contracts:17/65 — mandate or script content failed integrity.

    uc_extensions:4 — the UC2 integrity path: never answer from partial state. A
    truncated mandate is worse than no mandate, because the missing clause is invisible.
    """


class UnknownStage(PlanToolError):
    """contracts:65 — stage outside the defined set; names the valid range."""


@dataclass(frozen=True, slots=True)
class StageScript:
    stage: int
    name: str
    mode: str
    text: str
    revision_stamp: str
    divergence_required: bool
    tables: tuple[str, ...]


class Guidance:
    def __init__(self, revision: int | None = None):
        try:
            self.methodology: Methodology = (
                load() if revision is None else load(revision)
            )
        except MethodologyUnavailable as exc:
            raise GuidanceUnreadable(str(exc)) from exc

    @property
    def revision_stamp(self) -> str:
        return self.methodology.revision_stamp

    # --- contracts:17 ---

    def get_mandate(self) -> str:
        """The engineer's mandate (requirements:10)."""
        try:
            return self.methodology.read(self.methodology.mandate_file)
        except MethodologyUnavailable as exc:
            raise GuidanceUnreadable(
                "the engineer's mandate could not be read; refusing to answer from "
                "partial methodology",
                cause=str(exc),
            ) from exc

    # --- contracts:65 ---

    def get_stage_script(self, stage: int) -> StageScript:
        """The interview script for a stage.

        For elicit stages this includes the mandatory divergence rounds — context-free
        questions, negative-space probes, owner-generated candidates solicited *before*
        agent-authored drafts (requirements:16). That ordering is the countermeasure to
        the friction recorded in decisions:36, where the owner "did not feel pushed that
        hard" and every use case ended up agent-authored.
        """
        low, high = self.methodology.stage_range
        try:
            entry = self.methodology.stage(stage)
        except KeyError as exc:
            raise UnknownStage(
                "no such stage", stage=stage, valid_range=f"{low}-{high}"
            ) from exc

        try:
            text = self.methodology.read(entry.script_file)
        except MethodologyUnavailable as exc:
            raise GuidanceUnreadable(
                "the stage script could not be read; refusing to answer from partial "
                "methodology",
                stage=stage,
                cause=str(exc),
            ) from exc

        return StageScript(
            stage=entry.number,
            name=entry.name,
            mode=entry.mode,
            text=text,
            revision_stamp=self.methodology.revision_stamp,
            divergence_required=entry.is_elicit,
            tables=entry.tables,
        )

    def get_auxiliary(self, name: str) -> str:
        """Supplementary scripts, e.g. the red-team brief for use_cases:8."""
        filename = self.methodology.auxiliary.get(name)
        if filename is None:
            raise UnknownStage(
                "no such auxiliary script",
                name=name,
                available=sorted(self.methodology.auxiliary),
            )
        try:
            return self.methodology.read(filename)
        except MethodologyUnavailable as exc:
            raise GuidanceUnreadable(str(exc)) from exc
