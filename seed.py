"""Pre-load 'Community Tank' so the demo does not open onto empty panels.

Run once before the viva:   python seed.py

It drives the real graph with the demo model, so the readings, alerts, livestock
and message history are all produced by the same code path the grader will watch.
"""
from __future__ import annotations

import argparse

from langchain_core.messages import HumanMessage

from graph import compile_graph, make_config, read_state

SCRIPT = [
    "hi, this is a 110 litre freshwater community tank",
    "ammonia 0 nitrite 0 nitrate 10 ph 7.2 temp 25",
    "ammonia 0 nitrite 0 nitrate 15 ph 7.2 temp 25",
    "ammonia 0.25 nitrite 0 nitrate 20 ph 7.1 temp 26",
    "ammonia 0 nitrite 0 nitrate 25 ph 7.2 temp 26",
    "how often should I do water changes?",
    "ammonia 0 nitrite 0 nitrate 30 ph 7.3 temp 26",
    "can I add 6 neon tetras?",
    "ammonia 0 nitrite 0 nitrate 35 ph 7.3 temp 26",
    "can I add 6 corydoras?",
    "ammonia 0 nitrite 0 nitrate 40 ph 7.2 temp 27",
    "ammonia 0 nitrite 0 nitrate 45 ph 7.2 temp 27",
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed a tank with demo history.")
    ap.add_argument("--thread", default="Community Tank")
    ap.add_argument("--user", default="keeper-1")
    ap.add_argument("--budget", type=int, default=400)
    args = ap.parse_args()

    graph, model, _, _ = compile_graph(backend="demo")
    config = make_config(args.thread, args.user, args.budget)

    print("Seeding {!r} for {!r}…".format(args.thread, args.user))
    for i, line in enumerate(SCRIPT, 1):
        graph.invoke({"messages": [HumanMessage(content=line)]}, config)
        print("  {:>2}/{}  {}".format(i, len(SCRIPT), line[:60]))

    final = read_state(graph, config)
    stats = final.get("trim_stats", {})
    print("\nDone.")
    print("  readings : {}".format(len(final.get("readings", []))))
    print("  alerts   : {}".format(len(final.get("alerts", []))))
    print("  livestock: {}".format(final.get("livestock", {})))
    print("  messages : {}".format(len(final.get("messages", []))))
    print("  last turn sent {} of {} messages ({} of {} tokens)".format(
        stats.get("messages_sent"), stats.get("messages_before"),
        stats.get("tokens_after"), stats.get("tokens_before")))
    print("\nNow run:  streamlit run app.py")


if __name__ == "__main__":
    main()
