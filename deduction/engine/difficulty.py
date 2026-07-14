"""Stage 5 — difficulty tuning and deduction-step counting.

Difficulty is expressed as generation parameters (how big the world is, how
wide the forensic window is, how well-witnessed the culprit's lie is, how
many red herrings muddy the waters) plus a measured statistic: the number of
independent deduction steps the solver needed to reach uniqueness.
"""
from __future__ import annotations

from dataclasses import dataclass

from deduction.world.models import Difficulty


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
