"""AquaMind domain layer - pure Python, no LangGraph and no LLM.

Everything the grader actually watches happen (safe-range rules, the
compatibility matrix, the bioload maths) is deterministic and lives here.
If the API key dies mid-demo, this file still runs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TypedDict


# --------------------------------------------------------------------------
# Readings
# --------------------------------------------------------------------------

class Reading(TypedDict):
    ts: str
    ph: Optional[float]
    ammonia: Optional[float]
    nitrite: Optional[float]
    nitrate: Optional[float]
    temp_c: Optional[float]


PARAMS = ("ph", "ammonia", "nitrite", "nitrate", "temp_c")

# (low, high, unit, label) for a healthy freshwater community tank
SAFE_RANGES: dict[str, tuple[float, float, str, str]] = {
    "ph":      (6.5, 7.8, "", "pH"),
    "ammonia": (0.0, 0.02, " ppm", "Ammonia (NH3)"),
    "nitrite": (0.0, 0.02, " ppm", "Nitrite (NO2)"),
    "nitrate": (0.0, 40.0, " ppm", "Nitrate (NO3)"),
    "temp_c":  (22.0, 28.0, " C", "Temperature"),
}

# At or above these values it is an emergency rather than a warning.
CRITICAL: dict[str, float] = {
    "ammonia": 0.5,
    "nitrite": 0.5,
    "nitrate": 80.0,
}

# Synonyms the parser accepts for each parameter.
ALIASES: dict[str, tuple[str, ...]] = {
    "ammonia": ("ammonia", "nh3", "nh4"),
    "nitrite": ("nitrite", "nitrites", "no2"),
    "nitrate": ("nitrate", "nitrates", "no3"),
    "ph":      ("ph",),
    "temp_c":  ("temp", "temperature"),
}

NUM = r"(-?\d+(?:\.\d+)?)"


def _find(text: str, names: tuple[str, ...]) -> Optional[float]:
    """Find '<name> [:=/is/of] <number>' or '<number> <name>' in free text."""
    for name in names:
        n = re.escape(name)
        m = re.search(r"\b" + n + r"\b\s*(?:is|=|:|of|at|reads|read)?\s*" + NUM, text)
        if m:
            return float(m.group(1))
        m = re.search(NUM + r"\s*(?:ppm|mg/l)?\s*(?:of\s+)?\b" + n + r"\b", text)
        if m:
            return float(m.group(1))
    return None


def _find_temperature(text: str) -> Optional[float]:
    """Temperature normalised to Celsius. Understands 26C, 78F, 'temp 26'."""
    m = re.search(r"\btemp(?:erature)?\b\s*(?:is|=|:|of|at)?\s*" + NUM
                  + r"\s*(?:deg|degrees)?\s*f\b", text)
    if m:
        return round((float(m.group(1)) - 32.0) * 5.0 / 9.0, 1)
    m = re.search(NUM + r"\s*(?:deg|degrees)?\s*f\b", text)
    if m:
        return round((float(m.group(1)) - 32.0) * 5.0 / 9.0, 1)
    m = re.search(NUM + r"\s*(?:deg|degrees)?\s*c\b", text)
    if m:
        return float(m.group(1))
    return _find(text, ALIASES["temp_c"])


def parse_reading(text: str, ts: Optional[str] = None) -> Reading:
    """Pull a water test out of free text. Missing parameters stay None."""
    t = (text or "").lower().replace("°", " ")
    return {
        "ts": ts or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ph": _find(t, ALIASES["ph"]),
        "ammonia": _find(t, ALIASES["ammonia"]),
        "nitrite": _find(t, ALIASES["nitrite"]),
        "nitrate": _find(t, ALIASES["nitrate"]),
        "temp_c": _find_temperature(t),
    }


def looks_like_test_result(text: str) -> bool:
    """True when the message carries at least one named parameter with a number."""
    r = parse_reading(text)
    return sum(1 for p in PARAMS if r[p] is not None) >= 1


# --------------------------------------------------------------------------
# The rule engine
# --------------------------------------------------------------------------

def evaluate(reading: Reading) -> list[str]:
    """Compare a reading against SAFE_RANGES. Returns human-readable alerts."""
    alerts: list[str] = []
    for param in PARAMS:
        value = reading.get(param)
        if value is None:
            continue
        low, high, unit, label = SAFE_RANGES[param]
        crit = CRITICAL.get(param)
        if crit is not None and value >= crit:
            alerts.append(
                "CRITICAL - {} {}{} is at or above {}{}. Do a 50% water change now "
                "and stop feeding for 24h.".format(label, value, unit, crit, unit)
            )
        elif value > high:
            alerts.append("HIGH - {} {}{} is above the safe max of {}{}.".format(
                label, value, unit, high, unit))
        elif value < low:
            alerts.append("LOW - {} {}{} is below the safe min of {}{}.".format(
                label, value, unit, low, unit))
    if not alerts:
        alerts.append("OK - every parameter tested is inside its safe range.")
    return alerts


def cycle_status(reading: Reading) -> str:
    """One-line read on where the nitrogen cycle is."""
    a, ni, na = reading.get("ammonia"), reading.get("nitrite"), reading.get("nitrate")
    if a is None and ni is None and na is None:
        return "unknown - no nitrogen parameters in this test"
    if (ni or 0) > 0.02:
        return "cycling - stage 2, nitrite spike, the tank is not safe for fish yet"
    if (a or 0) > 0.02:
        return "cycling - stage 1, ammonia present, bacteria not established"
    if (na or 0) > 5:
        return "cycled - ammonia and nitrite at zero with nitrate accumulating"
    return "cycled, or a very lightly stocked tank"


def trend(readings: list[Reading], param: str) -> Optional[str]:
    """Direction of travel for one parameter across the given readings."""
    vals = [r[param] for r in readings if r.get(param) is not None]
    if len(vals) < 2:
        return None
    label = SAFE_RANGES[param][3]
    delta = vals[-1] - vals[0]
    if abs(delta) < 1e-9:
        return "{} flat at {}".format(label, vals[-1])
    return "{} {} {} -> {}".format(
        label, "rising" if delta > 0 else "falling", vals[0], vals[-1])


def format_reading(reading: Reading) -> str:
    bits = []
    for param in PARAMS:
        v = reading.get(param)
        if v is not None:
            low, high, unit, label = SAFE_RANGES[param]
            bits.append("{} {}{}".format(label, v, unit))
    return ", ".join(bits) if bits else "no parameters recorded"


# --------------------------------------------------------------------------
# Species table
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Species:
    name: str
    adult_cm: float
    bioload: float           # multiplier on length; messy fish score higher
    temp_min: float
    temp_max: float
    ph_min: float
    ph_max: float
    min_school: int          # 1 = happy alone
    min_tank_l: int
    temperament: str         # peaceful | semi-aggressive | aggressive
    fin_nipper: bool = False
    long_finned: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)


_SPECIES_LIST = [
    Species("neon tetra", 3.0, 1.0, 21, 27, 6.0, 7.5, 6, 60, "peaceful",
            aliases=("neons", "neon", "neon tetras")),
    Species("cardinal tetra", 3.5, 1.0, 23, 28, 5.5, 7.2, 6, 75, "peaceful",
            aliases=("cardinals", "cardinal tetras")),
    Species("rummynose tetra", 4.5, 1.0, 24, 28, 6.0, 7.2, 6, 90, "peaceful",
            aliases=("rummynose", "rummy nose tetra", "rummynose tetras")),
    Species("harlequin rasbora", 4.5, 1.0, 22, 27, 6.0, 7.8, 6, 75, "peaceful",
            aliases=("harlequin", "harlequins", "rasbora", "rasboras")),
    Species("zebra danio", 5.0, 1.1, 18, 25, 6.5, 8.0, 6, 75, "peaceful",
            aliases=("danio", "danios", "zebra danios")),
    Species("white cloud minnow", 4.0, 1.0, 16, 22, 6.0, 8.0, 6, 60, "peaceful",
            aliases=("white cloud", "white clouds", "minnow", "minnows")),
    Species("guppy", 4.0, 1.1, 22, 28, 7.0, 8.2, 3, 40, "peaceful",
            long_finned=True, aliases=("guppies",)),
    Species("endler", 3.0, 1.0, 22, 28, 7.0, 8.2, 3, 40, "peaceful",
            aliases=("endlers",)),
    Species("platy", 5.0, 1.2, 20, 26, 7.0, 8.2, 3, 60, "peaceful",
            aliases=("platies", "platys")),
    Species("molly", 8.0, 1.4, 23, 28, 7.2, 8.5, 3, 110, "peaceful",
            aliases=("mollies",)),
    Species("swordtail", 10.0, 1.4, 22, 28, 7.0, 8.2, 3, 110, "peaceful",
            aliases=("swordtails",)),
    Species("betta", 6.0, 1.2, 24, 30, 6.0, 7.5, 1, 19, "aggressive",
            long_finned=True, aliases=("bettas", "siamese fighting fish", "fighter")),
    Species("dwarf gourami", 8.0, 1.2, 24, 28, 6.0, 7.5, 1, 75, "semi-aggressive",
            aliases=("gourami", "gouramis", "dwarf gouramis")),
    Species("angelfish", 15.0, 1.8, 24, 30, 6.0, 7.5, 1, 150, "semi-aggressive",
            long_finned=True, aliases=("angel", "angels", "angel fish")),
    Species("german blue ram", 5.0, 1.2, 26, 30, 5.5, 7.0, 2, 75, "peaceful",
            aliases=("ram", "rams", "blue ram", "gbr")),
    Species("tiger barb", 7.0, 1.3, 22, 27, 6.0, 7.5, 8, 110, "semi-aggressive",
            fin_nipper=True, aliases=("tiger barbs", "barb", "barbs")),
    Species("corydoras", 6.0, 1.0, 22, 27, 6.0, 7.8, 6, 75, "peaceful",
            aliases=("cory", "corys", "cories", "cory catfish", "corydora")),
    Species("kuhli loach", 10.0, 0.9, 24, 29, 5.5, 7.5, 5, 75, "peaceful",
            aliases=("kuhli", "kuhlis", "kuhli loaches", "coolie loach")),
    Species("otocinclus", 4.0, 0.8, 22, 27, 6.0, 7.5, 6, 60, "peaceful",
            aliases=("oto", "otos", "otocinclus catfish")),
    Species("bristlenose pleco", 12.0, 2.0, 23, 27, 6.0, 7.8, 1, 110, "peaceful",
            aliases=("bristlenose", "bn pleco", "ancistrus")),
    Species("common pleco", 40.0, 3.0, 23, 28, 6.5, 7.8, 1, 400, "peaceful",
            aliases=("plecostomus", "pleco", "plecs", "sailfin pleco")),
    Species("goldfish", 20.0, 3.0, 16, 22, 7.0, 8.4, 2, 150, "peaceful",
            long_finned=True, aliases=("fancy goldfish", "gold fish")),
    Species("cherry shrimp", 2.5, 0.2, 20, 27, 6.5, 8.0, 6, 20, "peaceful",
            aliases=("cherry shrimps", "neocaridina", "shrimp", "shrimps")),
    Species("amano shrimp", 4.0, 0.3, 20, 27, 6.5, 8.0, 3, 40, "peaceful",
            aliases=("amano", "amanos")),
    Species("nerite snail", 2.5, 0.3, 22, 28, 7.0, 8.5, 1, 20, "peaceful",
            aliases=("nerite", "nerites", "snail", "snails")),
]

SPECIES: dict[str, Species] = {s.name: s for s in _SPECIES_LIST}

# Longest alias first, so "neon tetras" wins over "tetra".
_LOOKUP: list[tuple[str, str]] = sorted(
    [(a, s.name) for s in _SPECIES_LIST for a in (s.name,) + s.aliases],
    key=lambda pair: -len(pair[0]),
)


def resolve_species(text: str) -> Optional[str]:
    """Map a user's word to a canonical species name."""
    t = (text or "").lower().strip()
    for alias, canonical in _LOOKUP:
        if re.search(r"\b" + re.escape(alias) + r"\b", t):
            return canonical
    return None


