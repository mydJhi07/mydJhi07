"""The playable detective loop: examine, interrogate, cross-examine,
consult the notebook, accuse.

Holds all mutable game state explicitly in :class:`GameState`; the UI
renders, the engine reasons, and this module only orchestrates.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from deduction.engine.difficulty import build_deduction_chain
from deduction.engine.solver import SolveResult, solve
from deduction.game.notebook import build_notebook
from deduction.game.ui import GameUI
from deduction.world import narrative
from deduction.world.models import (
    BodyClue,
    Case,
    ForensicClue,
    MotiveClue,
    PhysicalClue,
    RecordClue,
    Statement,
)


@dataclass
class GameState:
    examined_rooms: set[str] = field(default_factory=set)
    met_suspects: set[str] = field(default_factory=set)
    heard: dict[tuple[str, int], Statement] = field(default_factory=dict)
    found_clues: list = field(default_factory=list)   # physical + motive clues
    hints_used: int = 0


def case_code(case: Case) -> str:
    return f"{case.difficulty.value[0].upper()}-{case.seed}"


def run(case: Case) -> bool:
    """Play the case.  Returns True if the player caught the culprit."""
    ui = GameUI()
    state = GameState()
    rng = random.Random(f"flavor:{case.seed}")

    # The solver's verdict, computed once from clues alone: it powers the
    # hint system and the step-by-step reveal.
    result: SolveResult = solve(case.facts, case.clues)
    chain = build_deduction_chain(case.facts, result)

    body = next(c for c in case.clues if isinstance(c, BodyClue))
    forensic = next(c for c in case.clues if isinstance(c, ForensicClue))
    records = [c for c in case.clues if isinstance(c, RecordClue)]
    testimony = {(c.statement.speaker, c.statement.slot): c.statement
                 for c in case.clues if hasattr(c, "statement")}

    ui.banner()
    ui.briefing(case, body.discovered_text, forensic.report_text,
                case_code(case))

    while True:
        notebook = build_notebook(case.facts, list(state.heard.values()), records)
        conflicts = len(notebook.conflicts) + len(notebook.record_conflicts)
        ui.console.print()
        choice = ui.choose(
            "What now, detective?",
            [
                "Examine a room",
                "Interrogate a suspect",
                f"Cross-examine  [red]({conflicts} contradiction(s) on file)[/]"
                if conflicts else "Cross-examine  [dim](no contradictions yet)[/]",
                "Consult the case notebook",
                "Review evidence & records",
                "Study the map of the manor",
                "Take a hint",
                "[bold red]Make an accusation[/]",
                "Abandon the case",
            ],
            allow_back=False,
        )
        if choice == 0:
            _examine(ui, state, case)
        elif choice == 1:
            _interrogate(ui, state, case, testimony)
        elif choice == 2:
            _cross_examine(ui, case, notebook, rng)
        elif choice == 3:
            ui.show_notebook(case.facts, notebook)
        elif choice == 4:
            ui.show_evidence(list(records) + state.found_clues)
        elif choice == 5:
            ui.show_map(case.facts, state.examined_rooms)
        elif choice == 6:
            _hint(ui, state, chain)
        elif choice == 7:
            outcome = _accuse(ui, case, chain)
            if outcome is not None:
                return outcome
        elif choice == 8:
            if ui.confirm("Walk away and let the killer go free?"):
                ui.show_reveal(case, chain)
                return False


def _examine(ui: GameUI, state: GameState, case: Case) -> None:
    rooms = list(case.facts.rooms)
    index = ui.choose("Search which room?",
                      [f"{room.name}" + (" [dim](searched)[/]"
                       if room.name in state.examined_rooms else "")
                       for room in rooms])
    if index < 0:
        return
    room = rooms[index]
    findings: list[str] = []
    for clue in case.clues:
        if isinstance(clue, (PhysicalClue, MotiveClue)) \
                and clue.room_found == room.name:
            findings.append(clue.description)
            if clue not in state.found_clues:
                state.found_clues.append(clue)
    state.examined_rooms.add(room.name)
    ui.show_room_search(room.name, room.description, findings)


def _interrogate(ui: GameUI, state: GameState, case: Case,
                 testimony: dict[tuple[str, int], Statement]) -> None:
    suspects = list(case.suspects)
    index = ui.choose("Question whom?", [s.name for s in suspects])
    if index < 0:
        return
    suspect = suspects[index]
    if suspect.name not in state.met_suspects:
        state.met_suspects.add(suspect.name)
        ui.show_background(suspect)
    while True:
        sub = ui.choose(
            f"What do you ask {suspect.name}?",
            ["Their whereabouts at a specific hour",
             "Their full account of the evening"])
        if sub < 0:
            return
        if sub == 0:
            slot_index = ui.choose(
                "Which hour?", [slot.label for slot in case.facts.slots])
            if slot_index < 0:
                continue
            slots = [slot_index]
        else:
            slots = [slot.index for slot in case.facts.slots]
        for slot in slots:
            statement = testimony[(suspect.name, slot)]
            state.heard[(suspect.name, slot)] = statement
            ui.show_statement(case.facts, statement, suspect.demeanor)


def _cross_examine(ui: GameUI, case: Case, notebook, rng: random.Random) -> None:
    pairs = list(notebook.conflicts)
    if not pairs:
        ui.console.print(
            "[dim]You have no two accounts on file that cannot both be "
            "true. Gather more testimony first.[/]")
        return
    options = [
        f"{case.facts.slots[first.slot].label}: "
        f"[bold]{first.speaker}[/] vs [bold]{second.speaker}[/]"
        for first, second in pairs
    ]
    index = ui.choose("Which contradiction do you press?", options)
    if index < 0:
        return
    first, second = pairs[index]
    who = ui.choose("Confront whom with it?", [first.speaker, second.speaker])
    if who < 0:
        return
    target, other = ((first, second) if who == 0 else (second, first))
    reaction = rng.choice(narrative.CONFRONTATION_REACTIONS).format(
        name=target.speaker, other=other.speaker, room=target.room,
        time=case.facts.slots[target.slot].label)
    ui.show_confrontation(case.facts, first, second, reaction)


def _hint(ui: GameUI, state: GameState, chain: list[str]) -> None:
    # Never hand over the final line — that names the killer.
    available = chain[:-1]
    if state.hints_used >= len(available):
        ui.console.print("[dim]Your notes have nothing more to offer. "
                         "The last step is yours to take.[/]")
        return
    hint = available[state.hints_used]
    state.hints_used += 1
    ui.show_hint(hint, len(available) - state.hints_used)


def _accuse(ui: GameUI, case: Case, chain: list[str]) -> bool | None:
    names = [s.name for s in case.suspects]
    index = ui.choose("You accuse...", names)
    if index < 0:
        return None
    accused = names[index]
    if not ui.confirm(f"Accuse {accused} of the murder of "
                      f"{case.facts.victim_name}? This is final"):
        return None
    correct = accused == case.culprit
    ui.show_verdict(correct, accused, case.culprit)
    ui.show_reveal(case, chain)
    return correct
