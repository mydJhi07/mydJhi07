"""Stages 1–3 of the pipeline: forward simulation, clue derivation, the lie.

The world is *simulated first*: every character walks a physically
consistent path through the manor, the murder happens at a concrete
room/time with the culprit alone with the victim, and only then are clues
*read out of* that ground truth.  Nothing is ever fabricated and then
checked for consistency after the fact.

Stage 4 acceptance also happens here: :func:`generate_case` hands every
candidate case to the independent solver (which sees only public facts and
clues) and rejects any case whose consistent-suspect set is not exactly the
ground-truth culprit.
"""
from __future__ import annotations

import random
from typing import Optional

from deduction.engine.difficulty import CONFIGS, DifficultyConfig
from deduction.engine.solver import solve
from deduction.world import narrative
from deduction.world.models import (
    BodyClue,
    Case,
    Clue,
    Difficulty,
    ForensicClue,
    MotiveClue,
    PhysicalClue,
    PublicCaseFacts,
    RecordClue,
    Room,
    Statement,
    Suspect,
    TestimonyClue,
    TimeSlot,
)

_MAX_ATTEMPTS = 500
_PATH_RESAMPLES = 40
_STAY_PROBABILITY = 0.4


class GenerationError(RuntimeError):
    """Raised only if a valid case cannot be produced (should never happen)."""


def generate_case(seed: int, difficulty: Difficulty = Difficulty.MEDIUM) -> Case:
    """Generate a solver-verified case.  Deterministic in (seed, difficulty)."""
    config = CONFIGS[difficulty]
    rng = random.Random(f"deduction:{difficulty.value}:{seed}")
    for _ in range(_MAX_ATTEMPTS):
        case = _attempt_case(rng, seed, difficulty, config)
        if case is None:
            continue
        # Stage 4 acceptance: the independent solver, fed only public facts
        # and clues, must converge on exactly the ground-truth culprit.
        result = solve(case.facts, case.clues)
        if result.culprits == {case.culprit}:
            return case
    raise GenerationError(
        f"could not generate a uniquely solvable case for seed={seed}, "
        f"difficulty={difficulty.value}"
    )


# ---------------------------------------------------------------------------
# Stage 1 — forward simulation
# ---------------------------------------------------------------------------

