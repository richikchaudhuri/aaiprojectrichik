# AquaMind — Operating Manual

Everything you need to install it, run it, demo it, and answer for it.

- [1. First-time setup](#1-first-time-setup)
- [2. Running it](#2-running-it)
- [3. Driving the interface](#3-driving-the-interface)
- [4. Before the viva](#4-before-the-viva)
- [5. The demo script](#5-the-demo-script)
- [6. Answers to the likely questions](#6-answers-to-the-likely-questions)
- [7. Troubleshooting](#7-troubleshooting)
- [8. Hosting it online](#8-hosting-it-online)
- [9. File map](#9-file-map)

---

## 1. First-time setup

You need Python 3.10 or newer. Check with `python --version`.

> **On this machine** Python 3.12 is installed at
> `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` but is **not on PATH** — typing
> `python` hits a Microsoft Store stub and fails. Either use that full path, or add it
> to PATH via *Settings → System → About → Advanced system settings → Environment
> Variables*.

From the project folder:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

On macOS or Linux the activate line is `source .venv/bin/activate`.

Then confirm the domain layer is sound — this needs no API key and no network:

```bash
pytest -q
```

You should see `26 passed`. If you see `ModuleNotFoundError`, the venv isn't active.

**No API key is needed.** The default backend is `demo`, which runs the entire graph
offline. To use a real model instead, copy `.env.example` to `.env`, paste in a key,
and pick `openai` or `gemini` from the sidebar.

---

## 2. Running it

Seed a tank with history first, so the panels aren't empty when you open them:

```bash
python seed.py
```

That writes 8 readings, 8 alerts and a stocked `livestock` dict into the
*Community Tank* thread. Then:

```bash
streamlit run app.py
```

It opens at <http://localhost:8501>. To stop it, press `Ctrl+C` in the terminal.

**Starting over.** Delete `data/checkpoints.sqlite` and `data/profiles.json`, then run
`python seed.py` again. That wipes every conversation and every keeper profile.

---

## 3. Driving the interface

**The sidebar is the control panel.**

| Control | What it does | Why it matters |
|---|---|---|
| `user_id` | Who the keeper is | Long-term memory is keyed by this. Change it and the profile changes. |
| `Tank` | Which thread you're in | One tank = one thread = one checkpoint. |
| `Add` / `Reset` | New tank, or a fresh copy of this one | Reset switches to a new `thread_id`; the old checkpoint is left intact. |
| `Context budget` | Token ceiling per turn | Drag it live and watch the Context panel change. |
| `Model` | `demo`, `openai`, `gemini` | `demo` needs no key and never rate-limits. |
| `LLM router` | Structured-output routing | Keyword router stays as the fallback. |
| `Forget this keeper` | Wipes the profile | Use it to rehearse the Topic 4 moment cleanly. |

**The view switch** (top right) toggles between *Conversation* — full-width chat, for
talking — and *Conversation + Evidence* — chat plus the four graded panels, for
demonstrating. Use the second one in the viva.

**Four things you can say**, one per branch of the router:

| Type this | Routes to | What happens |
|---|---|---|
| `ammonia 0.25 nitrite 0 nitrate 30 ph 7.2 temp 26` | `log_test` | Parsed, appended to `readings`, run through the rule engine |
| `my neons are gasping at the surface` | `diagnose` | Triage against the last 5 readings |
| `can I add 6 more neon tetras?` | `stocking` | Compatibility matrix + bioload maths |
| `how often should I do water changes?` | `general` | FAQ / open chat |

The parser is forgiving: `nh3=0.25`, `no2: 0`, `temp 78F` and `26C` all work.

---

## 4. Before the viva

Run this checklist the morning of, not the hour of.

1. `pytest -q` → 26 passed.
2. Delete `data/checkpoints.sqlite` and `data/profiles.json`.
3. `python seed.py` → confirm it prints `readings : 8`.
4. `streamlit run app.py`, set the view to **Conversation + Evidence**.
5. Set the backend to **demo**. Do this even if your key works — it removes the
   network from your demo entirely.
6. Walk section 5 end to end, twice.
7. Leave the browser open on the **Graph** panel.

---

## 5. The demo script

Rehearse until it runs under four minutes. Say the topic number out loud each time.

### Topic 1 — the graph (before typing anything)

Open on the **Graph** panel.

> "Eight nodes over a typed `TankState`. The conditional edge is here — `router` fans
> out to four branch nodes through `add_conditional_edges`, and all four rejoin at
> `memory_write`. Trimming is its own node, `prepare_context`, deliberately, so it's a
> box you can point at rather than a helper call buried in a branch."

### Topic 2 — reducers and threads

1. Tank = **Community Tank**. Type:
   `ammonia 0.25 nitrite 0 nitrate 30 ph 7.2 temp 26`
2. Open the **State** panel. `readings` shows **8 → 9** with a green delta.

   > "That's `operator.add`. The node returned a one-element list and the reducer
   > appended it. If this channel had no reducer, returning one reading would have
   > replaced all eight."

3. Type: `can I add 6 more neon tetras?` — `livestock` merges via the hand-written
   `merge_livestock` reducer, and the bioload bar moves.
4. Switch the sidebar tank to **Betta Tank**. The State panel is empty.

   > "Different `thread_id`, different checkpoint. The two conversations never touch."

### Topic 3 — trimming and filtering

Open the **Context** panel.

> "Before the model call this turn: 34 messages, about 1,070 tokens. After: 14 messages,
> 389 tokens, under the 400 budget. The struck-through lines are what got dropped —
> mostly stale `[keeper profile]` system messages, which is the filter step."

Now drag the **Context budget** slider to 1200, send another message, and point at the
drop count falling.

> "Same history, different budget. The trim runs in `prepare_context` before the router,
> so all four branches get an already-trimmed list."

If asked why the budget is so low: **say it is deliberate.** At a realistic 4,000 you'd
type thirty messages before anything trimmed and the panel would read zero all through
the demo.

### Topic 4 — memory

1. In **Betta Tank**, type:
   `hi, I'm Kiran and I'm a beginner — please use Fahrenheit`
2. Open the **Memory** panel — the profile is now populated, with a note saying which
   thread each fact was learned in.
3. Sidebar → type `Shrimp Tank` → **Add**.
4. Type: `what temperature should I keep this at?`

   It answers **in Fahrenheit and by name** — "Kiran, most tropical community fish sit
   happily at 75-79 F."

   > "Brand-new thread, so short-term memory is empty — the left panel proves it. The
   > name and the unit preference came from the store, which is keyed by `user_id`, not
   > `thread_id`."

5. **Optional, and it lands well:** stop the app with `Ctrl+C`, restart it, and repeat
   step 4. That proves SQLite and the JSON mirror both survive a restart.

---

## 6. Answers to the likely questions

**"What happens if you remove `Annotated` from `readings`?"**
Every logged test replaces the entire history with a single-element list. A channel
without a reducer is overwritten by whatever the node returns; a channel with one is
combined. That's the whole distinction.

**"Why is `intent` not annotated then?"**
Because it *should* be overwritten — only the current turn's routing decision matters.
Same for `model_input` and `trim_stats`. Using a reducer there would be a bug.

**"Where exactly does trimming happen?"**
In the `prepare_context` node, before the router, so all four branches call the model
with an already-trimmed list. It writes to `model_input` and leaves `messages` alone —
so the checkpoint stays complete.

**"So you're deleting conversation history?"**
No. Nothing is mutated. If I wanted true deletion I'd return `RemoveMessage(id=...)`
into the `messages` channel, which `add_messages` interprets as a delete.

**"How is long-term memory different from the checkpointer?"**
Different key, different lifetime. The checkpointer is keyed by `thread_id` and holds
the conversation. The store is keyed by `user_id` and sits outside every thread. Both
attach at the same call:
`builder.compile(checkpointer=checkpointer, store=store)`.

**"Does it work without an API key?"**
Yes — `DemoChatModel`. Routing, reducers, trimming and memory are all
model-independent, because the branch nodes compute the verdict deterministically in
`domain.py` and only ask the model to phrase it.

**"Is the router an LLM?"**
It's keyword-based by default, which is honest and fast. There's an LLM router behind a
sidebar checkbox that uses structured output — and it falls back to the keyword path on
any exception, so a rate limit can't stop the graph routing.

**"Why is the compatibility check not just an LLM prompt?"**
Because it needs to be *right* and *repeatable*. `domain.py` has 26 tests. One of them
catches a case a naive overlap check gets wrong: goldfish want 16–22 °C and neon tetras
21–27 °C, which overlap by exactly one degree. Mathematically compatible, in practice
not a tank. The rule requires at least 2 °C of shared range.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Memory "doesn't work" between messages | Graph rebuilt on every rerun → new checkpointer | `@st.cache_resource` on `build()` — already there, don't remove it |
| Everything lost on restart | `MemorySaver` instead of `SqliteSaver` | Already using `SqliteSaver`; check `data/checkpoints.sqlite` exists |
| Profile lost on restart | `InMemoryStore` with no mirror | Already mirrored to `data/profiles.json` |
| Graph panel shows an error | `grandalf` missing | `pip install grandalf` |
| `sqlite3.ProgrammingError` about threads | Missing `check_same_thread=False` | Already set in `graph.build_checkpointer()` |
| Context panel always reads 0 dropped | Budget too high for the history | Drop the slider to 400 and send a few more messages |
| `python` opens the Microsoft Store | PATH alias stub | Use the full path from section 1 |
| Port already in use | An old Streamlit is still running | `streamlit run app.py --server.port 8502` |

---

## 8. Hosting it online

The app is ready for **Streamlit Community Cloud**, which is free and reads directly
from the GitHub repo.

1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. **Create app** → **Deploy a public app from GitHub**.
3. Fill in:
   - Repository: `richikchaudhuri/aaiprojectrichik`
   - Branch: `main`
   - Main file path: `app.py`
4. Click **Deploy**. First build takes 2–4 minutes.

You'll get a URL like `https://aaiprojectrichik.streamlit.app`.

**Notes for the hosted version**

- It runs on `DemoChatModel` by default, so it works with no key and no billing.
- To use a real model, open the app's **Settings → Secrets** in the Streamlit dashboard
  and add:
  ```toml
  OPENAI_API_KEY = "sk-..."
  AQUAMIND_MODEL = "openai"
  ```
  Never commit a key to the repo.
- Community Cloud has an **ephemeral filesystem**. `data/checkpoints.sqlite` and
  `data/profiles.json` are recreated on each cold start, so memory persists during a
  session but resets when the app sleeps. That's fine for a demo; say so if asked. For
  true persistence you'd point `SqliteSaver` at Postgres via
  `langgraph-checkpoint-postgres`.
- If the repo is private, Community Cloud can still deploy it — it asks for extra
  GitHub permissions during sign-in.

---

## 9. File map

```
aquamind/
├── domain.py          pure-Python rules: parsing, safe ranges, species table,
│                      compatibility matrix, bioload maths  (no LLM, no LangGraph)
├── state.py           TankState + the four reducers            ← Topic 2
├── context.py         filter → trim → before/after stats       ← Topic 3
├── memory.py          store wrapper, JSON mirror, fact extraction ← Topic 4
├── graph.py           8 nodes, the conditional edge, compile   ← Topic 1
├── llm.py             get_model() → OpenAI | Gemini | DemoChatModel
├── app.py             Streamlit front end
├── theme.py           the design system (Apple HIG-derived CSS)
├── seed.py            pre-load a tank with demo history
├── test_domain.py     26 tests for the rule engine
├── .streamlit/
│   └── config.toml    pinned light theme
└── data/
    ├── checkpoints.sqlite   short-term memory (auto-created, gitignored)
    └── profiles.json        long-term memory (auto-created, gitignored)
```

**Where each graded topic lives**

| Topic | Code | Panel |
|---|---|---|
| T1 typed state, ≥2 nodes, ≥1 conditional edge | `graph.py` | Graph |
| T2 non-default reducer + checkpointer + threads | `state.py`, `graph.build_checkpointer()` | State |
| T3 trim + filter before the model call | `context.py`, `prepare_context` node | Context |
| T4 short-term checkpointer + long-term store | `memory.py` | Memory |
