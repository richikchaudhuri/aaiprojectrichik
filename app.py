"""AquaMind - Streamlit front end.

The conversation is the product; the four evidence panels are the proof. Both
are on one screen so a grader can watch a mechanic fire and immediately see the
state it changed.

Visual design lives in theme.py.
"""
from __future__ import annotations

import streamlit as st
from langchain_core.messages import HumanMessage

import domain
import llm
import memory
import theme
from context import BUDGET
from graph import BRANCHES, compile_graph, describe_graph, make_config, read_state

st.set_page_config(
    page_title="AquaMind",
    page_icon="🐟",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(theme.css(), unsafe_allow_html=True)

DEFAULT_THREADS = ["Community Tank", "Betta Tank", "Shrimp Tank"]

STARTERS = [
    ("Log a water test", "ammonia 0.25 nitrite 0 nitrate 30 ph 7.2 temp 26"),
    ("Report a symptom", "my neons are gasping at the surface"),
    ("Check stocking", "can I add 6 more neon tetras?"),
    ("Ask anything", "how often should I do water changes?"),
]


# --------------------------------------------------------------------------
# Build once. Without @st.cache_resource every rerun rebuilds the graph, which
# means a NEW checkpointer, which makes memory look broken.
# --------------------------------------------------------------------------

@st.cache_resource
def build(backend: str, use_llm_router: bool):
    return compile_graph(backend=backend, use_llm_router=use_llm_router)


def init_session():
    ss = st.session_state
    ss.setdefault("threads", list(DEFAULT_THREADS))
    ss.setdefault("thread_id", DEFAULT_THREADS[0])
    ss.setdefault("user_id", "keeper-1")
    ss.setdefault("budget", BUDGET)
    ss.setdefault("backend", "demo")
    ss.setdefault("use_llm_router", False)
    ss.setdefault("view", "Conversation + Evidence")
    ss.setdefault("prev_counts", {})     # thread -> readings count before last turn
    ss.setdefault("pending", None)       # queued prompt from a starter chip


init_session()


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Keeper")
    st.text_input("user_id", key="user_id", label_visibility="collapsed",
                  help="Long-term memory is keyed by this, not by the tank.")
    st.caption("Long-term memory is keyed by the keeper.")

    st.markdown("### Tank")
    st.selectbox("thread_id", st.session_state.threads, key="thread_id",
                 label_visibility="collapsed",
                 help="One tank = one thread = one checkpoint.")
    st.caption("One tank = one thread = one checkpoint.")

    new_tank = st.text_input("New tank", placeholder="Add a tank…",
                             label_visibility="collapsed")
    c1, c2 = st.columns(2)
    if c1.button("Add", use_container_width=True) and new_tank.strip():
        name = new_tank.strip()
        if name not in st.session_state.threads:
            st.session_state.threads.append(name)
        st.session_state.thread_id = name
        st.rerun()
    if c2.button("Reset", use_container_width=True,
                 help="Switches to a fresh thread_id. The old checkpoint is untouched."):
        base = st.session_state.thread_id.split(" (v")[0]
        n = sum(1 for t in st.session_state.threads if t.startswith(base)) + 1
        fresh = "{} (v{})".format(base, n)
        st.session_state.threads.append(fresh)
        st.session_state.thread_id = fresh
        st.rerun()

    st.markdown("### Context budget")
    st.slider("token_budget", 100, 2000, key="budget", step=50,
              label_visibility="collapsed",
              help="Deliberately low so trimming is visible in a short demo.")
    st.caption("Tokens allowed through to the model each turn.")

    st.markdown("### Model")
    st.selectbox("backend", llm.available_backends(), key="backend",
                 label_visibility="collapsed",
                 help="'demo' runs the entire graph with no API key.")
    st.checkbox("LLM router", key="use_llm_router",
                help="Structured-output routing, with the keyword router kept as fallback.")

    st.markdown("### Danger zone")
    if st.button("Forget this keeper", use_container_width=True):
        _, _, _, _store = build(st.session_state.backend, st.session_state.use_llm_router)
        memory.forget(_store, st.session_state.user_id)
        st.toast("Profile cleared for {}".format(st.session_state.user_id))


graph, model, checkpointer, store = build(
    st.session_state.backend, st.session_state.use_llm_router
)
config = make_config(
    st.session_state.thread_id, st.session_state.user_id, st.session_state.budget
)


# --------------------------------------------------------------------------
# Turn handling
# --------------------------------------------------------------------------

def run_turn(text: str) -> None:
    snap = read_state(graph, config)
    st.session_state.prev_counts[st.session_state.thread_id] = len(
        snap.get("readings", []))
    try:
        graph.invoke({"messages": [HumanMessage(content=text)]}, config)
    except Exception as exc:
        st.session_state.last_error = str(exc)


if st.session_state.pending:
    queued, st.session_state.pending = st.session_state.pending, None
    run_turn(queued)

snapshot = read_state(graph, config)
messages = [m for m in snapshot.get("messages", [])
            if getattr(m, "type", "") in ("human", "ai")]


# --------------------------------------------------------------------------
# Masthead
# --------------------------------------------------------------------------

st.markdown(theme.masthead("Freshwater water-chemistry & fish-care assistant"),
            unsafe_allow_html=True)

head_left, head_right = st.columns([3, 1.15])
with head_left:
    stats = snapshot.get("trim_stats", {})
    st.markdown(theme.chips([
        ("Tank", st.session_state.thread_id, True),
        ("Keeper", st.session_state.user_id),
        ("Model", getattr(model, "_llm_type", "llm")),
        ("Budget", "{} tokens".format(st.session_state.budget)),
        ("Readings", len(snapshot.get("readings", []))),
    ]), unsafe_allow_html=True)
with head_right:
    st.segmented_control(
        "View", ["Conversation", "Conversation + Evidence"],
        key="view", label_visibility="collapsed",
    )

if st.session_state.get("last_error"):
    st.error("Graph error: {}".format(st.session_state.pop("last_error")))

focus = st.session_state.view == "Conversation"


# --------------------------------------------------------------------------
# Conversation
# --------------------------------------------------------------------------

def render_thread(height: int) -> None:
    with st.container(height=height, border=False, key="thread"):
        if not messages:
            st.markdown(theme.empty_state(
                "🐟", "A new tank",
                "Log a water test, describe a symptom, or ask whether a fish will "
                "fit. Each tank keeps its own conversation."
            ), unsafe_allow_html=True)
            cols = st.columns(len(STARTERS))
            for col, (label, prompt_text) in zip(cols, STARTERS):
                if col.button(label, use_container_width=True,
                              key="starter-{}".format(label)):
                    st.session_state.pending = prompt_text
                    st.rerun()
            return
        for i, m in enumerate(messages):
            role = "user" if m.type == "human" else "assistant"
            with st.container(key="bubble-{}-{}".format(role, i)):
                st.markdown(str(m.content))


if focus:
    chat_area = st.container()
    evidence_area = None
else:
    chat_area, evidence_area = st.columns([1.3, 1], gap="large")

with chat_area:
    render_thread(560 if focus else 520)
    if prompt := st.chat_input("Message AquaMind…"):
        run_turn(prompt)
        st.rerun()


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------

def render_evidence() -> None:
    tab_graph, tab_state, tab_context, tab_memory = st.tabs(
        ["Graph", "State", "Context", "Memory"]
    )

    # ---- Topic 1 -----------------------------------------------------
    with tab_graph:
        st.markdown(theme.note(
            "<b>Topic 1.</b> Eight nodes over a typed <code>TankState</code>, with one "
            "conditional edge: <code>router</code> fans out to <code>{}</code> via "
            "<code>add_conditional_edges</code>, and every branch rejoins at "
            "<code>memory_write</code>.".format("</code>, <code>".join(BRANCHES))
        ), unsafe_allow_html=True)
        ascii_art, mermaid = describe_graph(graph)
        st.code(ascii_art, language="text")
        with st.expander("Mermaid source"):
            st.code(mermaid, language="text")
            st.caption("draw_mermaid_png() is avoided on purpose — it calls the "
                       "mermaid.ink web service and hangs on flaky Wi-Fi.")

    # ---- Topic 2 -----------------------------------------------------
    with tab_state:
        readings = snapshot.get("readings", [])
        alerts = snapshot.get("alerts", [])
        livestock = snapshot.get("livestock", {})
        prev = st.session_state.prev_counts.get(st.session_state.thread_id)

        c1, c2, c3 = st.columns(3)
        c1.metric("readings", len(readings),
                  delta=(len(readings) - prev) if prev is not None else None)
        c2.metric("alerts", len(alerts))
        c3.metric("intent", snapshot.get("intent", "—"))

        if prev is not None and len(readings) != prev:
            st.success(
                "`readings`: {} → {} — `operator.add` appended {}. Without the reducer, "
                "returning one reading would have replaced all {}.".format(
                    prev, len(readings), len(readings) - prev, prev))

        st.markdown(theme.eyebrow("readings · Annotated[list[Reading], operator.add]"),
                    unsafe_allow_html=True)
        if readings:
            st.dataframe(readings, use_container_width=True, hide_index=True,
                         height=min(38 * len(readings) + 38, 260))
        else:
            st.caption("empty — no tests logged in this thread")

        st.markdown(theme.eyebrow("livestock · Annotated[dict, merge_livestock]"),
                    unsafe_allow_html=True)
        if livestock:
            st.json(livestock)
            load = domain.bioload(livestock)
            cap = domain.capacity(snapshot.get("tank_liters") or domain.DEFAULT_TANK_L)
            st.progress(min(load / cap, 1.0), text="bioload {} / {} cm ({}%)".format(
                load, cap, int(round(100 * load / cap))))
        else:
            st.caption("empty")

        st.markdown(theme.eyebrow("alerts · Annotated[list[str], operator.add]"),
                    unsafe_allow_html=True)
        for a in alerts[-5:]:
            (st.error if a.startswith("CRITICAL") else
             st.warning if a.startswith(("HIGH", "LOW")) else st.success)(a)
        if not alerts:
            st.caption("empty")

        st.markdown(theme.note(
            "<code>intent</code>, <code>model_input</code>, <code>trim_stats</code> and "
            "<code>tank_liters</code> carry no <code>Annotated</code> wrapper, so they are "
            "last-write-wins — correct here, because only this turn's value matters."
        ), unsafe_allow_html=True)

    # ---- Topic 3 -----------------------------------------------------
    with tab_context:
        stats = snapshot.get("trim_stats", {})
        if not stats:
            st.info("Send a message — `prepare_context` fills this in on every turn.")
        else:
            c1, c2 = st.columns(2)
            c1.metric("tokens sent", stats["tokens_after"],
                      delta=stats["tokens_after"] - stats["tokens_before"])
            c2.metric("messages sent", stats["messages_sent"],
                      delta=-stats["messages_dropped"] if stats["messages_dropped"] else 0)

            used = stats["tokens_after"] / max(stats["budget"], 1)
            st.progress(min(used, 1.0), text="{} of {} tokens used".format(
                stats["tokens_after"], stats["budget"]))

            st.markdown(theme.note(
                "<b>Filter</b> — stale <code>[keeper profile]</code> system messages and "
                "empty turns removed: {} → {} messages.<br>"
                "<b>Trim</b> — <code>trim_messages(strategy='last', start_on='human', "
                "include_system=True)</code> cut that to {}.".format(
                    stats["messages_before"], stats["messages_after_filter"],
                    stats["messages_sent"])
            ), unsafe_allow_html=True)

            if stats["dropped_preview"]:
                st.markdown(theme.eyebrow("dropped before the model call"),
                            unsafe_allow_html=True)
                for line in stats["dropped_preview"]:
                    st.markdown(theme.dropped_line(line.replace("\n", " ")),
                                unsafe_allow_html=True)
            else:
                st.caption("Nothing dropped this turn — lower the budget to force it.")

            st.markdown(theme.note(
                "<code>messages</code> is never mutated. The full history stays in state "
                "and in the checkpoint; only <code>model_input</code> is trimmed."
            ), unsafe_allow_html=True)

    # ---- Topic 4 -----------------------------------------------------
    with tab_memory:
        left, right = st.columns(2)
        with left:
            st.markdown(theme.eyebrow("short-term · SqliteSaver · thread_id"),
                        unsafe_allow_html=True)
            st.code("thread_id = {!r}".format(st.session_state.thread_id),
                    language="python")
            st.metric("messages in this thread", len(snapshot.get("messages", [])))
            try:
                n = sum(1 for _ in checkpointer.list(config))
            except Exception:
                n = "—"
            st.metric("checkpoints written", n)
        with right:
            st.markdown(theme.eyebrow("long-term · store + JSON · user_id"),
                        unsafe_allow_html=True)
            profile = memory.load_profile(store, st.session_state.user_id)
            if profile:
                st.json({k: v for k, v in profile.items() if not k.startswith("_")})
                learned = profile.get("_learned_in", {})
                if learned:
                    st.caption("Learned in: " + " · ".join(
                        "{} ← {}".format(k, v) for k, v in learned.items()))
            else:
                st.caption("No profile yet. Try: “hi, I'm Kiran and I'm a beginner — "
                           "please use Fahrenheit”.")

        st.markdown(theme.note(
            "Switching tanks changes the panel on the left and leaves the one on the "
            "right alone. Different key, different lifetime — and both attach at the "
            "same call: <code>builder.compile(checkpointer=checkpointer, store=store)</code>."
        ), unsafe_allow_html=True)


if evidence_area is not None:
    with evidence_area:
        render_evidence()
else:
    with st.expander("Evidence panels — Topics 1–4"):
        render_evidence()
