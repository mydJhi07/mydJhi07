"""THE acceptance test: every generated case must be uniquely solvable.

Generates 10,000 cases spread across all difficulty tiers and asserts, for
every single one, that the independent solver — fed only public facts and
clues, never ground truth — returns exactly one consistent suspect, and
that this suspect is the ground-truth culprit.

Also asserts the structural invariants:
* no character ever occupies two rooms in the same time slot;
* every movement path respects location-graph adjacency;
* the culprit's lie is falsifiable by at least one other clue;
* at least one innocent suspect has a motive (motive is never a giveaway);
* the culprit was alone with the victim at the murder room/slot.

Override the case count with DEDUCTION_FUZZ_CASES (e.g. for a quick local
run); the default, and the definition of done, is the full 10,000.
"""
from __future__ import annotations

import os
import sys
import unittest

from deduction.engine.solver import solve, statements_conflict
from deduction.world.generator import generate_case
from deduction.world.models import (
    Case,
    Difficulty,
    RecordClue,
    TestimonyClue,
)

FUZZ_CASES = int(os.environ.get("DEDUCTION_FUZZ_CASES", "10000"))
TIERS = (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD)


def assert_case_invariants(case: Case) -> None:
    slot_count = len(case.facts.slots)
    reach = case.facts.adjacency()

    # Every character has exactly one room per slot (never two at once).
    everyone = set(case.facts.suspect_names) | {case.facts.victim_name}
    assert set(case.true_paths) == everyone
    for name, path in case.true_paths.items():
        assert len(path) == slot_count, f"{name} lacks a room for some slot"
        assert all(isinstance(room, str) and room for room in path)
    # ... and testimony never double-books a slot either.
    statement_keys = [
        (clue.statement.speaker, clue.statement.slot)
        for clue in case.clues if isinstance(clue, TestimonyClue)
    ]
    assert len(statement_keys) == len(set(statement_keys))
    assert len(statement_keys) == len(case.facts.suspect_names) * slot_count

    # Movement respects the location graph.
    for name, path in case.true_paths.items():
        for slot in range(slot_count - 1):
            assert path[slot + 1] in reach[path[slot]], (
                f"{name} teleported {path[slot]} -> {path[slot + 1]} "
                f"(seed={case.seed}, {case.difficulty.value})"
            )

    # The culprit was alone with the victim at the scene.
    assert case.true_paths[case.culprit][case.murder_slot] == case.murder_room
    assert case.true_paths[case.facts.victim_name][case.murder_slot] == case.murder_room
    for name in case.facts.suspect_names:
        if name != case.culprit:
            assert case.true_paths[name][case.murder_slot] != case.murder_room

    # The culprit's lie is falsifiable by at least one other clue.
    lie = case.lie
    assert lie is not None
    assert lie.room != case.murder_room  # it IS a lie
    truthful_statements = [
        clue.statement for clue in case.clues
        if isinstance(clue, TestimonyClue) and clue.statement != lie
    ]
    falsified_by_testimony = any(
        statements_conflict(lie, statement) for statement in truthful_statements
    )
    falsified_by_record = any(
        clue.person == lie.speaker and clue.slot == lie.slot and clue.room != lie.room
        for clue in case.clues if isinstance(clue, RecordClue)
    )
    assert falsified_by_testimony or falsified_by_record, (
        f"unfalsifiable lie (seed={case.seed}, {case.difficulty.value})"
    )

    # Motive is never a giveaway: at least one innocent has one too.
    innocent_motives = [
        suspect for suspect in case.suspects
        if suspect.name != case.culprit and suspect.motive is not None
    ]
    assert innocent_motives, f"no innocent motive (seed={case.seed})"
    assert case.suspect_by_name(case.culprit).motive is not None

    # The forensic window really contains the murder slot.
    assert case.murder_slot in case.forensic_window


class TestSolvability(unittest.TestCase):
    def test_fuzz_unique_solutions(self) -> None:
        """10,000 generated cases; each must have exactly one deducible culprit."""
        for index in range(FUZZ_CASES):
            difficulty = TIERS[index % len(TIERS)]
            case = generate_case(seed=index, difficulty=difficulty)
            assert_case_invariants(case)

            result = solve(case.facts, case.clues)
            self.assertEqual(
                len(result.culprits), 1,
                f"seed={index} {difficulty.value}: solver found "
                f"{sorted(result.culprits)} consistent suspects",
            )
            self.assertEqual(
                result.solution, case.culprit,
                f"seed={index} {difficulty.value}: solver deduced "
                f"{result.solution}, ground truth is {case.culprit}",
            )
            if (index + 1) % 1000 == 0:
                print(f"  ... {index + 1}/{FUZZ_CASES} cases verified",
                      file=sys.stderr, flush=True)

    def test_seed_reproducibility(self) -> None:
        """The same seed + difficulty must yield the identical case."""
        for difficulty in TIERS:
            first = generate_case(seed=424242, difficulty=difficulty)
            second = generate_case(seed=424242, difficulty=difficulty)
            self.assertEqual(first.culprit, second.culprit)
            self.assertEqual(first.true_paths, second.true_paths)
            self.assertEqual(first.clues, second.clues)
            self.assertEqual(first.lie, second.lie)

    def test_solver_never_sees_ground_truth(self) -> None:
        """The solver layer must not import the generator."""
        import pathlib

        import deduction.engine.solver as solver_module
        source = pathlib.Path(solver_module.__file__).read_text()
        import_lines = [line for line in source.splitlines()
                        if line.strip().startswith(("import ", "from "))]
        for line in import_lines:
            self.assertNotIn("generator", line)
        self.assertNotIn("true_paths", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
