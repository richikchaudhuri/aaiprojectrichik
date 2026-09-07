"""AquaMind design system.

Follows Apple's Human Interface Guidelines as closely as Streamlit allows:

* **Deference** - the chrome recedes, the conversation is the content.
* **Clarity** - one accent colour, hairline separators, generous negative space.
* **Depth** - soft elevation and translucent materials instead of hard borders.

Type: real San Francisco on Apple hardware, Inter as the substitute elsewhere
(Windows has no SF Pro, and Inter is metrically the closest widely-available face).
Spacing follows an 8-point grid. Radii follow Apple's continuous-corner scale.
"""
from __future__ import annotations

import html as _html

# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------

TOKENS = {
    # Apple system palette, light appearance
    "bg": "#f5f5f7",           # the signature Apple grey
    "surface": "#ffffff",
    "surface_alt": "#fbfbfd",
    "text": "#1d1d1f",
    "text_secondary": "#6e6e73",
    "text_tertiary": "#86868b",
    "separator": "rgba(0, 0, 0, 0.08)",
    "separator_strong": "rgba(0, 0, 0, 0.14)",
    "accent": "#0071e3",
    "accent_hover": "#0077ed",
    "green": "#1d9d5c",
    "amber": "#b25000",
    "red": "#d70015",
    "radius_lg": "18px",
    "radius_md": "12px",
    "radius_sm": "8px",
}

FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", '
    'Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
)
MONO_STACK = (
    '"SF Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, '
    '"Cascadia Mono", monospace'
)


def css() -> str:
    t = dict(TOKENS, font=FONT_STACK, mono=MONO_STACK)
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {{
  --am-bg: {bg};
  --am-surface: {surface};
  --am-surface-alt: {surface_alt};
  --am-text: {text};
  --am-text-2: {text_secondary};
  --am-text-3: {text_tertiary};
  --am-sep: {separator};
  --am-sep-2: {separator_strong};
  --am-accent: {accent};
  --am-green: {green};
  --am-amber: {amber};
  --am-red: {red};
  --am-r-lg: {radius_lg};
  --am-r-md: {radius_md};
  --am-r-sm: {radius_sm};
}}

/* ---------- Foundations ------------------------------------------------ */

html, body, .stApp, button, input, textarea, select {{
  font-family: {font} !important;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}}
/* Never override Streamlit's icon font - Material glyphs are ligatures, and a
   text font renders them as the literal word ("arrow_right"). */
[data-testid="stIconMaterial"], .material-icons, [class*="material-symbols"] {{
  font-family: "Material Symbols Rounded", "Material Icons" !important;
}}

.stApp {{ background: var(--am-bg); color: var(--am-text); }}

/* Full-bleed: reclaim Streamlit's default gutters and max-width. */
.block-container, [data-testid="stMainBlockContainer"] {{
  max-width: 100% !important;
  padding: 1.25rem 2.25rem 1.5rem !important;
}}

/* Streamlit's top toolbar and the deploy button are chrome we don't need. */
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], #MainMenu, footer {{ display: none !important; }}
[data-testid="stHeader"] {{ background: transparent; height: 0; }}

h1, h2, h3, h4 {{ color: var(--am-text); letter-spacing: -0.021em; font-weight: 600; }}
h1 {{ font-size: 2.6rem !important; line-height: 1.08; letter-spacing: -0.028em; }}
h2 {{ font-size: 1.55rem !important; }}
h3 {{ font-size: 1.2rem !important; }}
p, li, .stMarkdown {{ font-size: 1.02rem; line-height: 1.55; }}

code, kbd, pre, .stCode {{ font-family: {mono} !important; }}
code {{
  background: rgba(0,0,0,0.045); color: #b3261e;
  padding: 0.12em 0.4em; border-radius: 5px; font-size: 0.88em;
}}

/* ---------- Masthead --------------------------------------------------- */

.am-masthead {{
  display: flex; align-items: baseline; gap: 14px;
  padding: 2px 0 14px; margin-bottom: 10px;
  border-bottom: 1px solid var(--am-sep);
}}
.am-wordmark {{
  font-size: 1.65rem; font-weight: 600; letter-spacing: -0.024em;
  color: var(--am-text); margin: 0;
}}
.am-tagline {{ font-size: 0.95rem; color: var(--am-text-3); }}

