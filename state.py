"""Topic 2 - typed state and reducers.

Four channels carry reducers and three do not. That contrast is the whole
lesson: a channel WITHOUT a reducer is overwritten by whatever a node returns;
a channel WITH one is combined with what is already there.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from domain import Reading


def merge_livestock(left: dict, right: dict) -> dict:
    """Hand-written reducer: adds fish counts per species instead of overwriting.

    {"neon tetra": 6} + {"neon tetra": 4, "corydoras": 3}
        -> {"neon tetra": 10, "corydoras": 3}

    Negative counts subtract, so a future "I rehomed 2 tetras" node can pass
    {"neon tetra": -2}. Species that reach zero are dropped.
    """
    merged = dict(left or {})
    for species, count in (right or {}).items():
        merged[species] = merged.get(species, 0) + count
    return {k: v for k, v in merged.items() if v > 0}


class TankState(TypedDict):
    """One tank = one thread = one instance of this state."""

    # add_messages - the built-in reducer. Appends, dedupes by id, and honours
    # RemoveMessage for deletion.
    messages: Annotated[list[AnyMessage], add_messages]

    # operator.add - append-only channels. A node returns a ONE-element list and
    # the reducer concatenates it onto the history. Drop the Annotated wrapper and
    # a single new reading would destroy every previous one.
    readings: Annotated[list[Reading], operator.add]
    alerts: Annotated[list[str], operator.add]

    # a custom reducer, to show we can write our own
    livestock: Annotated[dict, merge_livestock]

    # No Annotated => default last-write-wins. Correct for these: we only care
    # about the current turn's routing decision and the current model input.
    intent: str
    model_input: list[AnyMessage]
    trim_stats: dict
    tank_liters: int
