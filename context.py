"""Topic 3 - trimming and filtering, with before/after evidence.

This runs in its own graph node (`prepare_context`) so that trimming is a
visible box in the diagram rather than a buried helper call.

Note what it does NOT do: it never mutates `messages`. The full history stays in
state and therefore in the checkpoint. Only `model_input` is trimmed.
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, SystemMessage, filter_messages
from langchain_core.messages.utils import trim_messages

try:
    from langchain_core.messages.utils import count_tokens_approximately
except ImportError:  # pragma: no cover - older langchain-core
    def count_tokens_approximately(messages) -> int:
        """~4 characters per token, plus 3 tokens of per-message overhead."""
        total = 0
        for m in messages:
            total += len(str(getattr(m, "content", ""))) // 4 + 3
        return total


BUDGET = 400   # deliberately small so the effect is visible in a short demo
PROFILE_TAG = "[keeper profile]"


def _key(message: BaseMessage) -> str:
    """Stable identity for a message, even when it has no id."""
    return message.id or "{}:{}".format(getattr(message, "type", "?"), id(message))


def prepare_messages(messages: list, budget: int = BUDGET):
    """Filter, then trim. Returns (messages_to_send, stats)."""
    messages = list(messages or [])
    before_n = len(messages)
    before_t = count_tokens_approximately(messages) if messages else 0

    # ---- FILTER -----------------------------------------------------------
    # `load_memory` injects a "[keeper profile] ..." system message on every
    # turn, so after ten turns there are ten near-identical copies in history.
    # Keep only the newest, and drop any empty turns.
    profile_msgs = [
        m for m in messages
        if isinstance(m, SystemMessage) and str(m.content).startswith(PROFILE_TAG)
    ]
    stale_ids = [m.id for m in profile_msgs[:-1] if m.id]
    filtered = filter_messages(messages, exclude_ids=stale_ids) if stale_ids else list(messages)
    # filter_messages only matches on id, so remove any id-less stale copies too
    newest_profile = profile_msgs[-1] if profile_msgs else None
    filtered = [
        m for m in filtered
        if not (isinstance(m, SystemMessage)
                and str(m.content).startswith(PROFILE_TAG)
                and m is not newest_profile)
    ]
    filtered = [m for m in filtered if str(getattr(m, "content", "")).strip()]
    after_filter_n = len(filtered)

    # Hoist the surviving profile message to the front. trim_messages only
    # honours include_system for a system message in position 0, and ours arrives
    # mid-conversation because add_messages appends it.
    if newest_profile in filtered:
        filtered = [newest_profile] + [m for m in filtered if m is not newest_profile]

    # ---- TRIM -------------------------------------------------------------
    try:
        kept = trim_messages(
            filtered,
            max_tokens=budget,
            token_counter=count_tokens_approximately,
            strategy="last",
            start_on="human",        # never start the model input mid-exchange
            end_on=("human", "tool"),
            include_system=True,     # keep the profile even when trimming hard
            allow_partial=False,
        )
    except Exception:
        kept = filtered[-4:]

    # A very small budget can trim everything away. The model still needs the
    # current question, so guarantee at least the last human turn.
    if not kept and filtered:
        last_human = next(
            (m for m in reversed(filtered) if getattr(m, "type", "") == "human"), None
        )
        kept = [m for m in (newest_profile, last_human) if m is not None] or filtered[-1:]

    kept_keys = {_key(m) for m in kept}
    dropped = [m for m in messages if _key(m) not in kept_keys]

    stats = {
        "messages_before": before_n,
        "messages_after_filter": after_filter_n,
        "messages_sent": len(kept),
        "messages_dropped": before_n - len(kept),
        "tokens_before": before_t,
        "tokens_after": count_tokens_approximately(kept) if kept else 0,
        "budget": budget,
        "dropped_preview": [
            "{}: {}".format(getattr(m, "type", "?"), str(m.content)[:60])
            for m in dropped
        ][:8],
    }
    return kept, stats