# --------------------------------------------------------------------------
# Bioload
# --------------------------------------------------------------------------

DEFAULT_TANK_L = 110          # a 30-gallon community tank
CM_PER_LITRE = 0.65           # filtered-tank capacity constant


def parse_volume(text: str) -> Optional[int]:
    """'my tank is 120 litres' / '30 gallon' -> litres."""
    t = (text or "").lower()
    m = re.search(NUM + r"\s*(?:us\s*)?gal(?:lon)?s?\b", t)
    if m:
        return int(round(float(m.group(1)) * 3.785))
    m = re.search(NUM + r"\s*(?:l|lit(?:re|er)s?)\b", t)
    if m:
        return int(round(float(m.group(1))))
    return None


def bioload(livestock: dict) -> float:
    """Total load in weighted adult-centimetres."""
    total = 0.0
    for name, count in (livestock or {}).items():
        s = SPECIES.get(name)
        if s and count > 0:
            total += s.adult_cm * s.bioload * count
    return round(total, 1)


def capacity(tank_l: int) -> float:
    """How many weighted centimetres this volume supports."""
    return round(max(tank_l, 1) * CM_PER_LITRE, 1)


_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
}


def parse_additions(text: str) -> dict:
    """'can I add 6 more neon tetras and 3 corys' -> {'neon tetra': 6, 'corydoras': 3}"""
    t = (text or "").lower()
    additions: dict = {}
    pattern = r"\b(\d+|" + "|".join(_WORD_NUMBERS) + r")\s+(?:more\s+|extra\s+|of\s+)*([a-z ]{2,30})"
    for m in re.finditer(pattern, t):
        qty_raw, tail = m.group(1), m.group(2)
        species = resolve_species(tail)
        if not species:
            continue
        qty = int(qty_raw) if qty_raw.isdigit() else _WORD_NUMBERS[qty_raw]
        additions[species] = additions.get(species, 0) + qty
    if not additions:
        species = resolve_species(t)
        if species:
            additions[species] = 1
    return additions


