"""Core dataclasses for the Deduction world model.

Three layers communicate exclusively through these structures:

* the generator (``world.generator``) produces a :class:`Case`;
* the solver (``engine.solver``) receives only :class:`PublicCaseFacts`
  plus the list of :class:`Clue` objects — never the ground truth;
* the game/UI layer reads both, but only reveals ground truth on accusation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ---------------------------------------------------------------------------
# World primitives
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Room:
    """A location in the manor.  ``neighbors`` are names of adjacent rooms."""

    name: str
    description: str
    neighbors: tuple[str, ...]


@dataclass(frozen=True)
class TimeSlot:
    """A discrete step of the evening's timeline."""

    index: int
    label: str  # e.g. "7:00 PM"


@dataclass(frozen=True)
class Suspect:
    name: str
    occupation: str
    trait: str                    # e.g. "chain-smokes thin cigars"
    relationship: str             # relationship to the victim
    motive: Optional[str]         # None => no apparent motive
    demeanor: str                 # flavor: how they act when questioned


# ---------------------------------------------------------------------------
# Statements & clues
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Statement:
    """One suspect's account of one time slot.

    ``seen`` is an *exhaustive* list: the speaker claims that exactly these
    other people (suspects and/or the victim) were in ``room`` with them
    during the slot — anyone not listed was, per the speaker, absent.
    """

    speaker: str
    slot: int
    room: str
    seen: frozenset[str]


class Clue:
    """Marker base class for everything the player (and solver) can learn."""


@dataclass(frozen=True)
class TestimonyClue(Clue):
    """A statement obtained by interrogating a suspect."""

    statement: Statement


@dataclass(frozen=True)
class BodyClue(Clue):
    """Where the victim's body was discovered (== the murder room)."""

    victim: str
    room: str
    discovered_text: str


@dataclass(frozen=True)
class ForensicClue(Clue):
    """The coroner narrows the time of death to a window of slot indices."""

    window: tuple[int, ...]  # sorted, contiguous slot indices
    report_text: str


@dataclass(frozen=True)
class RecordClue(Clue):
    """A hard, trustworthy record: ``person`` was in ``room`` at ``slot``.

    Derived from ground truth, therefore always true.
    """

    person: str
    slot: int
    room: str
    source_text: str


@dataclass(frozen=True)
class PhysicalClue(Clue):
    """Soft physical evidence found by examining a room.

    Soft clues carry suspicion and narrative, never logical weight — the
    solver ignores them, so they can safely mislead intuition.
    """

    room_found: str
    description: str
    linked_suspect: Optional[str]   # whose trait/item it evokes, if any
    is_weapon: bool = False


@dataclass(frozen=True)
class MotiveClue(Clue):
    """A letter/ledger/rumor revealing a suspect's possible motive."""

    suspect: str
    room_found: str
    description: str


# ---------------------------------------------------------------------------
# Public facts vs. ground truth
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PublicCaseFacts:
    """Everything that is common knowledge and NOT part of the hidden truth:
    the map, the timeline, who is present, and who died.

    This — plus the clue list — is the solver's entire input.
    """

    rooms: tuple[Room, ...]
    slots: tuple[TimeSlot, ...]
    suspect_names: tuple[str, ...]
    victim_name: str

    def adjacency(self) -> dict[str, frozenset[str]]:
        """Reachability per step: a character may stay put or move to an
        adjacent room between consecutive slots."""
        return {
            room.name: frozenset(room.neighbors) | {room.name}
            for room in self.rooms
        }

    def room_names(self) -> tuple[str, ...]:
        return tuple(room.name for room in self.rooms)


@dataclass
class Case:
    """A fully generated case: public facts, clues, and hidden ground truth."""

    seed: int
    difficulty: Difficulty
    facts: PublicCaseFacts
    clues: list[Clue]

    # ---- ground truth (never shown to the solver) ----
    suspects: tuple[Suspect, ...]
    victim: Suspect
    culprit: str
    murder_room: str
    murder_slot: int
    forensic_window: tuple[int, ...]
    true_paths: dict[str, list[str]] = field(default_factory=dict)  # name -> room per slot
    lie: Optional[Statement] = None          # the culprit's false statement
    true_murder_slot_room: str = ""          # culprit's real room at murder slot (== murder_room)

    def suspect_by_name(self, name: str) -> Suspect:
        for suspect in self.suspects:
            if suspect.name == name:
                return suspect
        raise KeyError(name)

    def testimony_of(self, name: str) -> list[Statement]:
        return sorted(
            (clue.statement for clue in self.clues
             if isinstance(clue, TestimonyClue) and clue.statement.speaker == name),
            key=lambda statement: statement.slot,
        )
