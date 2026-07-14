"""All ``rich`` rendering lives here — the game loop never prints directly.

The UI reads game structures and draws them; it makes no decisions.
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from deduction.game.notebook import Notebook
from deduction.world.models import (
    Case,
    MotiveClue,
    PhysicalClue,
    PublicCaseFacts,
    RecordClue,
    Statement,
    Suspect,
)


class GameUI:
    def __init__(self) -> None:
        self.console = Console(highlight=False)

    # ------------------------------------------------------------------ io

    def choose(self, prompt: str, options: list[str],
               allow_back: bool = True) -> int:
        """Numbered menu; returns the chosen index, or -1 for 'back'."""
        for index, option in enumerate(options, start=1):
            self.console.print(f"  [bold cyan]{index}[/].  {option}")
        if allow_back:
            self.console.print("  [bold cyan]0[/].  (back)")
        floor = 0 if allow_back else 1
        choices = [str(value) for value in range(floor, len(options) + 1)]
        answer = IntPrompt.ask(prompt, choices=choices, show_choices=False,
                               console=self.console)
        return answer - 1

    def confirm(self, prompt: str) -> bool:
        return Prompt.ask(prompt, choices=["y", "n"],
                          console=self.console) == "y"

    def pause(self) -> None:
        Prompt.ask("[dim](press Enter)[/]", default="", show_default=False,
                   console=self.console)

    # ----------------------------------------------------------- scenes

    def banner(self) -> None:
        self.console.print(Panel.fit(
            "[bold white]D E D U C T I O N[/]\n"
            "[dim]a procedurally generated murder mystery[/]",
            border_style="red"))

    def briefing(self, case: Case, body_text: str, forensic_text: str,
                 case_code: str) -> None:
        facts = case.facts
        lines = [
            f"[bold red]{body_text}[/]",
            "",
            f"[yellow]{forensic_text}[/]",
            "",
            f"The victim: [bold]{facts.victim_name}[/], "
            f"{case.victim.occupation}.",
            f"{len(facts.suspect_names)} guests were in the house all "
            f"evening. One of them is lying to you.",
            "",
            f"[dim]Case code: {case_code}  —  replay this exact case with "
            f"--case {case_code}[/]",
        ]
        self.console.print(Panel("\n".join(lines), title="The Case",
                                 border_style="red"))

    def show_map(self, facts: PublicCaseFacts, examined: set[str]) -> None:
        table = Table(title="The Manor", border_style="blue")
        table.add_column("Room", style="bold")
        table.add_column("Connects to")
        table.add_column("Searched?", justify="center")
        for room in facts.rooms:
            table.add_row(room.name, ", ".join(room.neighbors),
                          "[green]yes[/]" if room.name in examined else "[dim]no[/]")
        self.console.print(table)

    def show_suspects(self, suspects: tuple[Suspect, ...],
                      met: set[str]) -> None:
        table = Table(title="The Suspects", border_style="magenta")
        table.add_column("Name", style="bold")
        table.add_column("Occupation")
        table.add_column("Notes")
        for suspect in suspects:
            notes = (f"{suspect.relationship}; {suspect.trait}"
                     if suspect.name in met else "[dim]not yet questioned[/]")
            table.add_row(suspect.name, suspect.occupation, notes)
        self.console.print(table)

    def show_room_search(self, room: str, description: str,
                         findings: list[str]) -> None:
        body = Text.from_markup(f"[italic dim]{description}[/]\n")
        if findings:
            for finding in findings:
                body.append_text(Text.from_markup(f"\n  [yellow]•[/] {finding}"))
        else:
            body.append_text(Text.from_markup("\n[dim]Nothing of note.[/]"))
        self.console.print(Panel(body, title=f"Searching the {room}",
                                 border_style="yellow"))

    def show_statement(self, facts: PublicCaseFacts, statement: Statement,
                       demeanor: str) -> None:
        label = facts.slots[statement.slot].label
        if statement.seen:
            seen = ", ".join(sorted(statement.seen))
            quote = (f"At {label}? I was in the {statement.room}. "
                     f"{seen} — they were there with me. No one else.")
        else:
            quote = (f"At {label}? I was in the {statement.room}, "
                     f"quite alone. I saw no one.")
        self.console.print(
            f"  [bold]{statement.speaker}[/] [dim]({demeanor})[/]:\n"
            f'  [italic]"{quote}"[/]\n')

    def show_background(self, suspect: Suspect) -> None:
        self.console.print(Panel(
            f"[bold]{suspect.name}[/], {suspect.occupation}.\n"
            f"Relationship to the victim: {suspect.relationship}.\n"
            f"You notice: {suspect.trait}.",
            border_style="magenta"))

    def show_notebook(self, facts: PublicCaseFacts, notebook: Notebook) -> None:
        table = Table(title="Case Notebook — claimed whereabouts",
                      border_style="cyan", show_lines=True)
        table.add_column("Suspect", style="bold", no_wrap=True)
        for slot in facts.slots:
            table.add_column(slot.label, justify="center")
        for name in facts.suspect_names:
            row: list[Text] = [Text(name)]
            for slot in facts.slots:
                cell = notebook.cells[(name, slot.index)]
                if cell.statement is None:
                    row.append(Text("?", style="dim"))
                    continue
                text = Text(cell.statement.room)
                if cell.statement.seen:
                    text.append(f"\n+{len(cell.statement.seen)} seen",
                                style="dim")
                else:
                    text.append("\nalone", style="dim")
                if cell.contested:
                    text.stylize("bold red")
                    text.append("\n⚠ contested", style="bold red")
                elif cell.corroborated:
                    text.append("\n✓ on record", style="green")
                row.append(text)
            table.add_row(*row)
        self.console.print(table)
        if notebook.conflicts:
            self.console.print("[bold red]Contradictions in testimony:[/]")
            for first, second in notebook.conflicts:
                label = facts.slots[first.slot].label
                self.console.print(
                    f"  [red]⚠[/] {label}: [bold]{first.speaker}[/] and "
                    f"[bold]{second.speaker}[/] cannot both be right.")
        for record, statement in notebook.record_conflicts:
            self.console.print(
                f"  [red]⚠[/] A hard record contradicts "
                f"[bold]{statement.speaker}[/]'s account of "
                f"{facts.slots[record.slot].label}.")

    def show_evidence(self, clues: list) -> None:
        table = Table(title="Evidence & Documents", border_style="yellow")
        table.add_column("Where", style="bold", no_wrap=True)
        table.add_column("Finding")
        for clue in clues:
            if isinstance(clue, PhysicalClue):
                style = "[bold red]" if clue.is_weapon else ""
                table.add_row(clue.room_found,
                              f"{style}{clue.description}{'[/]' if style else ''}")
            elif isinstance(clue, MotiveClue):
                table.add_row(clue.room_found, f"[magenta]{clue.description}[/]")
            elif isinstance(clue, RecordClue):
                table.add_row("(record)", f"[green]{clue.source_text}[/]")
        self.console.print(table)

    def show_confrontation(self, facts: PublicCaseFacts, first: Statement,
                           second: Statement, reaction: str) -> None:
        label = facts.slots[first.slot].label
        self.console.print(Panel(
            f"You lay the two accounts side by side.\n\n"
            f"[bold]{first.speaker}[/]: the {first.room} at {label}, "
            f"{'with ' + ', '.join(sorted(first.seen)) if first.seen else 'alone'}.\n"
            f"[bold]{second.speaker}[/]: the {second.room} at {label}, "
            f"{'with ' + ', '.join(sorted(second.seen)) if second.seen else 'alone'}.\n\n"
            f"[italic]{reaction}[/]",
            title="Cross-examination", border_style="red"))

    def show_hint(self, hint: str, remaining: int) -> None:
        self.console.print(Panel(
            f"[italic]{hint}[/]\n\n[dim]{remaining} step(s) of reasoning "
            f"remain after this one.[/]",
            title="A quiet word from your own notes", border_style="green"))

    # ----------------------------------------------------------- endgame

    def show_verdict(self, correct: bool, accused: str, culprit: str) -> None:
        if correct:
            self.console.print(Panel(
                f"[bold green]Arrest made.[/] {accused} breaks down and "
                f"confesses. The case is closed.",
                title="VERDICT", border_style="green"))
        else:
            self.console.print(Panel(
                f"[bold red]{accused} is released with an apology.[/]\n"
                f"The real killer — [bold]{culprit}[/] — watches you from "
                f"across the hall, and smiles.",
                title="VERDICT", border_style="red"))

    def show_reveal(self, case: Case, chain: list[str]) -> None:
        facts = case.facts
        self.console.print(Rule("[bold]The Whole Truth[/]"))
        table = Table(title="What actually happened", border_style="white",
                      show_lines=False)
        table.add_column("Person", style="bold", no_wrap=True)
        for slot in facts.slots:
            table.add_column(slot.label, justify="center")
        order = [facts.victim_name] + list(facts.suspect_names)
        for name in order:
            row = [Text(name + (" †" if name == facts.victim_name else ""))]
            for slot in facts.slots:
                room = case.true_paths[name][slot.index]
                text = Text(room)
                if slot.index == case.murder_slot and room == case.murder_room \
                        and name in (facts.victim_name, case.culprit):
                    text.stylize("bold red")
                if name == facts.victim_name and slot.index > case.murder_slot:
                    text.stylize("dim")
                row.append(text)
            table.add_row(*row)
        self.console.print(table)

        lie = case.lie
        assert lie is not None
        self.console.print(Panel(
            f"[bold]{case.culprit}[/] murdered {facts.victim_name} in the "
            f"{case.murder_room} at {facts.slots[case.murder_slot].label} — "
            f"then claimed to have been in the {lie.room}. "
            f"Motive: {case.suspect_by_name(case.culprit).motive}.",
            title="The Killer", border_style="red"))

        self.console.print(Rule("[bold]The Deduction, step by step[/]"))
        for index, step in enumerate(chain, start=1):
            self.console.print(f"[bold cyan]{index}.[/] {step}\n")