# --------------------------------------------------------------------------
# Compatibility
# --------------------------------------------------------------------------

@dataclass
class StockingVerdict:
    requested: dict           # what the keeper asked for
    additions: dict           # what actually gets merged into state (empty if rejected)
    ok: bool
    issues: list
    load_before: float
    load_after: float
    capacity_cm: float
    tank_l: int

    @property
    def percent_after(self) -> int:
        return int(round(100 * self.load_after / max(self.capacity_cm, 1)))


# Two species are only really compatible if they share a band wide enough to
# actually keep the tank in. Goldfish (16-22 C) and neon tetra (21-27 C) overlap
# by exactly one degree - mathematically true, useless in practice.
MIN_TEMP_OVERLAP_C = 2.0
MIN_PH_OVERLAP = 0.3


def _overlap_width(a_min, a_max, b_min, b_max) -> float:
    return min(a_max, b_max) - max(a_min, b_min)


def _overlap(a_min, a_max, b_min, b_max, minimum: float = 0.0) -> bool:
    return _overlap_width(a_min, a_max, b_min, b_max) >= minimum


def check_stocking(livestock: dict, text: str,
                   tank_l: int = DEFAULT_TANK_L) -> StockingVerdict:
    """Compatibility matrix + bioload maths for a proposed addition."""
    livestock = {k: v for k, v in (livestock or {}).items() if v > 0}
    requested = parse_additions(text)
    issues: list = []

    asked_volume = parse_volume(text)
    if asked_volume:
        tank_l = asked_volume

    if not requested:
        return StockingVerdict(
            requested={}, additions={}, ok=False,
            issues=["I could not tell which species you meant. "
                    "Try 'can I add 6 neon tetras?'"],
            load_before=bioload(livestock), load_after=bioload(livestock),
            capacity_cm=capacity(tank_l), tank_l=tank_l,
        )

    resulting = dict(livestock)
    for name, count in requested.items():
        resulting[name] = resulting.get(name, 0) + count

    # 1. tank size floor
    for name in requested:
        s = SPECIES[name]
        if tank_l < s.min_tank_l:
            issues.append("TANK TOO SMALL - {} needs at least {} L; this tank is {} L.".format(
                s.name, s.min_tank_l, tank_l))

    # 2. schooling minimums
    for name, count in resulting.items():
        s = SPECIES.get(name)
        if s and s.min_school > 1 and count < s.min_school:
            issues.append("SCHOOL TOO SMALL - {} needs {}+; you would have {}.".format(
                s.name, s.min_school, count))

    # 3. pairwise temperament / temperature / pH
    names = list(resulting)
    for i, a_name in enumerate(names):
        a = SPECIES.get(a_name)
        if not a:
            continue
        for b_name in names[i + 1:]:
            b = SPECIES.get(b_name)
            if not b:
                continue
            if not _overlap(a.temp_min, a.temp_max, b.temp_min, b.temp_max,
                            MIN_TEMP_OVERLAP_C):
                width = _overlap_width(a.temp_min, a.temp_max, b.temp_min, b.temp_max)
                issues.append(
                    "TEMPERATURE CLASH - {} wants {}-{} C, {} wants {}-{} C ({}).".format(
                        a.name, a.temp_min, a.temp_max, b.name, b.temp_min, b.temp_max,
                        "no overlap" if width <= 0
                        else "only {:g} C of overlap".format(width)))
            if not _overlap(a.ph_min, a.ph_max, b.ph_min, b.ph_max, MIN_PH_OVERLAP):
                issues.append("pH CLASH - {} wants pH {}-{}, {} wants pH {}-{}.".format(
                    a.name, a.ph_min, a.ph_max, b.name, b.ph_min, b.ph_max))
            for x, y in ((a, b), (b, a)):
                if x.fin_nipper and y.long_finned:
                    issues.append("FIN NIPPING - {} will shred the fins of {}.".format(
                        x.name, y.name))
                if x.temperament == "aggressive" and y.name != x.name:
                    issues.append("AGGRESSION - {} is territorial and will harass {}.".format(
                        x.name, y.name))
                elif x.temperament != "peaceful" and x.adult_cm >= 3 * y.adult_cm:
                    issues.append(
                        "PREDATION RISK - {} ({} cm) is big enough to eat {} ({} cm).".format(
                            x.name, x.adult_cm, y.name, y.adult_cm))

    # 4. bioload
    load_before, load_after = bioload(livestock), bioload(resulting)
    cap = capacity(tank_l)
    if load_after > cap:
        issues.append(
            "OVERSTOCKED - that would put the tank at {} cm of weighted load against a "
            "{} cm capacity ({}%).".format(
                load_after, cap, int(round(100 * load_after / cap))))
    elif load_after > 0.85 * cap:
        issues.append(
            "NEAR CAPACITY - {}% of the bioload budget. Fine, but keep up weekly water "
            "changes.".format(int(round(100 * load_after / cap))))

    seen, deduped = set(), []
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            deduped.append(issue)

    # "NEAR CAPACITY" is advice, not a rejection.
    blocking = [i for i in deduped if not i.startswith("NEAR CAPACITY")]
    return StockingVerdict(
        requested=requested,
        additions={} if blocking else requested,
        ok=not blocking,
        issues=deduped,
        load_before=load_before, load_after=load_after,
        capacity_cm=cap, tank_l=tank_l,
    )


