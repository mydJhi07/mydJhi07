"""Name pools, motives, flavor text — everything narrative, nothing logical.

All functions draw from an explicit ``random.Random`` so cases are fully
seed-reproducible.  No module-level mutable state.
"""
from __future__ import annotations

import random

FIRST_NAMES = [
    "Adelaide", "Bartholomew", "Cordelia", "Desmond", "Eleanor", "Fitzgerald",
    "Genevieve", "Horace", "Imogen", "Jasper", "Katherine", "Leopold",
    "Millicent", "Nathaniel", "Ophelia", "Percival", "Rosalind", "Sebastian",
    "Theodora", "Ulysses", "Vivienne", "Winston", "Xenia", "Yusuf",
]

LAST_NAMES = [
    "Ashcroft", "Blackwood", "Carmichael", "Davenport", "Everly", "Fairbanks",
    "Greenhalgh", "Hollingsworth", "Ironwood", "Jessop", "Kingsley", "Lockhart",
    "Montague", "Northcott", "Ormond", "Pemberton", "Quimby", "Ravenscroft",
    "Sinclair", "Thornbury", "Underhill", "Vandermeer", "Whitlock", "Yardley",
]

OCCUPATIONS = [
    "retired colonel", "concert pianist", "family solicitor", "botanist",
    "stage actress", "antiques dealer", "private physician", "novelist",
    "art appraiser", "yacht broker", "archaeologist", "portrait painter",
    "racehorse trainer", "perfumer", "chess master", "opera singer",
]

TRAITS = [
    "chain-smokes thin cigars", "wears a distinctive green tweed coat",
    "carries a silver-tipped walking cane", "always trails rose perfume",
    "wears heavy hobnailed boots", "fidgets with a monogrammed handkerchief",
    "has a fondness for brandied cherries", "wears kid leather gloves indoors",
    "carries a pocket chess set", "hums old waltzes without noticing",
    "wears a scarab brooch", "leaves ink stains on everything touched",
    "wears a fur-lined stole", "taps out morse code when nervous",
    "carries loose pipe tobacco in every pocket", "wears a cracked monocle",
]

RELATIONSHIPS = [
    "estranged sibling of the victim", "the victim's business partner",
    "an old rival from university days", "the victim's former fiancé(e)",
    "a cousin owed a considerable debt", "the victim's longtime physician",
    "a neighbor locked in a land dispute", "the victim's protégé",
    "an old friend grown distant", "the victim's chief creditor",
    "a collaborator on an unfinished book", "the victim's ward",
]

MOTIVES = [
    "stands to inherit a fortune under the victim's will",
    "was being blackmailed by the victim over an old scandal",
    "was cheated out of a business stake by the victim",
    "was publicly humiliated by the victim last season",
    "owed the victim a ruinous gambling debt",
    "was about to be exposed by the victim for forgery",
    "was denied a promised inheritance by the victim",
    "blamed the victim for a family tragedy years ago",
    "was locked in a bitter lawsuit with the victim",
    "had a love affair ended cruelly by the victim",
]

DEMEANORS = [
    "answers slowly, weighing every word", "is brisk and faintly irritated",
    "keeps glancing at the door", "is theatrical and eager to help",
    "speaks in a flat, tired monotone", "is defensive from the first question",
    "seems genuinely shaken", "smiles too much for the occasion",
    "is icily polite", "keeps wringing their hands",
]

ROOM_POOLS: list[list[tuple[str, str]]] = [
    [
        ("Library", "Floor-to-ceiling shelves; the smell of old paper and pipe smoke."),
        ("Conservatory", "Glass walls sweating with the heat of orchids."),
        ("Billiard Room", "Green baize under a low brass lamp."),
        ("Dining Hall", "A long table still set with the evening's ruins."),
        ("Study", "A leather-topped desk, papers in careful disorder."),
        ("Gallery", "Ancestral portraits watching from the walls."),
        ("Drawing Room", "Velvet chairs arranged for conversations that never happen."),
        ("Wine Cellar", "Cold stone, racks of dusty bottles, a single bare bulb."),
    ],
    [
        ("Grand Foyer", "A sweeping staircase and a chandelier of doubtful stability."),
        ("Music Room", "A grand piano, its lid propped like a raised eyebrow."),
        ("Smoking Room", "Cracked leather chairs in a permanent blue haze."),
        ("Kitchen", "Copper pots and the ghost of tonight's roast."),
        ("Terrace", "Flagstones slick with evening mist."),
        ("Trophy Room", "Glass eyes glinting from every wall."),
        ("Chapel", "A private chapel, candles guttering in the draft."),
        ("Boathouse", "Oars, tarpaulins, and the slap of dark water below."),
    ],
]

