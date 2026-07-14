# DEDUCTION

A procedurally generated murder mystery for the terminal. Every playthrough
is a brand-new case — victim, culprit, motive, timeline, alibis, physical
evidence, witness testimony — and **every case is guaranteed to have exactly
one logically deducible solution**.

## Play

```bash
pip install rich                       # the only dependency (UI layer only)
python -m deduction.main               # a random Medium case
python -m deduction.main --seed 1234   # a reproducible case
python -m deduction.main --difficulty hard
python -m deduction.main --case M-1234 # replay a shared case code
```

Debug / curiosity modes:

```bash
python -m deduction.main --seed 1 --reveal   # print the hidden ground truth
python -m deduction.main --seed 1 --solve    # watch the solver deduce, step by step
```

As the detective you can **examine rooms** (physical evidence, letters),
**interrogate suspects** (whereabouts per hour, who they saw, background),
**cross-examine** (press a contradiction between two accounts), consult the
auto-populating **case notebook** (a suspect × hour grid that flags
contradictions and record-corroborations), take **hints** (the solver's own
next deduction step — never the answer), and finally **accuse**. Win or
lose, the game reveals the true timeline and the full deduction chain.

## How uniqueness is guaranteed

1. **Forward simulation** (`world/generator.py`) — the world is simulated
   first: every character walks a physically consistent path through a
   random connected room graph; the culprit is alone with the victim at the
   murder room/time. Ground truth is consistent *by construction*.
2. **Clue derivation** — clues are never invented; they are read out of the
   simulation: exhaustive testimony ("I was in the Library and saw exactly
   these people"), the body's location, a forensic time-of-death window,
   hard records, the weapon, red herrings, motives.
3. **The lie** — innocents always tell the truth; the culprit lies about the
   murder hour, claiming a room that actually held witnesses and to have
   seen exactly its actual occupants. The lie is falsifiable by
   construction.
4. **Independent verification** (`engine/solver.py`) — a deduction engine
   that never sees ground truth treats `culprit ∈ suspects` as a constraint
   satisfaction problem: for each (suspect, window-slot) hypothesis it
   checks movement adjacency, alone-with-victim, exhaustive-sighting
   consistency, record agreement, and victim-path feasibility. A case is
   accepted **only** if exactly one suspect survives — and it must be the
   ground-truth culprit.
5. **Difficulty** (`engine/difficulty.py`) — tiers tune world size, the
   forensic window width, how well-witnessed the lie is, and red-herring
   count; measured difficulty is the number of independent deduction steps
   the solver needed.

Red herrings (innocents with motives, suspicious items, proximity to the
scene at the wrong hour) mislead intuition but never logic: soft clues
carry no logical weight, and the solver is what proves it.

## Tests

```bash
python -m unittest deduction.tests.test_solvability -v
```

The acceptance test generates **10,000 cases across all difficulty tiers**
and asserts each one has exactly one consistent suspect equal to the true
culprit, plus: nobody occupies two rooms at once, every path respects the
room graph, the culprit's lie is falsifiable by at least one other clue,
and at least one innocent also has a motive. A quick run:
`DEDUCTION_FUZZ_CASES=500 python -m unittest deduction.tests.test_solvability`.

## Layout

```
deduction/
├── main.py              # CLI entry point
├── world/
│   ├── models.py        # dataclasses: rooms, slots, suspects, clues, Case
│   ├── generator.py     # stages 1–3: simulate, derive clues, plant the lie
│   └── narrative.py     # names, motives, flavor pools
├── engine/
│   ├── solver.py        # stage 4: independent constraint-based deduction
│   └── difficulty.py    # stage 5: tier tuning + deduction chain/steps
├── game/
│   ├── loop.py          # player actions & state
│   ├── notebook.py      # the contradiction grid (pure data)
│   └── ui.py            # rich rendering
└── tests/
    └── test_solvability.py
```

The core engine (world + engine + tests) is standard-library only;
`rich` is used exclusively by the UI layer.
