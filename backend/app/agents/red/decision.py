"""Provider-neutral choice of a test from runner-supplied, observed options.

Future model providers receive only these options. The runner validates every returned
choice and the core HTTP adapter remains responsible for destination and credential
enforcement.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TestOption:
    endpoint: str
    path: str
    actor_ref: str
    resource_ref: str
    owner_ref: str
    owner_path: str


class DecisionProvider(Protocol):
    async def choose(self, options: tuple[TestOption, ...]) -> TestOption | None: ...


class DeterministicDecisionProvider:
    """Select the next observed cross-user pair in stable order."""

    async def choose(self, options: tuple[TestOption, ...]) -> TestOption | None:
        return sorted(options, key=lambda o: (o.endpoint, o.actor_ref, o.resource_ref))[0] if options else None