WEAPONS = [
    "a heavy bronze candlestick", "a letter opener shaped like a dagger",
    "a marble bust of some forgotten ancestor", "a fireplace poker",
    "a crystal decanter, now cracked", "an antique dueling pistol's butt",
    "a bronze sundial ornament", "a walking stick with a weighted head",
]

BODY_TEXTS = [
    "The body was found by the housekeeper just before midnight, {victim} lying beside the cold hearth of the {room}.",
    "A scream from the {room} at midnight: the butler found {victim} dead upon the floor.",
    "{victim} was discovered in the {room} when the household gathered for a nightcap.",
]

FORENSIC_TEXTS = [
    "The coroner is unequivocal: death occurred between {start} and {end}.",
    "Rigor and lividity place the time of death between {start} and {end}, the coroner reports.",
    "The medical examiner fixes the moment of death within the window {start}–{end}.",
]

RECORD_TEXTS = [
    "The butler's service log notes {person} in the {room} at {time}.",
    "A dated photograph from the house camera shows {person} in the {room} at {time}.",
    "The housemaid's rounds ledger records {person} in the {room} at {time}.",
    "A telephone operator's slip confirms a call taken by {person} in the {room} at {time}.",
]

HERRING_TEXTS = [
    "{item_hint} — unmistakably {name}'s.",
    "{item_hint}, of the kind {name} is never without.",
    "{item_hint}; the household says only {name} matches it.",
]

TRAIT_ITEMS = {
    "chain-smokes thin cigars": "A cold stub of a thin cigar",
    "wears a distinctive green tweed coat": "A snag of green tweed on a door latch",
    "carries a silver-tipped walking cane": "A scuff of silver polish on the floorboards",
    "always trails rose perfume": "A lingering trace of rose perfume",
    "wears heavy hobnailed boots": "Hobnail scratches across the parquet",
    "fidgets with a monogrammed handkerchief": "A monogrammed handkerchief, dropped",
    "has a fondness for brandied cherries": "A saucer of brandied cherry stones",
    "wears kid leather gloves indoors": "A single kid leather glove",
    "carries a pocket chess set": "A stray ivory pawn under the settee",
    "hums old waltzes without noticing": "Sheet music for a waltz, recently handled",
    "wears a scarab brooch": "A scarab brooch pin, bent",
    "leaves ink stains on everything touched": "Fresh ink smudges on the door handle",
    "wears a fur-lined stole": "Tufts of pale fur caught on a chair arm",
    "taps out morse code when nervous": "A tabletop scored with tiny rhythmic dents",
    "carries loose pipe tobacco in every pocket": "A scatter of loose pipe tobacco",
    "wears a cracked monocle": "A sliver of monocle glass",
}

MOTIVE_DISCOVERY_TEXTS = [
    "A letter in a drawer of the {room} reveals that {name} {motive}.",
    "A page of the victim's diary, found in the {room}, records that {name} {motive}.",
    "Torn correspondence in the {room} makes plain that {name} {motive}.",
]


def make_slot_labels(count: int) -> list[str]:
    """Evening hours: 6 PM onward."""
    labels = []
    for index in range(count):
        hour = 6 + index
        if hour < 12:
            labels.append(f"{hour}:00 PM")
        else:
            labels.append(f"{hour - 12}:00 AM" if hour > 12 else "12:00 AM")
    return labels


def draw_names(rng: random.Random, count: int) -> list[str]:
    firsts = rng.sample(FIRST_NAMES, count)
    lasts = rng.sample(LAST_NAMES, count)
    return [f"{first} {last}" for first, last in zip(firsts, lasts)]


def draw_rooms(rng: random.Random, count: int) -> list[tuple[str, str]]:
    pool = rng.choice(ROOM_POOLS)
    return rng.sample(pool, count)
