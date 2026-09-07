"""Model selection, with a zero-credit fallback.

The whole point: routing, reducers, trimming and memory are model-independent.
If the API key dies five minutes before the viva, set AQUAMIND_MODEL=demo and
every graded mechanic still runs, because the branch nodes hand the model an
already-computed deterministic verdict and only ask it to phrase the answer.
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

try:  # optional - the app runs without it
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


# --------------------------------------------------------------------------
# The offline model
# --------------------------------------------------------------------------

_FAQ: list[tuple[tuple[str, ...], str]] = [
    (("water change", "change water", "how often"),
     "Weekly, 25-30% of the volume, with dechlorinated water matched to tank "
     "temperature. Vacuum the substrate while you drain. If nitrate is climbing past "
     "40 ppm between tests, change more often rather than more deeply."),
    (("cycle", "cycling", "nitrogen"),
     "The nitrogen cycle runs ammonia -> nitrite -> nitrate. Dose ammonia to 2 ppm and "
     "wait: the tank is cycled when it clears 2 ppm ammonia and 0 nitrite within 24 "
     "hours. Never add fish while nitrite is above zero."),
    (("feed", "feeding", "how much food"),
     "Once or twice a day, only what is eaten in about a minute. Overfeeding is the "
     "most common cause of an ammonia spike. Fast the tank one day a week."),
    (("algae", "green water", "brown"),
     "Algae means excess light or excess nutrients. Cut the photoperiod to 6-7 hours, "
     "check nitrate and phosphate, and increase water changes before reaching for "
     "chemicals."),
    (("temperature", "heater", "how warm", "how hot"),
     "Most tropical community fish sit happily at 24-26 C. Keep it stable - a swing of "
     "two degrees in a day stresses fish more than a steady value slightly off target."),
    (("ph", "hardness", "kh", "gh"),
     "A stable pH beats a perfect one. Most community fish adapt to anything from 6.5 "
     "to 7.8. Chase stability, not a number, and never adjust pH with commercial "
     "'pH down' products in a stocked tank."),
    (("salt", "medication", "medicine", "treat"),
     "Test the water before medicating - most 'disease' is a water-quality problem. If "
     "you do medicate, remove carbon from the filter and follow the full course."),
    (("plant", "planted", "fertiliser", "fertilizer"),
     "Start with low-light plants (anubias, java fern, cryptocoryne), root tabs for "
     "heavy root feeders, and a liquid fertiliser dosed weekly. Plants also consume "
     "ammonia, which helps stability."),
]


class DemoChatModel(BaseChatModel):
    """Deterministic stand-in for a real chat model.

    It reads the SystemMessage the branch node just built - which already contains
    the rule engine's verdict - and renders it as prose. No network, no key, no
    latency, and the numbers it reports are the numbers the rule engine produced.
    """

    @property
    def _llm_type(self) -> str:
        return "aquamind-demo"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = self._apply_profile(self._reply(messages), self._profile(messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    # -- profile awareness -----------------------------------------------
    # Long-term memory has to be visible offline too, so the demo model reads
    # the "[keeper profile]" system message that load_memory injected and honours
    # it: it uses the keeper's name and converts to Fahrenheit when asked.

    @staticmethod
    def _profile(messages: list[BaseMessage]) -> dict:
        for m in messages:
            content = str(getattr(m, "content", ""))
            if isinstance(m, SystemMessage) and content.startswith("[keeper profile]"):
                facts = {}
                body = content[len("[keeper profile]"):].split(". Address")[0]
                for chunk in body.split(","):
                    if ":" in chunk:
                        k, v = chunk.split(":", 1)
                        facts[k.strip()] = v.strip()
                return facts
        return {}

    @staticmethod
    def _celsius_to_fahrenheit(text: str) -> str:
        def one(m):
            return "{:.0f} F".format(float(m.group(1)) * 9 / 5 + 32)

        def span(m):
            return "{:.0f}-{:.0f} F".format(
                float(m.group(1)) * 9 / 5 + 32, float(m.group(2)) * 9 / 5 + 32)

        text = re.sub(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*C\b", span, text)
        return re.sub(r"(\d+(?:\.\d+)?)\s*C\b", one, text)

    def _apply_profile(self, text: str, profile: dict) -> str:
        if profile.get("units") == "fahrenheit":
            text = self._celsius_to_fahrenheit(text)
        name = profile.get("name")
        if name and name.lower() not in text.lower():
            text = "{}, {}{}".format(name, text[:1].lower(), text[1:])
        return text

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _last_system(messages: list[BaseMessage]) -> str:
        for m in reversed(messages):
            if isinstance(m, SystemMessage):
                return str(m.content)
        return ""

    @staticmethod
    def _last_human(messages: list[BaseMessage]) -> str:
        for m in reversed(messages):
            if getattr(m, "type", "") == "human":
                return str(m.content)
        return ""

    @staticmethod
    def _bullets(block: str, marker: str) -> list[str]:
        """Pull the '- ' bullets that follow a marker line."""
        if marker not in block:
            return []
        tail = block.split(marker, 1)[1]
        out = []
        for line in tail.splitlines():
            line = line.strip()
            if line.startswith("- "):
                out.append(line[2:].strip())
            elif out and not line:
                break
        return out

    def _reply(self, messages: list[BaseMessage]) -> str:
        system = self._last_system(messages)
        human = self._last_human(messages).lower()

        # 1. a logged water test
        if "Rule engine says:" in system:
            alerts = self._bullets(system, "Rule engine says:")
            cycle = ""
            m = re.search(r"Cycle status: (.+)", system)
            if m:
                cycle = m.group(1).strip()
            worst = next((a for a in alerts if a.startswith("CRITICAL")), None) \
                or next((a for a in alerts if a.startswith(("HIGH", "LOW"))), None)
            head = "Logged. "
            if worst is None:
                head += "Everything you tested is inside its safe range."
                tail = " Keep to your normal weekly water change."
            else:
                head += worst
                tail = " Re-test in 24 hours to confirm the direction of travel."
            return "{}\nCycle status: {}.{}".format(head, cycle, tail)

        # 2. a stocking question
        if "Verdict:" in system:
            approved = "Verdict: APPROVED" in system
            findings = self._bullets(system, "Findings:")
            load = re.search(r"Bioload: ([\d.]+) -> ([\d.]+) cm against a ([\d.]+) cm "
                             r"capacity \((\d+)%\)", system)
            load_line = ""
            if load:
                load_line = " That takes the bioload to {} of {} cm ({}% of capacity).".format(
                    load.group(2), load.group(3), load.group(4))
            if approved:
                note = ""
                if findings and findings[0] != "No problems found.":
                    note = " Note: " + findings[0]
                return "Yes, that works.{}{}".format(load_line, note)
            reasons = "; ".join(findings[:2]) if findings else "it fails the compatibility check"
            return ("No - I would not add that. {}{}\nA smaller group, or a species with a "
                    "lower bioload, would fit instead.".format(reasons, load_line))

        # 3. symptom triage
        if "Reported symptom:" in system:
            symptom = ""
            m = re.search(r"Reported symptom: (.+)", system)
            if m:
                symptom = m.group(1).strip()
            verdict = self._bullets(system, "Latest test verdict:")
            bad = [v for v in verdict if v.startswith(("CRITICAL", "HIGH", "LOW"))]
            if bad:
                cause = ("Most likely cause: water quality. Your latest test shows "
                         + bad[0].split(" - ", 1)[-1])
                action = ("Immediate action: a 50% water change with dechlorinator, then "
                          "re-test in 12 hours.")
            else:
                cause = ("Most likely cause: not water chemistry - your latest test is "
                         "clean. Look at oxygenation, temperature swings or a new "
                         "arrival introducing disease.")
                action = ("Immediate action: increase surface agitation, check the heater "
                          "against a second thermometer, and observe for 24 hours.")
            alt = ("Alternative cause: a recent overfeed or a filter disturbance that "
                   "knocked back the bacterial colony.")
            return "Symptom: {}\n{}\n{}\n{}".format(symptom or "reported issue", cause, alt, action)

        # 4. general chat - keyword FAQ, then a safe default
        for keys, answer in _FAQ:
            if any(k in human for k in keys):
                return answer
        if any(k in human for k in ("hi", "hello", "hey")) and len(human) < 60:
            return ("Hello. Tell me a water test (ammonia, nitrite, nitrate, pH, temp), "
                    "describe a symptom, or ask whether a fish will fit.")
        return ("I can log a water test, triage a symptom against this tank's recent "
                "chemistry, or check whether a new fish fits your stock and bioload. "
                "Which would you like?")

    def with_structured_output(self, schema, **kwargs):  # noqa: D102
        # Deliberately unsupported: it forces the LLM router down its keyword
        # fallback path, which is exactly what we want offline.
        raise NotImplementedError("DemoChatModel does not support structured output")


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------

def available_backends() -> list[str]:
    backends = ["demo"]
    if os.getenv("OPENAI_API_KEY"):
        backends.append("openai")
    if os.getenv("GOOGLE_API_KEY"):
        backends.append("gemini")
    return backends


def get_model(backend: Optional[str] = None, temperature: float = 0.2) -> BaseChatModel:
    """Return a chat model. Falls back to DemoChatModel on any problem."""
    backend = (backend or os.getenv("AQUAMIND_MODEL") or "demo").lower()

    if backend == "openai" and os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=temperature,
            )
        except Exception as exc:  # pragma: no cover
            print("[llm] OpenAI unavailable ({}); using DemoChatModel".format(exc))

    if backend == "gemini" and os.getenv("GOOGLE_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                temperature=temperature,
            )
        except Exception as exc:  # pragma: no cover
            print("[llm] Gemini unavailable ({}); using DemoChatModel".format(exc))

    return DemoChatModel()
