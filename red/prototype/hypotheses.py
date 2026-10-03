"""Evidence requirements for agent assessments, independent of mission verdicts.

The RedBoard lock protects this ledger and its evidence/task inputs together. The
ledger validates structure and provenance; agents interpret the response content.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from .domain import Evidence, HypothesisStatus, HypothesisUpdate, Role


def candidate_hash(key: str) -> str:
    import hashlib

    return hashlib.sha256(key.strip().casefold().encode()).hexdigest()


@dataclass
class CandidateHypothesis:
    hypothesis_id: str
    candidate_key: str
    statement: str
    expected_result: str
    session_id: str
    supporting_evidence_refs: list[str]
    status: HypothesisStatus = "inconclusive"
    revision: int = 1
    reopened_at_sequence: int = 0
    baseline_evidence_ref: str | None = None
    comparison_evidence_ref: str | None = None
    changed_condition: str = ""
    assessment: str = ""
    assessment_source: str = "agent_assessed"
    visibility: str = "red_private"
    history: list[dict[str, Any]] = field(default_factory=list)


class HypothesisLedger:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._candidates: dict[str, CandidateHypothesis] = {}

    def get(self, candidate_key: str) -> dict[str, Any] | None:
        item = self._candidates.get(candidate_hash(candidate_key))
        return asdict(item) if item else None

    def records(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self._candidates.values()]

    def _evidence(self, refs: list[str], evidence: Mapping[str, Evidence]) -> list[Evidence]:
        if any(ref not in evidence or evidence[ref].session_id != self.session_id for ref in refs):
            raise ValueError("hypothesis requires evidence from this run")
        return [evidence[ref] for ref in refs]

    @staticmethod
    def _usable(observation: Evidence, *, baseline: bool = False) -> bool:
        status = observation.status
        if (observation.failure_kind or status is None or status in (408, 429)
                or not (200 <= status < 300 or 400 <= status < 500)):
            return False
        if baseline and not 200 <= status < 300:
            return False
        # A failed login never establishes rejection or successful containment.
        if observation.capability == "start_account_session" and not 200 <= status < 300:
            return False
        return True

    def apply(
        self, update: HypothesisUpdate, *, evidence: Mapping[str, Evidence], role: Role,
        task_id: str, sequence: int,
    ) -> dict[str, Any]:
        key = candidate_hash(update.candidate_key)
        record = self._candidates.get(key)
        references = list(dict.fromkeys([
            *update.evidence_refs,
            *([update.baseline_evidence_ref] if update.baseline_evidence_ref else []),
            *([update.comparison_evidence_ref] if update.comparison_evidence_ref else []),
        ]))
        observations = self._evidence(references, evidence)
        if not update.assessment.strip():
            raise ValueError("hypothesis update requires a concise assessment")
        if update.operation == "create":
            if record is not None or update.expected_revision != 0:
                raise ValueError("candidate already exists; use its current revision")
            if not update.statement.strip() or not update.expected_result.strip() or not update.evidence_refs:
                raise ValueError("candidate requires a statement, expected result, and supporting evidence")
            if not any(ev.status is not None and not ev.failure_kind for ev in observations):
                raise ValueError("candidate requires an actual target observation")
            if update.status != "inconclusive" or update.baseline_evidence_ref or update.comparison_evidence_ref or update.changed_condition:
                raise ValueError("new candidates are unproven; assess a comparison separately")
            record = CandidateHypothesis(
                "hyp-" + uuid.uuid4().hex[:12], update.candidate_key.strip().casefold(),
                update.statement.strip(), update.expected_result.strip(), self.session_id,
                list(dict.fromkeys(update.evidence_refs)),
            )
            previous_status = None
        else:
            if record is None or update.expected_revision != record.revision:
                raise ValueError("hypothesis revision is stale or candidate is unknown")
            if ((update.statement.strip() and update.statement.strip() != record.statement)
                    or (update.expected_result.strip() and update.expected_result.strip() != record.expected_result)):
                raise ValueError("a changed prediction requires a separate candidate")
            previous_status = record.status
            if update.operation == "reopen":
                if record.status == "inconclusive":
                    raise ValueError("candidate is already inconclusive")
                if update.status != "inconclusive" or not update.evidence_refs:
                    raise ValueError("reopening requires contradictory observations and an inconclusive status")
                if update.baseline_evidence_ref or update.comparison_evidence_ref or update.changed_condition:
                    raise ValueError("reopening must precede the fresh comparison")
                if any(ev.sequence <= record.history[-1]["sequence"] for ev in observations):
                    raise ValueError("reopening requires observations newer than the last assessment")
            else:
                if role != "operator":
                    raise ValueError("only Operator may assess a candidate")
                if record.status != "inconclusive" and update.status != record.status:
                    raise ValueError("reopen a concluded candidate before reversing its assessment")
                if update.status != "inconclusive":
                    if not update.baseline_evidence_ref or not update.comparison_evidence_ref or not update.changed_condition.strip():
                        raise ValueError("conclusion requires a baseline, comparison, and one changed condition")
                    baseline = evidence[update.baseline_evidence_ref]
                    comparison = evidence[update.comparison_evidence_ref]
                    if not self._usable(baseline, baseline=True) or not self._usable(comparison):
                        raise ValueError("ambiguous observations must remain inconclusive")
                    if comparison.role != "operator" or baseline.sequence >= comparison.sequence:
                        raise ValueError("Operator must cite its later comparison against a distinct baseline")
                    if comparison.sequence <= record.history[0]["sequence"]:
                        raise ValueError("the expected result must be recorded before the comparison test")
                    if baseline.sequence <= record.reopened_at_sequence:
                        raise ValueError("reopened candidate requires a fresh baseline and comparison")
                    if record.comparison_evidence_ref and comparison.sequence <= evidence[record.comparison_evidence_ref].sequence:
                        raise ValueError("assessment requires a new comparison observation")

        # All validation precedes mutation, including optimistic revision checks.
        if update.operation == "create":
            self._candidates[key] = record
        else:
            record.revision += 1
        if update.operation == "reopen":
            record.reopened_at_sequence = sequence
        record.status = update.status
        record.assessment = update.assessment.strip()
        record.baseline_evidence_ref = update.baseline_evidence_ref
        record.comparison_evidence_ref = update.comparison_evidence_ref
        record.changed_condition = update.changed_condition.strip()
        record.supporting_evidence_refs = list(dict.fromkeys([*record.supporting_evidence_refs, *references]))
        record.history.append({
            "revision": record.revision, "sequence": sequence, "operation": update.operation,
            "from_status": previous_status, "status": record.status, "role": role, "task_id": task_id,
            "assessment": record.assessment, "evidence_refs": references,
            "baseline_evidence_ref": record.baseline_evidence_ref,
            "comparison_evidence_ref": record.comparison_evidence_ref,
            "changed_condition": record.changed_condition,
        })
        return asdict(record)