.am-chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 18px; }}
.am-chip {{
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--am-surface); border: 1px solid var(--am-sep);
  border-radius: 980px; padding: 5px 13px;
  font-size: 0.83rem; color: var(--am-text-2); white-space: nowrap;
}}
.am-chip b {{ color: var(--am-text); font-weight: 600; }}
.am-chip-accent {{ color: #fff; background: var(--am-accent); border-color: transparent; }}
.am-chip-accent b {{ color: #fff; }}

/* ---------- Conversation ----------------------------------------------- */

/* The scroll container from st.container(height=..., key="thread"). */
div[class*="st-key-thread"] {{
  background: var(--am-surface);
  border: 1px solid var(--am-sep);
  border-radius: var(--am-r-lg);
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 8px 28px rgba(0,0,0,0.05);
  padding: 18px 20px 6px;
  margin-bottom: 14px;
}}
div[class*="st-key-thread"]::-webkit-scrollbar {{ width: 8px; }}
div[class*="st-key-thread"]::-webkit-scrollbar-thumb {{
  background: rgba(0,0,0,0.16); border-radius: 4px;
}}
div[class*="st-key-thread"]::-webkit-scrollbar-track {{ background: transparent; }}

/* Bubbles. Keys come from st.container(key="bubble-<role>-<i>"), which
   Streamlit turns into a stable `st-key-...` class. */
div[class*="st-key-bubble-"] {{ margin-bottom: 10px; }}

/* Structure is: .st-key-bubble-* (flex column)
                   > [data-testid=stElementContainer]
                     > [data-testid=stMarkdown]  <- the bubble itself       */

div[class*="st-key-bubble-user-"] {{ align-items: flex-end !important; }}
div[class*="st-key-bubble-user-"] > [data-testid="stElementContainer"] {{
  width: fit-content !important; max-width: 76%;
}}
div[class*="st-key-bubble-user-"] [data-testid="stMarkdown"] {{
  background: var(--am-accent);
  padding: 11px 17px; border-radius: 20px 20px 6px 20px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.10);
}}
div[class*="st-key-bubble-user-"] [data-testid="stMarkdown"] * {{
  color: #ffffff !important;
}}
div[class*="st-key-bubble-user-"] code {{
  background: rgba(255,255,255,0.22) !important;
}}

div[class*="st-key-bubble-assistant-"] {{ align-items: flex-start !important; }}
div[class*="st-key-bubble-assistant-"] > [data-testid="stElementContainer"] {{
  width: fit-content !important; max-width: 84%;
}}
div[class*="st-key-bubble-assistant-"] [data-testid="stMarkdown"] {{
  background: #ffffff; color: var(--am-text);
  border: 1px solid var(--am-sep);
  padding: 11px 17px; border-radius: 20px 20px 20px 6px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}}

/* Empty state */
.am-empty {{ text-align: center; padding: 52px 24px 8px; }}
.am-empty-glyph {{ font-size: 3.2rem; line-height: 1; margin-bottom: 14px; }}
.am-empty h3 {{ margin: 0 0 6px; font-size: 1.3rem !important; }}
.am-empty p {{ color: var(--am-text-2); margin: 0 auto; max-width: 30rem; }}

/* ---------- Composer --------------------------------------------------- */

[data-testid="stChatInput"] {{
  background: var(--am-surface) !important;
  border: 1px solid var(--am-sep-2) !important;
  border-radius: 980px !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  padding: 2px 6px 2px 10px !important;
  transition: border-color .15s ease, box-shadow .15s ease;
}}
[data-testid="stChatInput"]:focus-within {{
  border-color: var(--am-accent) !important;
  box-shadow: 0 0 0 4px rgba(0,113,227,0.14);
}}
[data-testid="stChatInput"] textarea {{ font-size: 1.02rem !important; }}
[data-testid="stChatInput"] textarea::placeholder {{ color: var(--am-text-3) !important; }}

/* ---------- Controls --------------------------------------------------- */

.stButton > button {{
  border-radius: 980px; border: 1px solid var(--am-sep-2);
  background: var(--am-surface); color: var(--am-text);
  font-weight: 500; font-size: 0.92rem; padding: 0.44rem 1.05rem;
  transition: background .15s ease, border-color .15s ease, transform .06s ease;
}}
.stButton > button:hover {{ border-color: var(--am-accent); color: var(--am-accent); }}
.stButton > button:active {{ transform: scale(0.985); }}
.stButton > button[kind="primary"] {{
  background: var(--am-accent); border-color: transparent; color: #fff;
}}

/* Segmented control - the Apple pill group */
[data-testid="stSegmentedControl"] {{ background: transparent; }}
[data-testid="stSegmentedControl"] button {{
  border-radius: 980px !important; font-weight: 500; font-size: 0.9rem;
}}

/* Tabs, restyled as a segmented control. Streamlit >=1.60 renders these with
   react-aria roles; older builds use baseweb. Both are covered. */
.stTabs [role="tablist"], .stTabs [data-baseweb="tab-list"] {{
  gap: 2px; background: rgba(0,0,0,0.045); padding: 3px;
  border-radius: 11px; border: none; width: fit-content;
}}
.stTabs [role="tab"], .stTabs [data-baseweb="tab-list"] button {{
  border-radius: 8px; padding: 6px 16px; font-size: 0.9rem; font-weight: 500;
  color: var(--am-text-2); background: transparent; border: none;
  cursor: pointer; transition: background .15s ease, color .15s ease;
}}
.stTabs [role="tab"][aria-selected="true"],
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
  background: var(--am-surface); color: var(--am-text);
  box-shadow: 0 1px 3px rgba(0,0,0,0.10);
}}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{
  display: none !important;
}}
.stTabs [role="tabpanel"], .stTabs [data-testid="stTabsPanel"] {{ padding-top: 16px; }}

