# AquaMind

**A freshwater aquarium care & water-chemistry assistant, built on LangGraph.**

AquaMind logs water-test results, evaluates them against safe ranges, diagnoses
fish-health symptoms *in the context of the tank's recent chemistry history*, and
checks whether a new fish is compatible with the current stock and bioload —
remembering the keeper's name, units and experience level across every tank they own.

One tank = one thread. The keeper = one long-term profile that outlives every thread.

> **[→ Read MANUAL.md](MANUAL.md)** for setup, the interface guide, the full viva demo
> script, troubleshooting, and hosting instructions.

---

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q                        # 27 domain tests, no LLM needed
python seed.py                   # pre-load "Community Tank" with history
streamlit run app.py
```

No API key is required. The default backend is `demo`, which runs the entire graph
offline. To use a real model, copy `.env.example` to `.env`, add a key, and pick the
backend in the sidebar.

---

## Where each graded topic lives

| Requirement | Where | What to look at |
|---|---|---|
| **T1** Typed state, ≥2 nodes, ≥1 conditional edge | [`graph.py`](graph.py) — 8 nodes, `add_conditional_edges` out of `router` | **Graph tab**: `draw_ascii()` + Mermaid source |
| **T2** Non-default reducer + checkpointer + thread switching | [`state.py`](state.py) — `add_messages`, `operator.add` ×2, `merge_livestock`; `SqliteSaver` | **State tab**: the `readings` counter ticks up; sidebar thread dropdown |
| **T3** Trim + filter before the model call | [`context.py`](context.py), called from the `prepare_context` node | **Context tab**: tokens/messages before → after, dropped messages struck through |
| **T4** Short-term via checkpointer, long-term via store | [`memory.py`](memory.py) — `InMemoryStore` + JSON mirror | **Memory tab**: name given in Tank A, greeted by name in Tank B |

---

## The graph

```
START
  |
  v
load_memory        read profile from the long-term store, inject as a system message
  |
  v
prepare_context    TRIM + FILTER, record before/after stats      <- Topic 3 lives here
  |
  v
router             classify intent -> state["intent"]
  |
  +--(conditional edge)--+-- log_test  --+
  |                      +-- diagnose  --+
  |                      +-- stocking  --+
  |                      +-- general   --+
  |                                      v
  +--------------------------------> memory_write   extract & persist profile facts
                                         |
                                         v
                                        END
```

`prepare_context` is a node rather than a helper call on purpose: trimming becomes a
box in the diagram that the grader can point at.

### Four intents, four branches

| User says | Intent | Branch does |
|---|---|---|
| `ammonia 0.5, nitrite 0, nitrate 20, pH 7.4, temp 26` | `log_test` | Parse → append `Reading` → run rule engine → append `alerts` |
| `my neons are gasping at the surface` | `diagnose` | Symptom triage **cross-referenced against the last 5 readings** |
| `can I add 6 more tetras?` | `stocking` | Compatibility matrix + bioload maths against `livestock` |
| `how often should I do water changes?` | `general` | FAQ / open chat / profile capture |

---

## State channels

```python
messages:  Annotated[list[AnyMessage], add_messages]   # built-in reducer
readings:  Annotated[list[Reading], operator.add]      # append-only
alerts:    Annotated[list[str], operator.add]          # append-only
livestock: Annotated[dict, merge_livestock]            # hand-written reducer

intent / model_input / trim_stats / tank_liters        # no Annotated -> last-write-wins
```

A channel **without** a reducer is *overwritten* by whatever a node returns. A channel
**with** one is *combined*. `intent` should be overwritten — only this turn matters.
`readings` must never be overwritten, because a node returning one new reading would
otherwise destroy the tank's entire history.

---

## Layout

```
aquamind/
├── requirements.txt
├── domain.py          # pure-Python rules: safe ranges, compatibility, bioload
├── llm.py             # get_model() -> OpenAI | Gemini | DemoChatModel
├── state.py           # TypedDict + reducers            <- Topic 2
├── context.py         # trim + filter + token stats     <- Topic 3
├── memory.py          # store wrapper + JSON persistence <- Topic 4
├── graph.py           # nodes, router, edges, compile   <- Topic 1
├── app.py             # Streamlit front end
├── theme.py           # design system (Apple HIG-derived CSS)
├── seed.py            # pre-load a tank with demo history
├── test_domain.py     # unit tests for the rule engine
└── data/
    ├── checkpoints.sqlite     # short-term memory (auto-created)
    └── profiles.json          # long-term memory (auto-created)