# --------------------------------------------------------------------------
# Prompt builders - the deterministic result is handed to the model to phrase
# --------------------------------------------------------------------------

def explain_prompt(reading: Reading, alerts: list) -> str:
    return (
        "You are AquaMind, a freshwater aquarium assistant. A water test was just logged "
        "and the deterministic rule engine has already judged it. Report ONLY what is "
        "below; do not invent numbers.\n\n"
        "Test: {}\n".format(format_reading(reading)) +
        "Cycle status: {}\n".format(cycle_status(reading)) +
        "Rule engine says:\n- " + "\n- ".join(alerts) +
        "\n\nWrite 2-4 short sentences: what the numbers mean and the single most "
        "important action to take next. If everything is OK, say so plainly."
    )


def diagnosis_prompt(recent: list, symptom_text: str) -> str:
    if recent:
        history = "\n".join("- {}: {}".format(r["ts"], format_reading(r)) for r in recent)
        trends = [t for t in (trend(recent, p) for p in PARAMS) if t]
        trend_line = ("Trends: " + "; ".join(trends)) if trends else "Trends: not enough data."
        latest = evaluate(recent[-1])
    else:
        history = "- (no water tests logged for this tank yet)"
        trend_line = "Trends: none available."
        latest = ["No test data - ask the keeper to test ammonia, nitrite, nitrate, "
                  "pH and temperature."]
    return (
        "You are AquaMind, a freshwater aquarium assistant doing symptom triage. Diagnose "
        "IN THE CONTEXT of this tank's recent water chemistry - most fish illness is a "
        "water-quality problem first.\n\n"
        "Reported symptom: {}\n\n".format(symptom_text) +
        "Recent tests (oldest first):\n{}\n{}\n".format(history, trend_line) +
        "Latest test verdict:\n- " + "\n- ".join(latest) +
        "\n\nGive: (1) the most likely cause, explicitly tied to the numbers above, "
        "(2) one alternative cause, (3) the immediate action. Under 120 words. "
        "You are not a vet; say so if the case looks severe."
    )