/* Inputs */
[data-baseweb="input"], [data-baseweb="select"] > div, .stTextInput input {{
  border-radius: var(--am-r-sm) !important; border-color: var(--am-sep-2) !important;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {{
  border-color: var(--am-accent) !important;
  box-shadow: 0 0 0 3px rgba(0,113,227,0.13) !important;
}}

/* Sliders and metrics */
[data-testid="stSlider"] [role="slider"] {{ box-shadow: 0 1px 4px rgba(0,0,0,0.22); }}
[data-testid="stMetric"] {{
  background: var(--am-surface); border: 1px solid var(--am-sep);
  border-radius: var(--am-r-md); padding: 14px 16px;
}}
[data-testid="stMetricLabel"] {{
  font-size: 0.78rem !important; text-transform: uppercase;
  letter-spacing: 0.055em; color: var(--am-text-3) !important; font-weight: 600;
}}
[data-testid="stMetricValue"] {{
  font-size: 2rem !important; font-weight: 600; letter-spacing: -0.02em;
}}

/* Panels, alerts, tables */
[data-testid="stExpander"] {{
  border: 1px solid var(--am-sep); border-radius: var(--am-r-md);
  background: var(--am-surface);
}}
[data-testid="stAlert"] {{ border-radius: var(--am-r-md); border: none; }}
[data-testid="stDataFrame"] {{
  border-radius: var(--am-r-md); overflow: hidden; border: 1px solid var(--am-sep);
}}
[data-testid="stJson"] {{
  background: var(--am-surface-alt) !important; border: 1px solid var(--am-sep);
  border-radius: var(--am-r-md); padding: 10px 12px;
}}
.stCode, pre {{
  border-radius: var(--am-r-md) !important; border: 1px solid var(--am-sep) !important;
  font-size: 0.82rem !important;
}}
hr {{ border-color: var(--am-sep); }}

/* ---------- Sidebar ---------------------------------------------------- */

[data-testid="stSidebar"] {{
  background: rgba(251,251,253,0.86);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-right: 1px solid var(--am-sep);
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.6rem !important; }}
[data-testid="stSidebar"] h3 {{
  font-size: 0.76rem !important; text-transform: uppercase;
  letter-spacing: 0.075em; color: var(--am-text-3); font-weight: 600;
  margin: 1.5rem 0 0.4rem;
}}
[data-testid="stSidebar"] label {{ font-size: 0.88rem !important; }}

/* ---------- Evidence panel -------------------------------------------- */

.am-panel {{
  background: var(--am-surface); border: 1px solid var(--am-sep);
  border-radius: var(--am-r-lg); padding: 18px 20px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 8px 28px rgba(0,0,0,0.05);
}}
.am-note {{
  font-size: 0.9rem; color: var(--am-text-2); line-height: 1.5;
  background: var(--am-surface-alt); border: 1px solid var(--am-sep);
  border-left: 3px solid var(--am-accent);
  border-radius: var(--am-r-sm); padding: 10px 14px; margin: 10px 0;
}}
.am-eyebrow {{
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
  font-weight: 600; color: var(--am-text-3); margin: 18px 0 6px;
}}
.am-dropped {{
  font-family: {mono}; font-size: 0.78rem; color: var(--am-text-3);
  text-decoration: line-through; padding: 3px 0;
  border-bottom: 1px solid var(--am-sep);
}}
</style>
""".format(**t)


# --------------------------------------------------------------------------
# Small render helpers
# --------------------------------------------------------------------------

def masthead(subtitle: str) -> str:
    return (
        '<div class="am-masthead">'
        '<span class="am-wordmark">AquaMind</span>'
        '<span class="am-tagline">{}</span>'
        '</div>'.format(_html.escape(subtitle))
    )


def chips(items: list) -> str:
    """items: list of (label, value, accent?) tuples."""
    out = ['<div class="am-chips">']
    for item in items:
        label, value = item[0], item[1]
        accent = len(item) > 2 and item[2]
        out.append('<span class="am-chip{}">{}&nbsp;<b>{}</b></span>'.format(
            " am-chip-accent" if accent else "",
            _html.escape(str(label)), _html.escape(str(value))))
    out.append("</div>")
    return "".join(out)


def empty_state(glyph: str, title: str, body: str) -> str:
    return (
        '<div class="am-empty"><div class="am-empty-glyph">{}</div>'
        '<h3>{}</h3><p>{}</p></div>'
    ).format(glyph, _html.escape(title), _html.escape(body))


def note(text_html: str) -> str:
    return '<div class="am-note">{}</div>'.format(text_html)


def eyebrow(text: str) -> str:
    return '<div class="am-eyebrow">{}</div>'.format(_html.escape(text))


def dropped_line(text: str) -> str:
    return '<div class="am-dropped">{}</div>'.format(_html.escape(text))
