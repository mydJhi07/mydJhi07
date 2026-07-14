"""Stage 5 — difficulty tuning and deduction-step counting.

Difficulty is expressed as generation parameters (how big the world is, how
wide the forensic window is, how well-witnessed the culprit's lie is, how
many red herrings muddy the waters) plus a measured statistic: the number of
independent deduction steps the solver needed to reach uniqueness.
"""
from __future__ import annotations

from dataclasses import dataclass

from deduction.engine.solver import SolveResult
from deduction.world.models import Difficulty, PublicCaseFacts


@dataclass(frozen=True)
class DifficultyConfig:
    suspects: int
    rooms: int
    slots: int
    window_size: int         # width of the forensic time-of-death window
    min_lie_witnesses: int   # innocents actually present in the room the culprit claims
    records: int             # hard corroborating records handed to the player
    red_herrings: int        # suspicious-but-innocent physical clues
    innocent_motives: int    # innocents who also have a motive (>= 1 always)


CONFIGS: dict[Difficulty, DifficultyConfig] = {
    Difficulty.EASY: DifficultyConfig(
        suspects=5, rooms=5, slots=5, window_size=1,
        min_lie_witnesses=2, records=3, red_herrings=1, innocent_motives=1,
    ),
    Difficulty.MEDIUM: DifficultyConfig(
        suspects=6, rooms=6, slots=6, window_size=2,
        min_lie_witnesses=1, records=2, red_herrings=2, innocent_motives=2,
    ),
    Difficulty.HARD: DifficultyConfig(
        suspects=8, rooms=7, slots=7, window_size=3,
        min_lie_witnesses=1, records=1, red_herrings=4, innocent_motives=3,
    ),
}


def build_deduction_chain(facts: PublicCaseFacts, result: SolveResult) -> list[str]:
    """The solver's own reasoning, one step per line, ending in the answer.

    Built purely from the solve result — the same eliminations that proved
    uniqueness — so the explanation shown to the player is exactly the
    logic that makes the case solvable, never a post-hoc rationalization.
    """
    window_labels = [facts.slots[slot].label for slot in result.window]
    chain = [
        f"{facts.victim_name}'s body lay in the {result.murder_room}; the "
        f"coroner puts the moment of death at "
        f"{' or '.join(window_labels)}. The killer was alone with the "
        f"victim there, and lied about where they were at that hour. "
        f"Everyone else told the truth."
    ]
    culprit = result.solution
    for suspect in facts.suspect_names:
        if suspect == culprit:
            continue
        reasons: list[str] = []
        for slot in result.window:
            contradiction = result.eliminations[(suspect, slot)]
            prefix = (f"Could {suspect} have struck at "
                      f"{facts.slots[slot].label}? No — ")
            reasons.append(prefix + contradiction.text)
        chain.append(f"Consider {suspect}. " + " ".join(dict.fromkeys(reasons)))
    if culprit is not None:
        slots_ok = result.consistent[culprit]
        chain.append(
            f"That leaves {culprit} — and only {culprit}. Their account of "
            f"{facts.slots[slots_ok[0]].label} collapses under the other "
            f"testimony, and no clue can place them anywhere but the "
            f"{result.murder_room} with {facts.victim_name}. "
            f"{culprit} is the killer."
        )
    return chain


def count_deduction_steps(eliminations: dict) -> int:
    """Number of independent deduction steps the solver used.

    Each eliminated (suspect, slot) hypothesis required citing at least one
    contradiction; distinct contradictions are distinct steps.  This is the
    measured difficulty of a case.
    """
    distinct = {
        (contradiction.kind, contradiction.people, contradiction.slots)
        for contradiction in eliminations.values()
    }
    return len(distinct)
