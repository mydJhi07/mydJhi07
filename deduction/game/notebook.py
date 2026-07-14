"""The case notebook: an auto-populating suspect × time-slot grid.

Pure data — the UI layer renders it.  A cell is filled the moment the
player hears the corresponding statement; contradictions between any two
*discovered* statements (or a statement and a hard record) are surfaced
automatically, because spotting them by eye is the game.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from deduction.engine.solver import statements_conflict
from deduction.world.models import PublicCaseFacts, RecordClue, Statement


@dataclass
class NotebookCell:
    statement: Optional[Statement] = None
    contested: bool = False       # conflicts with another discovered statement
    corroborated: bool = False    # confirmed by a hard record


@dataclass
class Notebook:
    cells: dict[tuple[str, int], NotebookCell]
    conflicts: list[tuple[Statement, Statement]] = field(default_factory=list)
    record_conflicts: list[tuple[RecordClue, Statement]] = field(default_factory=list)


def build_notebook(facts: PublicCaseFacts,
                   discovered_statements: list[Statement],
                   discovered_records: list[RecordClue]) -> Notebook:
    cells = {
        (name, slot.index): NotebookCell()
        for name in facts.suspect_names for slot in facts.slots
    }
    for statement in discovered_statements:
        cells[(statement.speaker, statement.slot)].statement = statement

    notebook = Notebook(cells=cells)

    ordered = sorted(discovered_statements,
                     key=lambda statement: (statement.slot, statement.speaker))
    for index, first in enumerate(ordered):
        for second in ordered[index + 1:]:
            if statements_conflict(first, second):
                notebook.conflicts.append((first, second))
                cells[(first.speaker, first.slot)].contested = True
                cells[(second.speaker, second.slot)].contested = True

    for record in discovered_records:
        cell = cells.get((record.person, record.slot))
        if cell is None or cell.statement is None:
            continue
        if cell.statement.room == record.room:
            cell.corroborated = True
        else:
            cell.contested = True
            notebook.record_conflicts.append((record, cell.statement))
    return notebook