def _build_room_graph(rng: random.Random, count: int) -> list[Room]:
    """A random connected undirected graph: spanning tree + a few extra doors."""
    picks = narrative.draw_rooms(rng, count)
    names = [name for name, _ in picks]
    edges: set[frozenset[str]] = set()
    shuffled = names[:]
    rng.shuffle(shuffled)
    for index in range(1, len(shuffled)):
        other = shuffled[rng.randrange(index)]
        edges.add(frozenset({shuffled[index], other}))
    for _ in range(count // 2):
        a, b = rng.sample(names, 2)
        edges.add(frozenset({a, b}))
    neighbors: dict[str, set[str]] = {name: set() for name in names}
    for edge in edges:
        a, b = sorted(edge)
        neighbors[a].add(b)
        neighbors[b].add(a)
    return [
        Room(name=name, description=description,
             neighbors=tuple(sorted(neighbors[name])))
        for name, description in picks
    ]


def _reach(rooms: list[Room]) -> dict[str, list[str]]:
    """Rooms reachable in one step (stay put or use an adjacent door)."""
    return {room.name: sorted(set(room.neighbors) | {room.name}) for room in rooms}


def _random_walk(rng: random.Random, reach: dict[str, list[str]],
                 room_names: list[str], slots: int) -> list[str]:
    path = [rng.choice(room_names)]
    for _ in range(slots - 1):
        here = path[-1]
        if rng.random() < _STAY_PROBABILITY:
            path.append(here)
        else:
            path.append(rng.choice(reach[here]))
    return path


def _culprit_path(rng: random.Random, reach: dict[str, list[str]],
                  murder_room: str, murder_slot: int, slots: int) -> list[str]:
    """A path pinned to the murder room at the murder slot, walking backward
    to slot 0 and forward to the end — never re-entering the murder room
    after the deed (no one may stumble on the culprit with the body)."""
    path = [""] * slots
    path[murder_slot] = murder_room
    for slot in range(murder_slot - 1, -1, -1):
        path[slot] = rng.choice(reach[path[slot + 1]])
    for slot in range(murder_slot + 1, slots):
        options = [room for room in reach[path[slot - 1]] if room != murder_room]
        path[slot] = rng.choice(options) if options else path[slot - 1]
    return path


def _innocent_path(rng: random.Random, reach: dict[str, list[str]],
                   room_names: list[str], slots: int,
                   murder_room: str, murder_slot: int) -> Optional[list[str]]:
    """A free path that stays out of the murder room from the murder slot on
    (the murder needs privacy; afterwards, nobody trips over the body until
    it is discovered at night's end)."""
    for _ in range(_PATH_RESAMPLES):
        path = _random_walk(rng, reach, room_names, slots)
        if all(path[slot] != murder_room for slot in range(murder_slot, slots)):
            return path
    return None


# ---------------------------------------------------------------------------
# Stages 2 & 3 — clue derivation and the lie
# ---------------------------------------------------------------------------

def _true_statement(speaker: str, slot: int, paths: dict[str, list[str]],
                    alive_upto: dict[str, int]) -> Statement:
    """Read a truthful, exhaustive account straight out of ground truth."""
    room = paths[speaker][slot]
    seen = frozenset(
        other for other, path in paths.items()
        if other != speaker and path[slot] == room and slot <= alive_upto[other]
    )
    return Statement(speaker=speaker, slot=slot, room=room, seen=seen)


def _attempt_case(rng: random.Random, seed: int, difficulty: Difficulty,
                  config: DifficultyConfig) -> Optional[Case]:
    # ---- Stage 1: the world ----
    rooms = _build_room_graph(rng, config.rooms)
    reach = _reach(rooms)
    room_names = [room.name for room in rooms]
    slot_labels = narrative.make_slot_labels(config.slots)
    slots = tuple(TimeSlot(index=index, label=label)
                  for index, label in enumerate(slot_labels))

    names = narrative.draw_names(rng, config.suspects + 1)
    victim_name = names[0]
    suspect_names = names[1:]

    # Murder slot: never the very first or very last slot, and the forensic
    # window must fit inside the timeline.
    murder_slot = rng.randrange(1, config.slots - 1)
    window_low = max(0, murder_slot - config.window_size + 1)
    window_high = min(murder_slot, config.slots - config.window_size)
    if window_low > window_high:
        return None
    window_start = rng.randint(window_low, window_high)
    forensic_window = tuple(range(window_start, window_start + config.window_size))

    victim_path = _random_walk(rng, reach, room_names, config.slots)
    murder_room = victim_path[murder_slot]
    # The victim never leaves the murder room again.
    for slot in range(murder_slot, config.slots):
        victim_path[slot] = murder_room

    culprit = rng.choice(suspect_names)
    paths: dict[str, list[str]] = {victim_name: victim_path}
    paths[culprit] = _culprit_path(rng, reach, murder_room, murder_slot, config.slots)
    for name in suspect_names:
        if name == culprit:
            continue
        path = _innocent_path(rng, reach, room_names, config.slots,
                              murder_room, murder_slot)
        if path is None:
            return None
        paths[name] = path

    # The culprit must be *alone* with the victim: guaranteed, because every
    # innocent path avoids the murder room from the murder slot onward.

    # ---- Stage 3 (chosen early, it can fail): the lie ----
    # The culprit will claim to have been in a room that actually held
    # innocent witnesses, and to have seen exactly its actual occupants.
    # Every occupant's exhaustive truthful account omits the culprit, so the
    # lie is guaranteed falsifiable.
    occupancy: dict[str, list[str]] = {name: [] for name in room_names}
    for name in suspect_names:
        if name != culprit:
            occupancy[paths[name][murder_slot]].append(name)
    candidates = [
        room for room in room_names
        if room != murder_room
        and len(occupancy[room]) >= config.min_lie_witnesses
    ]
    if not candidates:
        return None
    # Prefer a lie that fits the culprit's own truthful neighboring claims,
    # so it cannot be dismissed on movement grounds alone.
    prev_room = paths[culprit][murder_slot - 1]
    next_room = (paths[culprit][murder_slot + 1]
                 if murder_slot + 1 < config.slots else None)
    plausible = [
        room for room in candidates
        if room in reach[prev_room]
        and (next_room is None or next_room in reach[room])
    ]
    lie_room = rng.choice(plausible if plausible else candidates)
    lie = Statement(
        speaker=culprit,
        slot=murder_slot,
        room=lie_room,
        seen=frozenset(occupancy[lie_room]),
    )

    # ---- Stage 1 (continued): motives, traits, relationships ----
    innocent_names = [name for name in suspect_names if name != culprit]
    motive_holders = [culprit] + rng.sample(
        innocent_names, min(config.innocent_motives, len(innocent_names))
    )
    motive_texts = rng.sample(narrative.MOTIVES, len(motive_holders))
    motives = dict(zip(motive_holders, motive_texts))

    occupations = rng.sample(narrative.OCCUPATIONS, config.suspects + 1)
    traits = rng.sample(narrative.TRAITS, config.suspects)
    relationships = rng.sample(narrative.RELATIONSHIPS, config.suspects)
    demeanors = [rng.choice(narrative.DEMEANORS) for _ in suspect_names]

    suspects = tuple(
        Suspect(
            name=name,
            occupation=occupations[index],
            trait=traits[index],
            relationship=relationships[index],
            motive=motives.get(name),
            demeanor=demeanors[index],
        )
        for index, name in enumerate(suspect_names)
    )
    victim = Suspect(
        name=victim_name,
        occupation=occupations[-1],
        trait="",
        relationship="the victim",
        motive=None,
        demeanor="",
    )

    # ---- Stage 2: derive every clue from ground truth ----
    alive_upto = {name: config.slots - 1 for name in suspect_names}
    alive_upto[victim_name] = murder_slot  # seen alive up to the murder slot
    clues: list[Clue] = []

    for name in suspect_names:
        for slot in range(config.slots):
            if name == culprit and slot == murder_slot:
                clues.append(TestimonyClue(statement=lie))
            else:
                clues.append(TestimonyClue(
                    statement=_true_statement(name, slot, paths, alive_upto)))

    clues.append(BodyClue(
        victim=victim_name,
        room=murder_room,
        discovered_text=rng.choice(narrative.BODY_TEXTS).format(
            victim=victim_name, room=murder_room),
    ))
    clues.append(ForensicClue(
        window=forensic_window,
        report_text=rng.choice(narrative.FORENSIC_TEXTS).format(
            start=slot_labels[forensic_window[0]],
            end=slot_labels[forensic_window[-1]]),
    ))

    # Hard records corroborating innocents' true whereabouts.
    record_pool = [(name, slot) for name in innocent_names
                   for slot in range(config.slots)]
    for name, slot in rng.sample(record_pool, min(config.records, len(record_pool))):
        clues.append(RecordClue(
            person=name, slot=slot, room=paths[name][slot],
            source_text=rng.choice(narrative.RECORD_TEXTS).format(
                person=name, room=paths[name][slot], time=slot_labels[slot]),
        ))

    # The weapon, found at the scene.
    clues.append(PhysicalClue(
        room_found=murder_room,
        description=f"The murder weapon: {rng.choice(narrative.WEAPONS)}, "
                    f"left near the body.",
        linked_suspect=None,
        is_weapon=True,
    ))

    # Red herrings: traces of innocents in rooms they genuinely visited —
    # ideally the murder room itself, at an innocent hour.
    herring_candidates: list[tuple[str, str]] = []
    for suspect in suspects:
        if suspect.name == culprit:
            continue
        visited = {paths[suspect.name][slot] for slot in range(config.slots)}
        preferred = [room for room in visited if room == murder_room]
        for room in preferred or sorted(visited):
            herring_candidates.append((suspect.name, room))
    rng.shuffle(herring_candidates)
    for name, room in herring_candidates[:config.red_herrings]:
        trait = next(s.trait for s in suspects if s.name == name)
        item_hint = narrative.TRAIT_ITEMS[trait]
        clues.append(PhysicalClue(
            room_found=room,
            description=rng.choice(narrative.HERRING_TEXTS).format(
                item_hint=item_hint, name=name),
            linked_suspect=name,
        ))

    # Discoverable motives (letters, diary pages) for everyone who has one.
    for name, motive in motives.items():
        clues.append(MotiveClue(
            suspect=name,
            room_found=rng.choice(room_names),
            description=rng.choice(narrative.MOTIVE_DISCOVERY_TEXTS).format(
                room=rng.choice(room_names), name=name, motive=motive),
        ))

    facts = PublicCaseFacts(
        rooms=tuple(rooms),
        slots=slots,
        suspect_names=tuple(suspect_names),
        victim_name=victim_name,
    )
    return Case(
        seed=seed,
        difficulty=difficulty,
        facts=facts,
        clues=clues,
        suspects=suspects,
        victim=victim,
        culprit=culprit,
        murder_room=murder_room,
        murder_slot=murder_slot,
        forensic_window=forensic_window,
        true_paths=paths,
        lie=lie,
        true_murder_slot_room=murder_room,
    )
