"""Topic 4 - long-term memory.

The distinction that matters: the checkpointer is keyed by `thread_id` and holds
the conversation, so it is SHORT-term and per-tank. This store is keyed by
`user_id` and sits outside every thread, so it is LONG-term and per-keeper. Both
are wired in at compile().

InMemoryStore dies on restart, which would sink the one thing Topic 4 is meant
to prove, so every write is mirrored to data/profiles.json.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PROFILE_PATH = os.path.join(DATA_DIR, "profiles.json")
NS = ("profiles",)

FIELDS = ("name", "units", "experience", "tank_type")

_store: Optional[InMemoryStore] = None


# --------------------------------------------------------------------------
# Store lifecycle
# --------------------------------------------------------------------------

def get_store() -> BaseStore:
    """Return the process-wide store, hydrated from disk on first call."""
    global _store
    if _store is not None:
        return _store

    _store = InMemoryStore()
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as fh:
                for user_id, profile in (json.load(fh) or {}).items():
                    _store.put(NS, user_id, profile)
        except (json.JSONDecodeError, OSError) as exc:
            print("[memory] could not read {}: {}".format(PROFILE_PATH, exc))
    return _store


def load_profile(store: BaseStore, user_id: str) -> dict:
    item = store.get(NS, user_id)
    return dict(item.value) if item else {}


def save_profile(store: BaseStore, user_id: str, updates: dict,
                 thread_id: str = "") -> dict:
    """Merge updates into the stored profile and mirror the whole store to JSON."""
    profile = load_profile(store, user_id)
    learned = dict(profile.get("_learned_in", {}))
    for key, value in updates.items():
        if profile.get(key) != value:
            learned[key] = thread_id or "unknown"
    profile.update(updates)
    if learned:
        profile["_learned_in"] = learned

    store.put(NS, user_id, profile)

    os.makedirs(DATA_DIR, exist_ok=True)
    all_profiles = {item.key: item.value for item in store.search(NS)}
    try:
        with open(PROFILE_PATH, "w", encoding="utf-8") as fh:
            json.dump(all_profiles, fh, indent=2)
    except OSError as exc:  # pragma: no cover
        print("[memory] could not write {}: {}".format(PROFILE_PATH, exc))
    return profile


def all_profiles(store: BaseStore) -> dict:
    return {item.key: item.value for item in store.search(NS)}


def forget(store: BaseStore, user_id: str) -> None:
    """Wipe one keeper's profile - handy for rehearsing the demo."""
    store.delete(NS, user_id)
    try:
        with open(PROFILE_PATH, "w", encoding="utf-8") as fh:
            json.dump(all_profiles(store), fh, indent=2)
    except OSError:  # pragma: no cover
        pass


# --------------------------------------------------------------------------
# Fact extraction - cheap path first
# --------------------------------------------------------------------------

# Words that follow "I'm ..." but are not names.
_NOT_A_NAME = {
    "a", "an", "the", "new", "not", "just", "still", "really", "so", "very",
    "beginner", "novice", "intermediate", "advanced", "expert", "experienced",
    "sorry", "sure", "fine", "ok", "okay", "good", "back", "here", "using",
    "trying", "thinking", "looking", "going", "doing", "worried", "confused",
    "keeping", "running", "planning", "wondering", "getting", "having",
}

_NAME_PATTERNS = (
    r"\bmy name(?:'s| is)\s+([A-Za-z][A-Za-z'-]{1,20})",
    r"\bi am\s+([A-Za-z][A-Za-z'-]{1,20})",
    r"\bi'?m\s+([A-Za-z][A-Za-z'-]{1,20})",
    r"\bcall me\s+([A-Za-z][A-Za-z'-]{1,20})",
    r"\bthis is\s+([A-Za-z][A-Za-z'-]{1,20})\s+(?:here|speaking)",
)


def extract_facts(text: str) -> dict:
    """Regex/keyword extraction. Zero cost, zero latency, never fails in a demo."""
    if not text:
        return {}
    raw = str(text)
    low = raw.lower()
    facts: dict = {}

    # name
    for pattern in _NAME_PATTERNS:
        m = re.search(pattern, raw, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = m.group(1).strip()
        if candidate.lower() in _NOT_A_NAME:
            continue
        facts["name"] = candidate[:1].upper() + candidate[1:]
        break

    # unit preference
    if re.search(r"\bfahrenheit\b|\bdeg(?:rees)? f\b|\buse f\b|\bin f\b", low):
        facts["units"] = "fahrenheit"
    elif re.search(r"\bcelsius\b|\bcentigrade\b|\bdeg(?:rees)? c\b|\buse c\b", low):
        facts["units"] = "celsius"

    # experience
    if re.search(r"\bbeginner\b|\bnovice\b|\bnew to (?:this|the hobby|fishkeeping)\b"
                 r"|\bfirst tank\b|\bjust start(?:ed|ing)\b", low):
        facts["experience"] = "beginner"
    elif re.search(r"\bexpert\b|\badvanced\b|\bexperienced\b|\byears? (?:of )?"
                   r"(?:experience|in the hobby)\b|\bbeen keeping fish\b", low):
        facts["experience"] = "advanced"
    elif re.search(r"\bintermediate\b", low):
        facts["experience"] = "intermediate"

    # tank type
    for keyword, value in (
        ("planted", "planted freshwater"),
        ("community", "freshwater community"),
        ("shrimp", "shrimp tank"),
        ("cichlid", "cichlid tank"),
        ("blackwater", "blackwater"),
        ("nano", "nano tank"),
        ("biotope", "biotope"),
    ):
        if re.search(r"\b" + keyword + r"\b", low):
            facts["tank_type"] = value
            break

    return facts


def extract_and_save_facts(store: BaseStore, user_id: str, messages: list,
                           thread_id: str = "", model=None) -> dict:
    """Scan the latest turns for profile facts and persist anything new.

    Tries the LLM extractor when a model is supplied, and always falls back to
    the regex path - a rate-limit error must never cost us Topic 4.
    """
    human_text = " ".join(
        str(m.content) for m in messages if getattr(m, "type", "") == "human"
    )
    if not human_text.strip():
        return {}

    facts = extract_facts(human_text)

    if model is not None:
        try:
            facts = {**_llm_extract(model, human_text), **facts}
        except Exception:
            pass  # regex result stands

    existing = load_profile(store, user_id)
    updates = {k: v for k, v in facts.items() if v and existing.get(k) != v}
    if not updates:
        return {}
    save_profile(store, user_id, updates, thread_id=thread_id)
    return updates


def _llm_extract(model, text: str) -> dict:
    """Optional structured-output extractor. Raises on any problem; caller catches."""
    from typing import Optional as Opt

    from pydantic import BaseModel, Field

    class Profile(BaseModel):
        name: Opt[str] = Field(None, description="the keeper's first name, if stated")
        units: Opt[str] = Field(None, description="'celsius' or 'fahrenheit' if stated")
        experience: Opt[str] = Field(
            None, description="'beginner', 'intermediate' or 'advanced' if stated")
        tank_type: Opt[str] = Field(None, description="e.g. 'planted freshwater'")

    result = model.with_structured_output(Profile).invoke(
        "Extract only facts the keeper explicitly stated about themselves. "
        "Leave a field null if it was not stated.\n\n" + text
    )
    return {k: v for k, v in result.model_dump().items() if v}


def profile_sentence(profile: dict) -> str:
    """Render the profile as the system line injected by load_memory."""
    facts = ", ".join(
        "{}: {}".format(k, v) for k, v in profile.items()
        if not k.startswith("_") and v
    )
    return facts
