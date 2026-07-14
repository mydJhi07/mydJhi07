"""Stage 4 — the independent deduction engine.

The solver receives ONLY :class:`PublicCaseFacts` and the clue list.  It
never imports the generator and never touches ground truth, so a unique
answer from the solver is a genuine guarantee of logical solvability.

Knowledge available to any player (and to the solver), stated as axioms:

* Every suspect gave a complete account: for each time slot, the room they
  were in and an *exhaustive* list of everyone else they saw there.
* Innocent suspects tell the truth in every statement.
* The culprit's account is true everywhere except the murder slot, where
  the claimed location is false.
* The murder happened in the room where the body was found, during one of
  the forensic-window slots, with the culprit *alone* with the victim.
* Movement is constrained by the manor's doors: between consecutive slots a
  character stays put or moves to an adjacent room.  The victim's body does
  not move after the murder.
* Records (logbooks, photographs) are trustworthy facts.

The case is modeled as a constraint satisfaction problem over the variable
``culprit`` (and the auxiliary ``murder_slot``): a hypothesis (S, t) is
eliminated when the axioms above become mutually contradictory under it.
The solver returns every suspect consistent with the clues; the generator
only accepts cases where that set is exactly one suspect.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from deduction.world.models import (
    BodyClue,
    Clue,
    ForensicClue,
    PublicCaseFacts,
    RecordClue,
    Statement,
    TestimonyClue,
)


@dataclass(frozen=True)
class Contradiction:
    """Why a (suspect, slot) hypothesis is impossible."""

    kind: str                       # machine-readable category
    text: str                       # human-readable deduction sentence
    people: tuple[str, ...] = ()
    slots: tuple[int, ...] = ()


@dataclass
class SolveResult:
    culprits: frozenset[str]
    # every hypothesis that survived: culprit -> feasible murder slots
    consistent: dict[str, list[int]]
    # every hypothesis that died: (suspect, slot) -> why
    eliminations: dict[tuple[str, int], Contradiction]
    murder_room: str
    window: tuple[int, ...]

    @property
    def unique(self) -> bool:
        return len(self.culprits) == 1

    @property
    def solution(self) -> Optional[str]:
        return next(iter(self.culprits)) if self.unique else None


@dataclass
class _CluePack:
    statements: dict[tuple[str, int], Statement] = field(default_factory=dict)
    records: list[RecordClue] = field(default_factory=list)
    body_room: str = ""
    victim: str = ""
    window: tuple[int, ...] = ()


def _unpack(facts: PublicCaseFacts, clues: list[Clue]) -> _CluePack:
    pack = _CluePack(victim=facts.victim_name)
    for clue in clues:
        if isinstance(clue, TestimonyClue):
            statement = clue.statement
            key = (statement.speaker, statement.slot)
            if key in pack.statements:
                raise ValueError(f"duplicate statement for {key}")
            pack.statements[key] = statement
        elif isinstance(clue, BodyClue):
            pack.body_room = clue.room
        elif isinstance(clue, ForensicClue):
            pack.window = clue.window
        elif isinstance(clue, RecordClue):
            pack.records.append(clue)
        # soft clues (physical evidence, motives) carry no logical weight
    slot_count = len(facts.slots)
    for name in facts.suspect_names:
        for slot in range(slot_count):
            if (name, slot) not in pack.statements:
                raise ValueError(f"missing statement: {name} at slot {slot}")
    if not pack.body_room or not pack.window:
        raise ValueError("clue set lacks the body location or forensic report")
    return pack


def solve(facts: PublicCaseFacts, clues: list[Clue]) -> SolveResult:
    """Return every suspect logically consistent with the clue set."""
    pack = _unpack(facts, clues)
    consistent: dict[str, list[int]] = {}
    eliminations: dict[tuple[str, int], Contradiction] = {}
    for suspect in facts.suspect_names:
        for slot in pack.window:
            contradiction = _check_hypothesis(facts, pack, suspect, slot)
            if contradiction is None:
                consistent.setdefault(suspect, []).append(slot)
            else:
                eliminations[(suspect, slot)] = contradiction
    return SolveResult(
        culprits=frozenset(consistent),
        consistent=consistent,
        eliminations=eliminations,
        murder_room=pack.body_room,
        window=pack.window,
    )


# ---------------------------------------------------------------------------
# Hypothesis checking
# ---------------------------------------------------------------------------

def _check_hypothesis(facts: PublicCaseFacts, pack: _CluePack,
                      culprit: str, murder_slot: int) -> Optional[Contradiction]:
    """Assume ``culprit`` killed the victim at ``murder_slot``.  Under the
    axioms, every statement is then true except the culprit's statement for
    that slot, whose location claim is false; the culprit was actually in
    the murder room, alone with the victim.  Return the first contradiction
    this produces, or None if the hypothesis is consistent."""
    label = lambda slot: facts.slots[slot].label  # noqa: E731
    body_room = pack.body_room
    slot_count = len(facts.slots)
    reach = facts.adjacency()

    lie = pack.statements[(culprit, murder_slot)]
    # Axiom: the culprit's murder-slot location claim is FALSE.  A suspect
    # who openly claims the murder room cannot be lying about being
    # elsewhere — as the culprit they would be telling the truth.
    if lie.room == body_room:
        return Contradiction(
            kind="truthful-about-scene",
            text=(f"{culprit} openly places themself in the {body_room} at "
                  f"{label(murder_slot)}; the killer lied about that hour, so "
                  f"this account rules the hypothesis out."),
            people=(culprit,), slots=(murder_slot,),
        )

    # Pin every character's position implied by deemed-true statements.
    position: dict[tuple[str, int], str] = {}
    for (speaker, slot), statement in pack.statements.items():
        if speaker == culprit and slot == murder_slot:
            continue  # the lie: wholly unreliable
        position[(speaker, slot)] = statement.room
    position[(culprit, murder_slot)] = body_room

    # Trustworthy records must agree with the (hypothesized) positions.
    for record in pack.records:
        pinned = position.get((record.person, record.slot))
        if pinned is not None and pinned != record.room:
            return Contradiction(
                kind="record-conflict",
                text=(f"A record places {record.person} in the {record.room} "
                      f"at {label(record.slot)}, which cannot be squared with "
                      f"{record.person} being in the {pinned} then."),
                people=(record.person,), slots=(record.slot,),
            )

    # Movement must respect the manor's doors.
    for name in facts.suspect_names:
        for slot in range(slot_count - 1):
            here, there = position[(name, slot)], position[(name, slot + 1)]
            if there not in reach[here]:
                return Contradiction(
                    kind="impossible-movement",
                    text=(f"{name} would have had to get from the {here} to "
                          f"the {there} between {label(slot)} and "
                          f"{label(slot + 1)}, but no door connects them."),
                    people=(name,), slots=(slot, slot + 1),
                )

    # The culprit must be ALONE with the victim.
    for name in facts.suspect_names:
        if name != culprit and position[(name, murder_slot)] == body_room:
            return Contradiction(
                kind="not-alone",
                text=(f"{name}'s account places them in the {body_room} at "
                      f"{label(murder_slot)}, so {culprit} could not have "
                      f"been alone there with {pack.victim}."),
                people=(culprit, name), slots=(murder_slot,),
            )

    # Exhaustive sightings: every deemed-true statement must agree with
    # every pinned position — X saw Y iff Y was in X's room.
    for (speaker, slot), statement in sorted(pack.statements.items()):
        if speaker == culprit and slot == murder_slot:
            continue
        for other in facts.suspect_names:
            if other == speaker:
                continue
            other_room = position[(other, slot)]
            listed = other in statement.seen
            if listed and other_room != statement.room:
                return Contradiction(
                    kind="sighting-conflict",
                    text=(f"{speaker} states they saw {other} in the "
                          f"{statement.room} at {label(slot)}, yet {other} "
                          f"would have been in the {other_room}."),
                    people=(speaker, other), slots=(slot,),
                )
            if not listed and other_room == statement.room:
                return Contradiction(
                    kind="sighting-conflict",
                    text=(f"{other} would have been in the {statement.room} "
                          f"at {label(slot)}, yet {speaker}, who was there, "
                          f"is adamant {other} was not."),
                    people=(speaker, other), slots=(slot,),
                )

    # Finally, the victim: dead in the murder room from the murder slot on,
    # alive and free to move before — but pinned wherever truthful witnesses
    # saw them, absent wherever truthful witnesses did not, and always
    # respecting the doors.
    room_names = set(facts.room_names())
    domains: list[set[str]] = []
    for slot in range(slot_count):
        domain = {body_room} if slot >= murder_slot else set(room_names)
        domains.append(domain)
    for record in pack.records:
        if record.person == pack.victim:
            domains[record.slot] &= {record.room}
    for (speaker, slot), statement in sorted(pack.statements.items()):
        if speaker == culprit and slot == murder_slot:
            continue
        if pack.victim in statement.seen:
            domains[slot] &= {statement.room}
        else:
            domains[slot].discard(statement.room)
    for slot, domain in enumerate(domains):
        if not domain:
            return Contradiction(
                kind="victim-placement",
                text=(f"The witnesses' accounts leave {pack.victim} nowhere "
                      f"to be at {label(slot)} if the murder happened in the "
                      f"{body_room} at {label(murder_slot)}."),
                people=(pack.victim,), slots=(slot,),
            )
    feasible = set(domains[0])
    for slot in range(1, slot_count):
        feasible = {room for room in domains[slot]
                    if any(room in reach[prev] for prev in feasible)}
        if not feasible:
            return Contradiction(
                kind="victim-placement",
                text=(f"{pack.victim} could not have moved from where the "
                      f"witnesses place them to the {body_room} in time for "
                      f"a murder at {label(murder_slot)}."),
                people=(pack.victim,), slots=(slot,),
            )
    return None


# ---------------------------------------------------------------------------
# Pairwise statement conflicts (shared with the notebook UI)
# ---------------------------------------------------------------------------

def statements_conflict(first: Statement, second: Statement) -> bool:
    """True when no possible world satisfies both statements.

    Because ``seen`` lists are exhaustive, two accounts of the same slot
    conflict when they disagree about who shared a room with whom.
    """
    if first.slot != second.slot or first.speaker == second.speaker:
        return False
    if first.room == second.room:
        if second.speaker not in first.seen or first.speaker not in second.seen:
            return True
        return (first.seen - {second.speaker}) != (second.seen - {first.speaker})
    if second.speaker in first.seen or first.speaker in second.seen:
        return True
    return bool(first.seen & second.seen)  # nobody can be in two rooms at once