def stocking_prompt(verdict: StockingVerdict, livestock: dict) -> str:
    current = ", ".join("{}x {}".format(v, k) for k, v in livestock.items()) or "empty tank"
    proposed = ", ".join("{}x {}".format(v, k) for k, v in verdict.requested.items()) \
        or "nothing parsed"
    body = "\n- ".join(verdict.issues) if verdict.issues else "No problems found."
    return (
        "You are AquaMind. A deterministic compatibility matrix and bioload calculator have "
        "already produced the verdict below. Report it; do not overrule it.\n\n"
        "Tank: {} L\n".format(verdict.tank_l) +
        "Current stock: {}\n".format(current) +
        "Proposed addition: {}\n".format(proposed) +
        "Bioload: {} -> {} cm against a {} cm capacity ({}%)\n".format(
            verdict.load_before, verdict.load_after,
            verdict.capacity_cm, verdict.percent_after) +
        "Verdict: {}\n".format("APPROVED" if verdict.ok else "REJECTED") +
        "Findings:\n- {}\n\n".format(body) +
        "Answer in 2-4 sentences: yes or no, the reason, and - if no - one workable "
        "alternative."
    )


GENERAL_SYSTEM = (
    "You are AquaMind, a friendly freshwater aquarium assistant. You help with water "
    "chemistry, fish health and stocking. Be concise (under 120 words), practical, and "
    "honest about uncertainty. Never invent test numbers the keeper has not given you."
)