```

---

## Design decisions worth defending

**`budget = 400` is intentionally low.** With a realistic 4000-token budget you would
have to type 30 messages before anything got trimmed and the panel would read
"0 dropped" all through the demo. It is a sidebar slider, so it can be moved live.

**Trimming does not mutate `messages`.** The full history stays in state and therefore
in the checkpoint; only `model_input` is trimmed. Permanent deletion would mean
returning `RemoveMessage(id=...)` into the `messages` channel, which `add_messages`
interprets as a delete.

**`SqliteSaver`, not `MemorySaver`.** `MemorySaver` loses everything on restart, and
Streamlit restarts constantly. The connection uses `check_same_thread=False` because
Streamlit runs the script on a worker thread.

**`InMemoryStore` is mirrored to JSON.** Otherwise long-term memory dies on restart —
the exact thing Topic 4 is meant to prove.

**`@st.cache_resource` on the graph build.** Without it every rerun rebuilds the graph
and creates a new checkpointer, which makes memory look broken.

**The LLM router has a keyword fallback.** One rate-limit error must never stop the
graph from routing. The keyword path is always compiled in.

**`draw_mermaid_png()` is avoided.** It calls the mermaid.ink web service and hangs on
flaky Wi-Fi. The app shows `draw_ascii()` plus the Mermaid *source*.

---

## Demo script (under four minutes)

**T1 — Graph.** Open the Graph tab before typing anything. "Eight nodes, typed state,
and this conditional edge out of the router."

**T2 — Reducers and threads.**
1. Thread = `Community Tank`. Type `ammonia 0.25 nitrite 0 nitrate 30 ph 7.2 temp 26`.
2. State tab: `readings` went 12 → 13, `alerts` gained an ammonia warning. "That's
   `operator.add`. If this channel had no reducer, returning one reading would have
   wiped the other twelve."
3. Type `can I add 6 neon tetras?` — `livestock` merges via the hand-written reducer.
4. Switch the dropdown to `Betta Tank`. State tab is empty. "Different `thread_id`,
   different checkpoint. The two conversations never touch."

**T3 — Trimming.** Context tab: point at the two metrics. Drag the budget slider from
400 to 1200, send another message, watch the dropped count fall.

**T4 — Memory.** In `Betta Tank`: `hi, I'm Kiran and I'm a beginner — please use
Fahrenheit`. Memory tab shows the profile. Create a new tank `Shrimp Tank`, ask
`what temperature should I keep this at?` — it answers in °F and uses the name.
"The thread is new, so short-term memory is empty. The name and unit preference came
from the store, which is keyed by `user_id`, not `thread_id`." Restart the app and
repeat to prove SQLite + JSON persistence.

---

## Likely viva questions

- **"What happens if you remove `Annotated` from `readings`?"** Every logged test
  replaces the whole history with a single-element list.
- **"Where exactly does trimming happen?"** In `prepare_context`, before the router, so
  all four branches call the model with an already-trimmed list. It writes to
  `model_input`, leaving `messages` — and therefore the checkpoint — complete.
- **"Why is the token budget so low?"** So the effect is observable in a short demo.
  It's a slider; here's 2000.
- **"How is long-term memory different from the checkpointer?"** Different key
  (`user_id` vs `thread_id`), different lifetime. Both attach at `compile()`.
- **"Does it work without an API key?"** Yes — `DemoChatModel`. Routing, reducers,
  trimming and memory are all model-independent.
