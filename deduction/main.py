"""Entry point.

    python -m deduction.main                     play a random Medium case
    python -m deduction.main --seed 1234         play a reproducible case
    python -m deduction.main --difficulty hard   pick a tier
    python -m deduction.main --case H-77         replay a shared case code
    python -m deduction.main --seed 1 --reveal   print the ground truth
    python -m deduction.main --seed 1 --solve    watch the solver deduce
"""
from __future__ import annotations

import argparse
import contextlib
import random
import signal
import sys

from deduction.engine.difficulty import build_deduction_chain, count_deduction_steps
from deduction.engine.solver import solve
from deduction.world.generator import generate_case
from deduction.world.models import (
    Case,
    Difficulty,
    MotiveClue,
    PhysicalClue,
    RecordClue,
)

_CODE_TO_TIER = {"E": Difficulty.EASY, "M": Difficulty.MEDIUM, "H": Difficulty.HARD}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="deduction", description="A procedurally generated murder mystery.")
    parser.add_argument("--seed", type=int, default=None,
                        help="case seed (default: random)")
    parser.add_argument("--difficulty", choices=[d.value for d in Difficulty],
                        default=Difficulty.MEDIUM.value)
    parser.add_argument("--case", metavar="CODE",
                        help="replay a shared case code, e.g. M-1234")
    parser.add_argument("--reveal", action="store_true",
                        help="print the hidden ground truth and exit (debug)")
    parser.add_argument("--solve", action="store_true",
                        help="run the independent solver on the clue set and "
                             "print its deduction, then exit")
    return parser.parse_args(argv)


def print_ground_truth(case: Case) -> None:
    facts = case.facts
    print(f"=== GROUND TRUTH  (seed {case.seed}, {case.difficulty.value}) ===")
    print(f"Victim : {facts.victim_name} ({case.victim.occupation})")
    print(f"Culprit: {case.culprit}")
    print(f"Murder : {case.murder_room} at {facts.slots[case.murder_slot].label}"
          f"  (forensic window: "
          f"{', '.join(facts.slots[s].label for s in case.forensic_window)})")
    assert case.lie is not None
    print(f"The lie: claims the {case.lie.room}, "
          f"'saw {', '.join(sorted(case.lie.seen)) or 'no one'}'")
    print()
    print("Rooms:")
    for room in facts.rooms:
        print(f"  {room.name} <-> {', '.join(room.neighbors)}")
    print()
    width = max(len(name) for name in case.true_paths) + 2
    header = " " * width + " | ".join(f"{slot.label:^14}" for slot in facts.slots)
    print(header)
    for name in [facts.victim_name, *facts.suspect_names]:
        path = case.true_paths[name]
        marker = "†" if name == facts.victim_name else (
            "!" if name == case.culprit else " ")
        cells = " | ".join(f"{room:^14}" for room in path)
        print(f"{marker}{name:<{width - 1}}{cells}")
    print()
    print("Suspects:")
    for suspect in case.suspects:
        tag = "CULPRIT" if suspect.name == case.culprit else "innocent"
        motive = suspect.motive or "no apparent motive"
        print(f"  [{tag:^8}] {suspect.name}: {suspect.relationship}; {motive}")
    print()
    print("Derived clues:")
    for clue in case.clues:
        if isinstance(clue, RecordClue):
            print(f"  [record ] {clue.source_text}")
        elif isinstance(clue, PhysicalClue):
            kind = "weapon " if clue.is_weapon else "herring"
            print(f"  [{kind}] ({clue.room_found}) {clue.description}")
        elif isinstance(clue, MotiveClue):
            print(f"  [motive ] {clue.description}")


def print_solver_run(case: Case) -> None:
    result = solve(case.facts, case.clues)
    print(f"=== SOLVER  (clues only — no ground truth) ===")
    print(f"Hypotheses tested: {len(case.facts.suspect_names)} suspects "
          f"x {len(result.window)} window slot(s)")
    print(f"Deduction steps  : {count_deduction_steps(result.eliminations)}")
    print(f"Consistent set   : {sorted(result.culprits)}")
    print()
    for step_number, step in enumerate(build_deduction_chain(case.facts, result), 1):
        print(f"{step_number}. {step}")
        print()
    verdict = "UNIQUE" if result.unique else "AMBIGUOUS (bug!)"
    match = "matches" if result.solution == case.culprit else "DOES NOT MATCH"
    print(f"[{verdict}] Solver's culprit {match} ground truth.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    difficulty = Difficulty(args.difficulty)
    seed = args.seed
    if args.case:
        try:
            tier_letter, seed_text = args.case.upper().split("-", 1)
            difficulty = _CODE_TO_TIER[tier_letter]
            seed = int(seed_text)
        except (ValueError, KeyError):
            print(f"Unrecognized case code: {args.case!r} (expected e.g. M-1234)")
            return 2
    if seed is None:
        seed = random.SystemRandom().randrange(1_000_000)

    case = generate_case(seed=seed, difficulty=difficulty)

    if args.reveal:
        print_ground_truth(case)
        return 0
    if args.solve:
        print_solver_run(case)
        return 0

    from deduction.game.loop import run  # imports rich; only needed to play
    try:
        caught = run(case)
    except (KeyboardInterrupt, EOFError):
        print("\nThe case file stays open on your desk.")
        return 130
    return 0 if caught else 1


if __name__ == "__main__":
    # Behave like a good Unix citizen when piped into `head` etc.
    with contextlib.suppress(ValueError):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    raise SystemExit(main())
