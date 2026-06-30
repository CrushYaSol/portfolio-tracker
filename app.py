"""
app.py — THE EXCHANGE  (Bram's underground terminal)
A cyberpunk black-market themed portfolio tracker. A shadowy broker, "Bram",
watches over a bank of monitors with robotic tentacles. Click a monitor to
jump screens. Buy/sell stocks, track real holdings, log income/expenses.

pip install streamlit yfinance plotly pandas streamlit-local-storage
streamlit run app.py
"""
from __future__ import annotations
import json, csv, random, html
from pathlib import Path
from datetime import date, datetime, time as dtime
from dataclasses import dataclass, field, asdict
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# ── Files / constants ────────────────────────────────────────
PORTFOLIO_FILE   = "portfolio.json"
TRANSACTION_FILE = "transactions.csv"
BENCHMARK        = "^GSPC"

# Palette — neon cyberpunk
C_BG, C_PANEL, C_CARD = "#070a10", "#0d1320", "#111a2b"
C_CYAN, C_MAGENTA, C_PURPLE = "#2fe6ff", "#ff3b9a", "#a64dff"
C_TEXT, C_MUTED       = "#cfe9ff", "#7088a0"
C_GREEN, C_GREEN_LIGHT = "#1f9e5e", "#2bd673"
C_RED, C_RED_LIGHT     = "#8e1530", "#ff3b5c"
C_GOLD                 = "#ffd23f"
C_EYE                  = "#ff2230"
C_BORDER = "rgba(47,230,255,0.30)"   # rgba (fixes Plotly 8-digit-hex bug)
CHART_COLORS = ["#2fe6ff","#ff3b9a","#a64dff","#2bd673",
                "#ffd23f","#ff7b4a","#4a9eff","#ff5ce0"]
SCREENS = ["Overview", "Browse", "Holdings", "Bram's Take", "Ledger"]

# ══════════════════════════════════════════════════════════════
# Broker "Bram" — shadowy, cryptic, market-savvy
# ══════════════════════════════════════════════════════════════
KEEPER_NAME = "BRAM"
KEEPER_LINES = {
    "greet": [
        "You found your way back. The market never closes down here.",
        "Welcome to The Exchange. Mind the cables.",
        "The terminals are warm. What do you seek?",
        "Sssso. A trader returns. Show me your nerve.",
        "Numbers in the dark. That's all this is. Sit.",
        "Pick a screen. The machines are listening.",
        "Buy low. Sell high. Trust no one. Especially me.",
        "I've been watching the tape. It whispers things.",
        "Capital flows like blood through these wires. Yours now too.",
        "Every fortune starts with a flicker. Begin.",
    ],
    "buy": [
        "Acquired. The machine remembers everything.",
        "It is done. The position is yours to defend.",
        "A bold key to press. I approve... mostly.",
        "Bought. Hold your nerve when the screens turn red.",
        "Logged in the ledger. No takebacks down here.",
        "The tape twitches in your favor. For now.",
    ],
    "sell": [
        "Released. The coin returns to your account.",
        "Cashed out. The wise know when to vanish.",
        "Sold. Greed kills more traders than loss ever did.",
        "It's gone. Don't look back at the chart.",
        "Settled. The machine hums its approval.",
    ],
    "deposit": [
        "Fresh capital. The terminals like to be fed.",
        "Dollars added. Power is just liquidity, trader.",
        "More to work with. Spend it like it can run out — it can.",
    ],
    "income": [
        "Passive flow. Money that works while you sleep. The best kind.",
        "Dollars trickle in. A quiet stream cuts the deepest channel.",
        "Logged. Yield is patience made visible.",
    ],
    "expense": [
        "Drained. Every operation bleeds a little.",
        "Logged. The wires don't run for free.",
        "Paid. Even shadows have their costs.",
    ],
    "add": [
        "Catalogued — no dollars moved. It was already yours.",
        "Marked in the ledger. The machine sees it now.",
        "Recorded. Now I can watch it for you.",
    ],
    "error": [
        "No. The machine rejects it. Look closer.",
        "That signal is corrupt. Try again.",
        "The terminal blinks red. Something's wrong.",
    ],
    "confirm": [
        "Look into the eye. Are you certain?",
        "The machine wants your nerve. Confirm it.",
        "Press it like you mean it... or walk away.",
        "No hesitation in The Exchange. Decide.",
    ],
}
def keeper_says(key): return random.choice(KEEPER_LINES.get(key, KEEPER_LINES["greet"]))

def trader_rank(port_ret):
    if port_ret >= 30: return "◆ GHOST BROKER"
    if port_ret >= 15: return "◆ SHADOW DEALER"
    if port_ret >= 5:  return "◆ WIRE RUNNER"
    if port_ret >= 0:  return "◆ INITIATE"
    return "◆ FRESH MEAT"

st.set_page_config(page_title="THE EXCHANGE", page_icon="◆",
                   layout="wide", initial_sidebar_state="expanded")

# ══════════════════════════════════════════════════════════════
# Animated scene (broker + tentacles + monitors + typing text)
# Rendered in an iframe via components.html so JS/animations run.
# ══════════════════════════════════════════════════════════════
def _t(d, rim):
    return (f'<path d="{d}" fill="none" stroke="#070b14" stroke-width="20" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="{rim}" stroke-width="2.5" stroke-linecap="round" opacity="0.55"/>')

def _tip(x, y, rim):
    return (f'<circle cx="{x}" cy="{y}" r="9" fill="#0a1018" stroke="{rim}" stroke-width="2" opacity="0.85"/>'
            f'<circle cx="{x}" cy="{y}" r="3" fill="{rim}" opacity="0.8"/>')

def _deco_monitor(x, y, rim):
    return (f'<rect x="{x}" y="{y}" width="96" height="68" rx="6" fill="#06101c" stroke="{rim}" stroke-width="2"/>'
            f'<rect x="{x+6}" y="{y+6}" width="84" height="48" rx="3" fill="#0a1c2c"/>'
            f'<rect class="scan" x="{x+6}" y="{y+6}" width="84" height="48" rx="3" fill="url(#scanl)"/>'
            f'<polyline points="{x+12},{y+44} {x+30},{y+30} {x+48},{y+38} {x+66},{y+18} {x+84},{y+24}" '
            f'fill="none" stroke="{rim}" stroke-width="2" opacity="0.8"/>'
            f'<rect x="{x+38}" y="{y+74}" width="20" height="10" fill="#0a1018" stroke="{rim}" stroke-width="1.5"/>')

def _teeth():
    out, tx, up = "", 414, True
    while tx < 486:
        if up: out += f'<polygon points="{tx},181 {tx+11},181 {tx+5},196" fill="#e6f3ff"/>'
        else:  out += f'<polygon points="{tx},199 {tx+11},199 {tx+5},184" fill="#bcd8f0"/>'
        tx += 11; up = not up
    return out

_TENTACLES = (
    _t("M450 296 C 330 286 200 250 96 210", C_CYAN)    + _tip(96, 210, C_CYAN) +
    _t("M450 300 C 360 330 270 334 196 314", C_MAGENTA) + _tip(196, 314, C_MAGENTA) +
    _t("M450 296 C 572 286 702 250 808 210", C_MAGENTA) + _tip(808, 210, C_MAGENTA) +
    _t("M450 300 C 540 330 632 334 706 314", C_CYAN)    + _tip(706, 314, C_CYAN)
)

SCENE_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Chakra+Petch:wght@600;700&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;padding:0;background:#05070c;overflow:hidden;}
  .room{position:relative;width:100%;height:360px;overflow:hidden;
    background:radial-gradient(circle at 50% 26%, #13213c 0%, #0a0e16 55%, #05070c 100%);}
  .floor{position:absolute;left:-20%;right:-20%;bottom:0;height:150px;
    background-image:linear-gradient(rgba(47,230,255,.18) 1px,transparent 1px),
      linear-gradient(90deg,rgba(47,230,255,.14) 1px,transparent 1px);
    background-size:46px 46px;transform:perspective(320px) rotateX(62deg);transform-origin:bottom;opacity:.5;}
  .vig{position:absolute;inset:0;box-shadow:inset 0 0 160px 40px #05070c;pointer-events:none;}
  .scanlines{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(255,255,255,.025) 0 2px,transparent 2px 4px);pointer-events:none;opacity:.6;}
  .entity{position:absolute;left:50%;bottom:0;width:900px;max-width:100%;transform:translateX(-50%);
    transform-origin:bottom center;animation:sway 6.5s ease-in-out infinite alternate;}
  @keyframes sway{from{transform:translateX(-50%) rotate(-1.3deg);}to{transform:translateX(-50%) rotate(1.3deg);}}
  .eye{transform-origin:450px 150px;animation:eyePulse 2.6s ease-in-out infinite;}
  @keyframes eyePulse{0%,100%{filter:drop-shadow(0 0 7px #ff2230) drop-shadow(0 0 14px #ff223066);}
    50%{filter:drop-shadow(0 0 16px #ff3a48) drop-shadow(0 0 30px #ff2230aa);}}
  .scan{animation:scanFlick .5s steps(3) infinite;opacity:.5;}
  @keyframes scanFlick{0%{opacity:.35}50%{opacity:.6}100%{opacity:.4}}
  .dialogue{position:absolute;top:16px;left:50%;transform:translateX(-50%);width:84%;max-width:700px;
    text-align:center;font-family:'Share Tech Mono',monospace;font-size:18px;color:#d7fbff;
    text-shadow:0 0 8px rgba(41,211,255,.6);line-height:1.45;min-height:54px;z-index:3;}
  .name{font-family:'Chakra Petch',sans-serif;font-size:12px;letter-spacing:.35em;color:#ff3b9a;
    text-shadow:0 0 8px rgba(255,59,154,.6);margin-bottom:6px;}
  .cursor{display:inline-block;width:9px;height:17px;background:#29d3ff;margin-left:3px;vertical-align:-2px;
    box-shadow:0 0 8px #29d3ff;animation:blink .75s step-end infinite;}
  @keyframes blink{50%{opacity:0;}}
</style></head><body>
<div class="room">
  <div class="floor"></div>
  <div class="dialogue"><div class="name">&#9670; __NAME__ &#9670;</div><span id="dlg"></span><span class="cursor"></span></div>
  <svg class="entity" viewBox="0 0 900 360" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="eyeG" cx="50%" cy="44%" r="62%">
        <stop offset="0%" stop-color="#ffe0d6"/><stop offset="22%" stop-color="#ff5a48"/>
        <stop offset="68%" stop-color="#c5121f"/><stop offset="100%" stop-color="#3e0006"/>
      </radialGradient>
      <linearGradient id="cloak" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#0e1626"/><stop offset="1" stop-color="#05080f"/>
      </linearGradient>
      <linearGradient id="scanl" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#2fe6ff" stop-opacity="0"/><stop offset="1" stop-color="#2fe6ff" stop-opacity="0.10"/>
      </linearGradient>
    </defs>
    __LEFTMON__ __RIGHTMON__
    __TENTACLES__
    <path d="M450 64 C 528 86 568 158 568 232 L 568 322 L 332 322 L 332 232 C 332 158 372 86 450 64 Z"
          fill="url(#cloak)" stroke="#23415e" stroke-width="2"/>
    <path d="M450 64 C 528 86 568 158 568 232" fill="none" stroke="#2fe6ff" stroke-width="1.5" opacity="0.35"/>
    <path d="M450 64 C 372 86 332 158 332 232" fill="none" stroke="#ff3b9a" stroke-width="1.5" opacity="0.30"/>
    <ellipse cx="450" cy="156" rx="74" ry="84" fill="#05070d"/>
    <rect x="411" y="180" width="78" height="20" rx="3" fill="#080b12"/>
    __TEETH__
    <circle class="eye" cx="450" cy="150" r="24" fill="url(#eyeG)"/>
    <ellipse cx="450" cy="150" rx="4" ry="12" fill="#2a0006"/>
    <circle cx="443" cy="143" r="4" fill="#fff4f2" opacity="0.85"/>
  </svg>
  <div class="scanlines"></div><div class="vig"></div>
</div>
<script>
  var T = __DIALOGUE__;
  var el = document.getElementById('dlg'); el.textContent = '';
  var i = 0;
  (function type(){ if(i < T.length){ el.textContent += T.charAt(i); i++; setTimeout(type, 24); } })();
</script>
</body></html>"""

def scene_html(dialogue: str) -> str:
    return (SCENE_TEMPLATE
            .replace("__NAME__", KEEPER_NAME)
            .replace("__LEFTMON__", _deco_monitor(36, 150, C_CYAN))
            .replace("__RIGHTMON__", _deco_monitor(768, 150, C_MAGENTA))
            .replace("__TENTACLES__", _TENTACLES)
            .replace("__TEETH__", _teeth())
            .replace("__DIALOGUE__", json.dumps(dialogue)))

EYE_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Chakra+Petch:wght@700&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;padding:0;background:#05070c;overflow:hidden;}
  .stage{position:relative;width:100%;height:240px;overflow:hidden;
    background:radial-gradient(circle at 50% 40%, #1a0a12 0%, #0a0710 60%, #05070c 100%);}
  .lean{position:absolute;left:50%;top:18px;transform:translateX(-50%);animation:leanIn .55s cubic-bezier(.2,.8,.2,1) forwards;}
  @keyframes leanIn{0%{transform:translateX(-50%) scale(.25);opacity:0;}70%{transform:translateX(-50%) scale(1.12);opacity:1;}100%{transform:translateX(-50%) scale(1);}}
  .e{filter:drop-shadow(0 0 16px #ff2230) drop-shadow(0 0 34px #ff2230aa);animation:pulse 1.4s ease-in-out infinite;}
  @keyframes pulse{0%,100%{filter:drop-shadow(0 0 14px #ff2230) drop-shadow(0 0 28px #ff223099);}50%{filter:drop-shadow(0 0 24px #ff4250) drop-shadow(0 0 46px #ff2230cc);}}
  .ask{position:absolute;bottom:16px;left:0;right:0;text-align:center;font-family:'Chakra Petch',sans-serif;
    font-weight:700;letter-spacing:.18em;color:#ff5566;font-size:22px;text-shadow:0 0 12px #ff223088;}
  .sub{font-family:'Share Tech Mono',monospace;color:#d7fbff;font-size:15px;letter-spacing:.05em;margin-top:4px;text-shadow:0 0 8px #29d3ff66;}
  .scan{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(255,255,255,.03) 0 2px,transparent 2px 4px);pointer-events:none;}
</style></head><body>
<div class="stage">
  <svg class="lean" width="150" height="120" viewBox="0 0 150 120" xmlns="http://www.w3.org/2000/svg">
    <defs><radialGradient id="g" cx="50%" cy="44%" r="62%">
      <stop offset="0%" stop-color="#ffe0d6"/><stop offset="22%" stop-color="#ff5a48"/>
      <stop offset="66%" stop-color="#c5121f"/><stop offset="100%" stop-color="#3e0006"/></radialGradient></defs>
    <ellipse cx="75" cy="60" rx="70" ry="46" fill="#0a0710"/>
    <circle class="e" cx="75" cy="58" r="34" fill="url(#g)"/>
    <ellipse cx="75" cy="58" rx="6" ry="20" fill="#2a0006"/>
    <circle cx="64" cy="48" r="6" fill="#fff4f2" opacity="0.85"/>
  </svg>
  <div class="ask">ARE YOU SURE?<div class="sub">__SUB__</div></div>
  <div class="scan"></div>
</div></body></html>"""

def eye_html(action: str, ticker: str, shares: float) -> str:
    sub = f"{action} {shares:g} {html.escape(ticker)}"
    return EYE_TEMPLATE.replace("__SUB__", sub)


# ══════════════════════════════════════════════════════════════
# CSS  (page chrome: monitors, neon, panels)
# ══════════════════════════════════════════════════════════════
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Chakra+Petch:wght@500;600;700&family=Rajdhani:wght@500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; font-size: 16px; }
.stApp {
  background-color: #070a10;
  background-image:
    radial-gradient(circle at 14% 0%, rgba(47,230,255,0.06), transparent 40%),
    radial-gradient(circle at 88% 6%, rgba(255,59,154,0.06), transparent 42%),
    repeating-linear-gradient(0deg, rgba(255,255,255,0.012) 0 2px, transparent 2px 4px),
    linear-gradient(180deg, #0a0f18, #06080e);
  color: #cfe9ff;
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg,#0b1220,#070a12) !important;
  border-right: 1px solid rgba(47,230,255,0.25);
}
section[data-testid="stSidebar"] * { color: #cfe9ff !important; }
section[data-testid="stSidebar"] label { color: #2fe6ff !important; font-family:'Share Tech Mono',monospace !important; font-size: 0.74rem !important; letter-spacing:.08em !important; text-transform: uppercase !important; }
section[data-testid="stSidebar"] small { color: #7088a0 !important; }

[data-testid="metric-container"] {
  background: linear-gradient(180deg,#0e1726,#0a1018);
  border: 1px solid rgba(47,230,255,0.30); border-radius: 8px; padding: 14px 18px;
  box-shadow: 0 0 14px rgba(47,230,255,0.10), inset 0 0 18px rgba(47,230,255,0.05);
}
[data-testid="metric-container"] label { color: #6fb9d9 !important; font-family:'Share Tech Mono',monospace !important; font-size: 0.66rem !important; letter-spacing:.1em !important; text-transform: uppercase !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-family: 'Share Tech Mono', monospace; font-size: 1.3rem; color: #d7fbff; text-shadow:0 0 8px rgba(47,230,255,0.3); }
[data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricDelta"] { font-weight: 700; }

div.stButton > button {
  border-radius: 8px; font-family:'Chakra Petch',sans-serif; font-weight: 700; font-size: 0.92rem; letter-spacing:.07em;
  padding: 11px 16px; transition: all .08s; width: 100%; border: 2px solid rgba(47,230,255,0.4);
  background: linear-gradient(180deg,#10203a,#0a1626); color:#bfeaff;
  box-shadow: 0 0 12px rgba(47,230,255,0.15); text-shadow:0 0 6px rgba(47,230,255,0.4);
}
div.stButton > button:hover { filter: brightness(1.18); }
div.stButton > button:active { transform: translateY(3px) !important; }
.buy-btn  > div.stButton > button { background: linear-gradient(180deg,#1f9e5e,#127a45); color:#eafff2; border:2px solid #2bd673; font-size:1.1rem; padding:15px; box-shadow:0 0 18px rgba(43,214,115,0.4), 0 5px 0 #0c5230; text-shadow:0 0 7px rgba(43,214,115,0.6); }
.buy-btn  > div.stButton > button:active { box-shadow:0 0 18px rgba(43,214,115,0.4), 0 2px 0 #0c5230; }
.sell-btn > div.stButton > button { background: linear-gradient(180deg,#c0314e,#8e1530); color:#ffecef; border:2px solid #ff3b5c; font-size:1.1rem; padding:15px; box-shadow:0 0 18px rgba(255,59,92,0.4), 0 5px 0 #6e0f22; text-shadow:0 0 7px rgba(255,59,92,0.6); }
.sell-btn > div.stButton > button:active { box-shadow:0 0 18px rgba(255,59,92,0.4), 0 2px 0 #6e0f22; }
.neutral-btn > div.stButton > button { background: linear-gradient(180deg,#3a2a66,#241a44); color:#e6d8ff; border:2px solid #a64dff; box-shadow:0 0 14px rgba(166,77,255,0.3), 0 4px 0 #1a1230; }
.neutral-btn > div.stButton > button:active { box-shadow:0 0 14px rgba(166,77,255,0.3), 0 1px 0 #1a1230; }

input, textarea, [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
  background:#0c1626 !important; border:1px solid rgba(47,230,255,0.35) !important; color:#d7fbff !important; border-radius:6px !important; font-family:'Share Tech Mono',monospace !important; font-size:0.95rem !important; }

h1 { font-family:'Chakra Petch',sans-serif !important; color:#2fe6ff !important; font-size:1.7rem !important; letter-spacing:.1em !important; text-shadow:0 0 12px rgba(47,230,255,0.4); }
h2 { font-family:'Chakra Petch',sans-serif !important; color:#d7fbff !important; font-size:1.05rem !important; border-bottom:1px solid rgba(47,230,255,0.25) !important; padding-bottom:6px !important; margin-top:0 !important; letter-spacing:.06em !important; }
h3 { color:#7088a0 !important; font-family:'Share Tech Mono',monospace !important; font-size:0.74rem !important; text-transform:uppercase !important; letter-spacing:.12em !important; }
h4 { color:#2fe6ff !important; font-family:'Chakra Petch',sans-serif !important; }

/* ── Monitor navigation row ── */
.mon > div.stButton > button {
  background: radial-gradient(circle at 50% 38%, #0c2235, #06101c);
  border: 2px solid rgba(47,230,255,0.4); border-radius: 9px; color:#7fe9ff;
  font-family:'Share Tech Mono',monospace; letter-spacing:.05em; font-size:0.82rem; line-height:1.2;
  padding: 16px 6px; min-height:70px; position:relative; overflow:hidden;
  box-shadow: 0 0 12px rgba(47,230,255,0.15), inset 0 0 20px rgba(47,230,255,0.08);
  text-shadow:0 0 7px rgba(47,230,255,0.5); animation: monFlicker 5s infinite;
}
.mon > div.stButton > button::after {
  content:''; position:absolute; inset:0; pointer-events:none; opacity:.5;
  background: repeating-linear-gradient(0deg, rgba(255,255,255,.05) 0 2px, transparent 2px 4px),
             repeating-linear-gradient(0deg, rgba(47,230,255,.05) 0 1px, transparent 1px 3px);
  background-size:100% 4px, 100% 3px; animation: monStatic .35s steps(4) infinite;
}
@keyframes monStatic { 0%{background-position:0 0,0 0} 100%{background-position:0 8px,0 6px} }
@keyframes monFlicker { 0%,100%{filter:brightness(1)} 47%{filter:brightness(1.09)} 79%{filter:brightness(.95)} }
.mon > div.stButton > button:hover { filter: brightness(1.2); transform: translateY(-2px); }
.mon-active > div.stButton > button {
  border-color:#ff3b9a; color:#ffd0ea;
  box-shadow:0 0 20px rgba(255,59,154,0.45), inset 0 0 24px rgba(255,59,154,0.12);
  text-shadow:0 0 9px rgba(255,59,154,0.7);
}

/* ── CRT boot header (plays on each screen switch) ── */
.crt-boot {
  font-family:'Share Tech Mono',monospace; color:#2fe6ff; letter-spacing:.22em; text-transform:uppercase; font-size:0.92rem;
  border:1px solid rgba(47,230,255,0.4); background:linear-gradient(180deg,#0d1726,#0a1018);
  padding:9px 16px; border-radius:6px; box-shadow:0 0 16px rgba(47,230,255,0.2), inset 0 0 20px rgba(47,230,255,0.07);
  margin-bottom:16px; position:relative; overflow:hidden; animation: bootIn .5s ease-out;
}
@keyframes bootIn { 0%{transform:scaleY(.04);opacity:0;filter:brightness(3);} 60%{transform:scaleY(1.05);opacity:1;} 100%{transform:scaleY(1);} }
.crt-boot::after { content:''; position:absolute; inset:0; pointer-events:none;
  background:repeating-linear-gradient(0deg, rgba(255,255,255,.06) 0 2px, transparent 2px 4px); }

[data-testid="stDataFrame"] { background:#0c1626; border:1px solid rgba(47,230,255,0.25); border-radius:8px; }
[data-testid="stAlert"] { border-radius:8px; }
hr { border-color:rgba(47,230,255,0.2); margin:12px 0; }
[data-testid="stSelectbox"] > div > div { background:#0c1626 !important; border-color:rgba(47,230,255,0.35) !important; color:#d7fbff !important; }
[data-testid="stFileUploadDropzone"] { background:#0c1626 !important; border-color:rgba(47,230,255,0.35) !important; }
[data-testid="stCaptionContainer"] p { color:#7088a0 !important; }
.stExpander { border:1px solid rgba(47,230,255,0.25) !important; border-radius:8px !important; background:#0b1220 !important; }

.rank-badge { display:inline-block; background:linear-gradient(180deg,#241a44,#16102e); border:1px solid #a64dff; border-radius:6px; padding:6px 12px; font-family:'Chakra Petch',sans-serif; font-size:0.8rem; color:#d8b8ff; letter-spacing:.1em; font-weight:700; box-shadow:0 0 12px rgba(166,77,255,0.35); }
.ticker-badge { display:inline-block; background:#0c1626; border:1px solid #2fe6ff; color:#2fe6ff; font-family:'Share Tech Mono',monospace; font-size:0.85rem; font-weight:700; padding:3px 10px; border-radius:5px; letter-spacing:.08em; text-shadow:0 0 6px rgba(47,230,255,0.4); }
.price-big { font-family:'Share Tech Mono',monospace; font-size:1.9rem; font-weight:700; color:#d7fbff; margin:0; text-shadow:0 0 10px rgba(47,230,255,0.3); }
.price-up { color:#2bd673; font-size:0.95rem; font-weight:700; text-shadow:0 0 6px rgba(43,214,115,0.5); }
.price-down { color:#ff3b5c; font-size:0.95rem; font-weight:700; text-shadow:0 0 6px rgba(255,59,92,0.5); }

.info-box { background:#0c1626; border:1px solid rgba(47,230,255,0.25); padding:12px 16px; border-radius:8px; color:#7fa6c4; font-size:0.95rem; }
.notif-success { background:#0b2418; border:1px solid #2bd673; padding:12px 16px; border-radius:8px; color:#6ff0a8; font-size:0.98rem; font-weight:600; margin-bottom:12px; box-shadow:0 0 14px rgba(43,214,115,0.25); }
.notif-error { background:#2a0e16; border:1px solid #ff3b5c; padding:12px 16px; border-radius:8px; color:#ff8fa3; font-size:0.98rem; font-weight:600; margin-bottom:12px; box-shadow:0 0 14px rgba(255,59,92,0.25); }
.disclaimer { background:#171026; border:1px solid #a64dff; border-left:5px solid #a64dff; padding:12px 16px; border-radius:8px; color:#cdb8f0; font-size:0.88rem; line-height:1.5; margin:8px 0 16px 0; }
.read-card { background:linear-gradient(180deg,#0e1726,#0a1018); border:1px solid rgba(47,230,255,0.22); border-radius:8px; padding:14px 16px; margin-bottom:10px; box-shadow:0 0 12px rgba(47,230,255,0.08); }
.read-lean-bull { color:#2bd673; font-weight:700; font-family:'Chakra Petch',sans-serif; letter-spacing:.05em; }
.read-lean-bear { color:#ff3b5c; font-weight:700; font-family:'Chakra Petch',sans-serif; letter-spacing:.05em; }
.read-lean-neutral { color:#7088a0; font-weight:700; font-family:'Chakra Petch',sans-serif; letter-spacing:.05em; }
.signal-line { color:#aecbe4; font-size:0.92rem; margin:3px 0; }
</style>""", unsafe_allow_html=True)


# ── Browser save (autosave / autoload that survives reboots) ──
try:
    from streamlit_local_storage import LocalStorage
    _LS = LocalStorage()
    HAS_BROWSER_SAVE = True
except Exception:
    _LS = None
    HAS_BROWSER_SAVE = False
LS_KEY = "the_exchange_save_v1"

def browser_load_dict():
    if not HAS_BROWSER_SAVE: return None
    try:
        raw = _LS.getItem(LS_KEY)
        if raw: return json.loads(raw) if isinstance(raw, str) else raw
    except Exception: pass
    return None

def browser_save(p):
    if not HAS_BROWSER_SAVE or p is None: return
    try: _LS.setItem(LS_KEY, json.dumps(_portfolio_to_dict(p)), key="ls_autosave")
    except Exception: pass

def browser_clear():
    if not HAS_BROWSER_SAVE: return
    try: _LS.setItem(LS_KEY, "", key="ls_clear")
    except Exception: pass


def info_box(msg): st.markdown(f'<div class="info-box">{msg}</div>', unsafe_allow_html=True)
def crt_boot(title): st.markdown(f'<div class="crt-boot">&#9612; {title} &#9616;</div>', unsafe_allow_html=True)
def disclaimer():
    st.markdown(
        '<div class="disclaimer">◆ <b>Bram\'s reads are a game feature, not financial advice.</b> '
        'They\'re based on simple technical indicators (RSI, moving averages, price vs. recent highs/lows) '
        'that only describe <i>past</i> price behavior — they are frequently wrong about the future. '
        'Always do your own research and talk to a trusted adult before trading real money.</div>',
        unsafe_allow_html=True)

def base_layout(height=340):
    return dict(paper_bgcolor=C_CARD, plot_bgcolor=C_PANEL,
        font=dict(family="Share Tech Mono, monospace", color=C_MUTED, size=11),
        xaxis=dict(gridcolor="#16243a", showgrid=True, zeroline=False, color=C_MUTED),
        yaxis=dict(gridcolor="#16243a", showgrid=True, zeroline=False, color=C_MUTED),
        legend=dict(bgcolor=C_PANEL, bordercolor=C_BORDER, borderwidth=1,
                    font=dict(family="Share Tech Mono, monospace", size=11, color=C_TEXT)),
        hovermode="x unified", margin=dict(l=0, r=0, t=10, b=0), height=height)


# ── Data Models ──────────────────────────────────────────────
@dataclass
class Position:
    ticker: str; shares: float; avg_cost: float
    @property
    def cost_basis(self): return self.shares * self.avg_cost

@dataclass
class Transaction:
    timestamp: str; action: str; ticker: str; shares: float
    price: float; total: float; cash_after: float; notes: str = ""

@dataclass
class Portfolio:
    cash: float
    positions: dict = field(default_factory=dict)
    transactions: list = field(default_factory=list)
    inception_date: str = field(default_factory=lambda: date.today().isoformat())
    benchmark_start_price: Optional[float] = None
    recurring: list = field(default_factory=list)


# ── Persistence ──────────────────────────────────────────────
def _portfolio_to_dict(p: Portfolio) -> dict:
    return {"cash": p.cash, "inception_date": p.inception_date,
            "benchmark_start_price": p.benchmark_start_price,
            "positions": {t: asdict(pos) for t, pos in p.positions.items()},
            "transactions": [asdict(tx) for tx in p.transactions],
            "recurring": p.recurring}

def _portfolio_from_dict(data: dict) -> Portfolio:
    positions = {t: Position(**v) for t, v in data.get("positions", {}).items()}
    txs = [Transaction(**tx) for tx in data.get("transactions", [])]
    return Portfolio(cash=data["cash"], positions=positions, transactions=txs,
                     inception_date=data.get("inception_date", date.today().isoformat()),
                     benchmark_start_price=data.get("benchmark_start_price"),
                     recurring=data.get("recurring", []))

def save_portfolio(p: Portfolio):
    with open(PORTFOLIO_FILE, "w") as f: json.dump(_portfolio_to_dict(p), f, indent=2)
    try: st.session_state["_browser_dirty"] = True
    except Exception: pass

def load_portfolio() -> Optional[Portfolio]:
    if not Path(PORTFOLIO_FILE).exists(): return None
    with open(PORTFOLIO_FILE) as f: data = json.load(f)
    return _portfolio_from_dict(data)

def load_holdings_csv(f) -> dict:
    positions = {}
    for row in csv.DictReader(f.read().decode("utf-8").splitlines()):
        t = row["ticker"].strip().upper()
        positions[t] = Position(t, float(row["shares"]), float(row["avg_cost"]))
    return positions

def append_tx_log(tx: Transaction):
    write_header = not Path(TRANSACTION_FILE).exists()
    with open(TRANSACTION_FILE, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(tx).keys()))
        if write_header: w.writeheader()
        w.writerow(asdict(tx))


# ── Market Data ──────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_price(ticker: str) -> float:
    info = yf.Ticker(ticker).fast_info
    p = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
    if not p: raise ValueError(f"No price found for {ticker}")
    return float(p)

@st.cache_data(ttl=60)
def fetch_prices(tickers: tuple) -> dict:
    if not tickers: return {}
    if len(tickers) == 1: return {tickers[0]: fetch_price(tickers[0])}
    raw = yf.download(list(tickers), period="1d", progress=False, auto_adjust=True)
    out = {}
    for t in tickers:
        try:
            v = float(raw["Close"][t].iloc[-1])
            if v == v: out[t] = v   # skip NaN
        except Exception:
            pass
    return out

@st.cache_data(ttl=300)
def fetch_chart_data(ticker: str, period="6mo") -> pd.DataFrame:
    df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    df.reset_index(inplace=True)
    return df

@st.cache_data(ttl=60)
def fetch_ticker_info(ticker: str) -> dict:
    try:
        i = yf.Ticker(ticker).info
        return {"name": i.get("longName", ticker), "sector": i.get("sector", "—"),
                "market_cap": i.get("marketCap"), "pe": i.get("trailingPE"),
                "52w_high": i.get("fiftyTwoWeekHigh"), "52w_low": i.get("fiftyTwoWeekLow"),
                "prev_close": i.get("previousClose"), "div_yield": i.get("dividendYield")}
    except: return {}

def _close_series(df) -> pd.Series:
    c = df["Close"]
    if isinstance(c, pd.DataFrame): c = c.iloc[:, 0]
    return c.astype(float).reset_index(drop=True)


# ── Technical "reads" (educational, not advice) ──────────────
def compute_rsi(close: pd.Series, period=14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean(); avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=600)
def compute_signals(ticker: str) -> dict:
    df = fetch_chart_data(ticker, "1y")
    if df.empty or len(df) < 20: return {"ok": False}
    close = _close_series(df)
    price = float(close.iloc[-1]); rsi = float(compute_rsi(close).iloc[-1])
    sma50  = float(close.rolling(50).mean().iloc[-1])  if len(close) >= 50  else None
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    hi, lo = float(close.max()), float(close.min())
    pct_from_high = (price - hi) / hi * 100; pct_from_low = (price - lo) / lo * 100
    obs, score = [], 0.0
    if rsi == rsi:
        if rsi < 30:   obs.append(f"RSI is {rsi:.0f} — under 30, often called \"oversold\" (fallen hard lately)."); score += 1
        elif rsi > 70: obs.append(f"RSI is {rsi:.0f} — over 70, often called \"overbought\" (run up fast lately)."); score -= 1
        else:          obs.append(f"RSI is {rsi:.0f} — in the neutral middle zone.")
    if sma50 and sma200:
        if price > sma50 > sma200:   obs.append("Price is above both its 50-day and 200-day average — a classic uptrend shape."); score += 1
        elif price < sma50 < sma200: obs.append("Price is below both its 50-day and 200-day average — a downtrend shape."); score -= 1
        else:                        obs.append("The 50-day and 200-day averages are tangled — no clear trend.")
    elif sma50:
        obs.append("Above its 50-day average." if price > sma50 else "Below its 50-day average.")
        score += 0.5 if price > sma50 else -0.5
    if pct_from_high <= -20:  obs.append(f"It's {pct_from_high:.0f}% below its 1-year high."); score += 0.5
    elif pct_from_high >= -3: obs.append("It's hovering near its 1-year high."); score -= 0.25
    obs.append(f"Up {pct_from_low:.0f}% from its 1-year low.")
    lean = "Bullish-leaning" if score >= 1 else "Bearish-leaning" if score <= -1 else "Neutral"
    return {"ok": True, "price": price, "rsi": rsi, "obs": obs, "lean": lean, "score": score}

def keeper_read_line(lean: str, ticker: str) -> str:
    if lean == "Bullish-leaning":
        return random.choice([
            f"{ticker} pulses green on my screens — though the machine lies as often as it tells truth.",
            f"{ticker} has strength in its signal. Watch it closely.",
            f"If pressed, I'd call {ticker} healthy — but never move on my word alone."])
    if lean == "Bearish-leaning":
        return random.choice([
            f"{ticker} runs cold on the wire. I'd tread carefully.",
            f"Something drains {ticker}. Watch before you commit.",
            f"I would not chase {ticker} tonight — but that is only the tape talking."])
    return random.choice([
        f"{ticker} drifts in the static — no clear signal.",
        f"The machine can't read {ticker} cleanly. Mixed noise.",
        f"{ticker} sits in the grey. Sometimes patience is the play."])


# ── Trading / ledger logic ───────────────────────────────────
def _stamp(custom_date: Optional[date]) -> str:
    if custom_date: return datetime.combine(custom_date, dtime(12, 0)).strftime("%Y-%m-%d %H:%M:%S")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def add_existing_holding(p, ticker, shares, avg_cost):
    try:
        ticker = ticker.upper().strip()
        if not ticker: return False, "Enter a ticker symbol."
        if shares <= 0:   return False, "Shares must be positive."
        if avg_cost <= 0: return False, "Cost basis per share must be positive."
        if ticker in p.positions:
            pos = p.positions[ticker]; ns = pos.shares + shares
            p.positions[ticker] = Position(ticker, ns, (pos.cost_basis + shares*avg_cost) / ns)
        else:
            p.positions[ticker] = Position(ticker, shares, avg_cost)
        tx = Transaction(_stamp(None), "IMPORT", ticker, shares, avg_cost, round(shares*avg_cost, 2), p.cash, "existing holding")
        p.transactions.append(tx); append_tx_log(tx); save_portfolio(p)
        return True, f"Added {shares:g} × {ticker} at ${avg_cost:,.2f} cost basis (cash unchanged)."
    except Exception as e: return False, str(e)

def execute_buy(p, ticker, shares, price=None, notes="", custom_date=None):
    try:
        if shares <= 0: return False, "Share quantity must be positive."
        mp = price if price else fetch_price(ticker)
        total = round(shares * mp, 4)
        if total > p.cash: return False, f"Not enough dollars. Need ${total:,.2f}, you have ${p.cash:,.2f}."
        if ticker in p.positions:
            pos = p.positions[ticker]; ns = pos.shares + shares
            p.positions[ticker] = Position(ticker, ns, (pos.cost_basis + total) / ns)
        else:
            p.positions[ticker] = Position(ticker, shares, mp)
        p.cash = round(p.cash - total, 4)
        tx = Transaction(_stamp(custom_date), "BUY", ticker, shares, mp, total, p.cash, notes)
        p.transactions.append(tx); append_tx_log(tx); save_portfolio(p)
        return True, f"Bought {shares:g} × {ticker} @ ${mp:,.2f} = ${total:,.2f}"
    except Exception as e: return False, str(e)

def execute_sell(p, ticker, shares, price=None, notes="", custom_date=None):
    try:
        if shares <= 0: return False, "Share quantity must be positive."
        if ticker not in p.positions: return False, f"You don't hold any {ticker}."
        pos = p.positions[ticker]
        if shares > pos.shares: return False, f"You only hold {pos.shares:.4f} shares of {ticker}."
        mp = price if price else fetch_price(ticker)
        proceeds = round(shares * mp, 4)
        remaining = round(pos.shares - shares, 8)
        if remaining < 1e-6: del p.positions[ticker]
        else: p.positions[ticker] = Position(ticker, remaining, pos.avg_cost)
        p.cash = round(p.cash + proceeds, 4)
        tx = Transaction(_stamp(custom_date), "SELL", ticker, shares, mp, proceeds, p.cash, notes)
        p.transactions.append(tx); append_tx_log(tx); save_portfolio(p)
        return True, f"Sold {shares:g} × {ticker} @ ${mp:,.2f} = ${proceeds:,.2f}"
    except Exception as e: return False, str(e)

def post_cashflow(p, kind, amount, label, custom_date=None):
    try:
        if amount <= 0: return False, "Amount must be positive."
        p.cash = round(p.cash + amount, 2) if kind == "INCOME" else round(p.cash - amount, 2)
        tx = Transaction(_stamp(custom_date), kind, label or kind.title(), 0.0, 0.0, round(amount, 2), p.cash, "")
        p.transactions.append(tx); append_tx_log(tx); save_portfolio(p)
        return True, f"{kind.title()} of ${amount:,.2f} logged ({label})."
    except Exception as e: return False, str(e)

def get_stats(p: Portfolio):
    tickers = tuple(p.positions.keys())
    live = fetch_prices(tickers)
    rows, total_mv, total_cost = [], 0.0, 0.0
    for t, pos in p.positions.items():
        lp = live.get(t, pos.avg_cost); mv = pos.shares * lp
        pnl = (lp - pos.avg_cost) * pos.shares
        pnl_pct = (lp - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost else 0
        rows.append({"Ticker": t, "Shares": pos.shares, "Avg Cost": pos.avg_cost,
                     "Price": lp, "Value": mv, "P&L ($)": pnl, "P&L (%)": pnl_pct, "Weight": 0})
        total_mv += mv; total_cost += pos.cost_basis
    total_val = p.cash + total_mv
    for r in rows: r["Weight"] = r["Value"] / total_val * 100 if total_val else 0
    unrealised = total_mv - total_cost
    port_ret = (unrealised / total_cost * 100) if total_cost else 0
    cash_weight = p.cash / total_val * 100 if total_val else 0
    spx_ret = None
    if p.benchmark_start_price:
        try:
            spx_now = fetch_price(BENCHMARK)
            spx_ret = (spx_now - p.benchmark_start_price) / p.benchmark_start_price * 100
        except: pass
    return {"rows": rows, "total_val": total_val, "cash": p.cash, "cash_weight": cash_weight,
            "total_mv": total_mv, "total_cost": total_cost, "unrealised": unrealised,
            "port_ret": port_ret, "spx_ret": spx_ret,
            "alpha": (port_ret - spx_ret) if spx_ret is not None else None}


# ── Session state ────────────────────────────────────────────
if "portfolio" not in st.session_state: st.session_state.portfolio = load_portfolio()
if st.session_state.get("portfolio") is None:
    _saved = browser_load_dict()
    if _saved:
        try: st.session_state.portfolio = _portfolio_from_dict(_saved)
        except Exception: pass
if "trade_msg"     not in st.session_state: st.session_state.trade_msg = None
if "dialogue"      not in st.session_state: st.session_state.dialogue  = keeper_says("greet")
if "screen"        not in st.session_state: st.session_state.screen = "Overview"
if "pending_trade" not in st.session_state: st.session_state.pending_trade = None
portfolio: Optional[Portfolio] = st.session_state.portfolio


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
def set_pending(action, ticker, shares, price, custom_dt=None):
    st.session_state.pending_trade = {"action": action, "ticker": ticker.upper(),
        "shares": float(shares), "price": price,
        "custom_dt": custom_dt.isoformat() if custom_dt else None}
    st.session_state.dialogue = keeper_says("confirm")

with st.sidebar:
    if portfolio is None:
        st.markdown(f'<div class="rank-badge">◆ {KEEPER_NAME} // THE EXCHANGE</div>', unsafe_allow_html=True)
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.markdown("### Jack In")
        init_cash = st.number_input("Starting Dollars ($)", value=10000.0, min_value=0.0, step=500.0)
        uploaded = st.file_uploader("Import Holdings CSV (optional)", type="csv",
                                    help="Columns: ticker, shares, avg_cost")
        st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
        if st.button("◆  ENTER THE EXCHANGE"):
            positions = load_holdings_csv(uploaded) if uploaded else {}
            spx = None
            try: spx = fetch_price(BENCHMARK)
            except: pass
            p = Portfolio(cash=init_cash, positions=positions, benchmark_start_price=spx)
            save_portfolio(p); st.session_state.portfolio = p
            st.session_state.dialogue = "You're in. Add what you already hold under 'Add Existing Holding'."
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")
        if HAS_BROWSER_SAVE:
            st.caption("Been here before on this device? Your terminal loads itself. New machine? Load a backup.")
        else:
            st.caption("Got a saved file? Load it below.")
        jup = st.file_uploader("Load a saved game", type="json", key="json_restore")
        if jup:
            p = _portfolio_from_dict(json.load(jup))
            st.session_state.portfolio = p; save_portfolio(p)
            st.session_state.dialogue = "Reconnected. The machine remembers you."
            st.rerun()
    else:
        if portfolio.positions:
            try:
                s0 = get_stats(portfolio)
                st.markdown(f'<div class="rank-badge">{trader_rank(s0["port_ret"])}</div>', unsafe_allow_html=True)
                st.markdown("&nbsp;", unsafe_allow_html=True)
            except: pass

        st.markdown("### ➕ Add Existing Holding")
        with st.expander("Enter a stock you already own"):
            st.caption("For stocks you bought in real life. Records them at your cost basis; "
                       "does NOT spend your dollars.")
            ex_ticker = st.text_input("Ticker", placeholder="e.g. AAPL", key="ex_ticker").upper().strip()
            ex_shares = st.number_input("Shares you own", min_value=0.0, step=1.0, value=0.0, key="ex_shares")
            ex_cost   = st.number_input("Your avg cost per share ($)", min_value=0.0, step=1.0, value=0.0, key="ex_cost")
            st.markdown('<div class="neutral-btn">', unsafe_allow_html=True)
            if st.button("Add to Holdings"):
                ok, msg = add_existing_holding(portfolio, ex_ticker, ex_shares, ex_cost)
                st.session_state.trade_msg = ("success" if ok else "error", msg)
                st.session_state.dialogue  = keeper_says("add" if ok else "error")
                fetch_prices.clear(); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### ⚡ Trade at Market")
        trade_ticker = st.text_input("Ticker", placeholder="e.g. AAPL", key="trade_ticker").upper().strip()
        trade_shares = st.number_input("Shares", min_value=0.0001, step=1.0, value=1.0, key="trade_shares")
        use_custom = st.checkbox("I bought/sold at a different price or date")
        custom_price, custom_dt = None, None
        if use_custom:
            custom_price = st.number_input("Price per share ($)", min_value=0.0, step=1.0, value=0.0, key="custom_price")
            custom_price = custom_price if custom_price > 0 else None
            custom_dt = st.date_input("Trade date", value=date.today(), max_value=date.today(), key="custom_dt")
        preview_price = None
        if trade_ticker:
            try:
                live_p = fetch_price(trade_ticker)
                use_p = custom_price if custom_price else live_p
                preview_price = use_p
                tag = " (your price)" if custom_price else " (live)"
                st.caption(f"${use_p:,.2f}/share{tag}  ·  est. ${trade_shares*use_p:,.2f}")
            except: st.caption("⚠ Can't find that ticker")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
            if st.button("▲ BUY", key="sb_buy") and trade_ticker:
                set_pending("BUY", trade_ticker, trade_shares, preview_price, custom_dt); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="sell-btn">', unsafe_allow_html=True)
            if st.button("▼ SELL", key="sb_sell") and trade_ticker:
                set_pending("SELL", trade_ticker, trade_shares, preview_price, custom_dt); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 💰 Income & Expenses")
        with st.expander("Log income or expense"):
            flow_kind  = st.radio("Type", ["Income", "Expense"], horizontal=True, key="flow_kind")
            flow_label = st.text_input("Label", placeholder="e.g. Dividend, Allowance, Fee", key="flow_label")
            flow_amt   = st.number_input("Amount ($)", min_value=0.0, step=10.0, value=0.0, key="flow_amt")
            flow_custom = st.checkbox("Use a past date", key="flow_custom")
            flow_dt = st.date_input("Date", value=date.today(), max_value=date.today(), key="flow_dt") if flow_custom else None
            st.markdown('<div class="neutral-btn">', unsafe_allow_html=True)
            if st.button("Log it"):
                kind = "INCOME" if flow_kind == "Income" else "EXPENSE"
                ok, msg = post_cashflow(portfolio, kind, flow_amt, flow_label, flow_dt)
                st.session_state.trade_msg = ("success" if ok else "error", msg)
                st.session_state.dialogue  = keeper_says("income" if (ok and kind=="INCOME") else "expense" if ok else "error")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        with st.expander("Recurring reminders"):
            st.caption("Save a recurring item, then post it with one click when it's due.")
            r_label = st.text_input("Name", placeholder="e.g. Monthly allowance", key="r_label")
            r_amt   = st.number_input("Amount ($)", min_value=0.0, step=10.0, value=0.0, key="r_amt")
            r_kind  = st.radio("Type", ["Income", "Expense"], horizontal=True, key="r_kind")
            r_cad   = st.selectbox("Cadence", ["Weekly", "Monthly", "Quarterly", "Yearly"], key="r_cad")
            if st.button("Save reminder"):
                if r_label and r_amt > 0:
                    portfolio.recurring.append({"label": r_label, "amount": r_amt,
                        "kind": "INCOME" if r_kind=="Income" else "EXPENSE", "cadence": r_cad})
                    save_portfolio(portfolio); st.rerun()
            for idx, item in enumerate(portfolio.recurring):
                sign = "+" if item["kind"] == "INCOME" else "−"
                st.markdown(f'<small>{sign}${item["amount"]:,.2f} · {item["label"]} ({item["cadence"]})</small>', unsafe_allow_html=True)
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("Post", key=f"post_{idx}"):
                        ok, msg = post_cashflow(portfolio, item["kind"], item["amount"], item["label"])
                        st.session_state.trade_msg = ("success" if ok else "error", msg)
                        st.session_state.dialogue  = keeper_says("income" if item["kind"]=="INCOME" else "expense")
                        st.rerun()
                with cc2:
                    if st.button("Remove", key=f"rm_{idx}"):
                        portfolio.recurring.pop(idx); save_portfolio(portfolio); st.rerun()

        st.markdown("---")
        st.markdown("### 🔧 Manage")
        with st.expander("Remove a holding"):
            if portfolio.positions:
                rem = st.selectbox("Choose holding", list(portfolio.positions.keys()), key="rem_pick")
                if st.button("Remove from list"):
                    del portfolio.positions[rem]; save_portfolio(portfolio)
                    st.session_state.dialogue = "Wiped from the record. Gone."
                    st.rerun()
            else:
                st.caption("No holdings to remove.")

        st.markdown("### 💾 Save")
        if HAS_BROWSER_SAVE:
            st.markdown('<div class="neutral-btn">', unsafe_allow_html=True)
            if st.button("💾 Save"):
                browser_save(portfolio)
                st.session_state.dialogue = "Saved to the machine. It will remember when you return."
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.caption("Your terminal also saves on its own — this just makes sure. It reloads "
                       "automatically next time you open it on this device.")
        else:
            st.caption("Auto-save isn't available here — use the backup file below to keep your progress safe.")
        with st.expander("Backup / move to another device"):
            st.caption("Download a backup, or load one to move your terminal to another device.")
            if Path(PORTFOLIO_FILE).exists():
                with open(PORTFOLIO_FILE) as f:
                    st.download_button("⬇  Download backup", f.read(), file_name="my_exchange_save.json", mime="application/json")
            if Path(TRANSACTION_FILE).exists():
                with open(TRANSACTION_FILE) as f:
                    st.download_button("⬇  Download trade log (CSV)", f.read(), file_name="transactions.csv", mime="text/csv")
            backup = st.file_uploader("Load a backup file", type="json", key="backup_load")
            if backup:
                p = _portfolio_from_dict(json.load(backup))
                st.session_state.portfolio = p; save_portfolio(p)
                st.session_state.dialogue = "Backup restored. Welcome back to The Exchange."
                st.rerun()
        st.markdown("---")
        if st.button("🗑  Wipe Everything"):
            st.session_state.portfolio = None
            st.session_state["_browser_dirty"] = False
            st.session_state.pending_trade = None
            st.session_state.dialogue = keeper_says("greet")
            browser_clear()
            for fp in [PORTFOLIO_FILE, TRANSACTION_FILE]:
                if Path(fp).exists(): Path(fp).unlink()
            st.rerun()


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
components.html(scene_html(st.session_state.dialogue), height=372, scrolling=False)

if portfolio is None:
    info_box("Jack in using the sidebar to begin. Once you're inside, use "
             "<b>➕ Add Existing Holding</b> to enter the stocks you already own.")
    st.stop()

# ── Pending trade → leaning eye confirm ──────────────────────
pt = st.session_state.pending_trade
if pt:
    components.html(eye_html(pt["action"], pt["ticker"], pt["shares"]), height=248, scrolling=False)
    cdt = pt.get("custom_dt")
    cdt = date.fromisoformat(cdt) if cdt else None
    cc1, cc2, _ = st.columns([1, 1, 2])
    with cc1:
        cls = "buy-btn" if pt["action"] == "BUY" else "sell-btn"
        st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
        if st.button(f"CONFIRM {pt['action']}", key="confirm_trade"):
            if pt["action"] == "BUY":
                ok, msg = execute_buy(portfolio, pt["ticker"], pt["shares"], pt["price"], custom_date=cdt)
            else:
                ok, msg = execute_sell(portfolio, pt["ticker"], pt["shares"], pt["price"], custom_date=cdt)
            st.session_state.trade_msg = ("success" if ok else "error", msg)
            st.session_state.dialogue  = keeper_says(pt["action"].lower() if ok else "error")
            st.session_state.pending_trade = None
            fetch_prices.clear(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with cc2:
        st.markdown('<div class="neutral-btn">', unsafe_allow_html=True)
        if st.button("CANCEL", key="cancel_trade"):
            st.session_state.pending_trade = None
            st.session_state.dialogue = "Cold feet? Wise. The machine waits."
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ── Trade result banner ──────────────────────────────────────
if st.session_state.trade_msg:
    kind, msg = st.session_state.trade_msg
    cls = "notif-success" if kind == "success" else "notif-error"
    icon = "✔" if kind == "success" else "✘"
    st.markdown(f'<div class="{cls}">{icon}  {msg}</div>', unsafe_allow_html=True)
    st.session_state.trade_msg = None

stats = get_stats(portfolio)

# ── Monitor navigation (click a screen) ──────────────────────
mon_labels = {"Overview":"◢ OVERVIEW","Browse":"◷ BROWSE","Holdings":"▤ HOLDINGS",
              "Bram's Take":"◉ BRAM'S TAKE","Ledger":"❏ LEDGER"}
cols = st.columns(len(SCREENS))
for col, name in zip(cols, SCREENS):
    with col:
        active = "mon-active" if st.session_state.screen == name else ""
        st.markdown(f'<div class="mon {active}">', unsafe_allow_html=True)
        if st.button(mon_labels[name], key=f"nav_{name}"):
            st.session_state.screen = name; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
screen = st.session_state.screen


# ── SCREEN: Overview ─────────────────────────────────────────
if screen == "Overview":
    crt_boot("Overview // your standing")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: st.metric("Total Value", f"${stats['total_val']:,.2f}")
    with k2: st.metric("Dollars", f"${stats['cash']:,.2f}", delta=f"{stats['cash_weight']:.1f}% of total", delta_color="off")
    with k3:
        sign = "+" if stats['unrealised'] >= 0 else ""
        st.metric("Total Gain/Loss", f"{sign}${stats['unrealised']:,.2f}", delta=f"{sign}{stats['port_ret']:.2f}%")
    with k4:
        spx = f"{stats['spx_ret']:+.2f}%" if stats['spx_ret'] is not None else "N/A"
        st.metric("S&P 500", spx)
    with k5:
        al = f"{stats['alpha']:+.2f}%" if stats['alpha'] is not None else "N/A"
        st.metric("Alpha (vs S&P)", al)
    st.caption("Gain/Loss compares each stock's current price to your average cost (what you paid). "
               "Alpha is how much you're beating — or trailing — the S&P 500.")
    st.markdown("---")
    left, right = st.columns([3, 2])
    with left:
        st.markdown("## Performance")
        if stats["rows"]:
            pm = {"1 Month":"1mo","3 Months":"3mo","6 Months":"6mo","1 Year":"1y"}
            pl = st.selectbox("Period", list(pm.keys()), index=2, key="perf_period")
            fig = go.Figure()
            for i, row in enumerate(stats["rows"]):
                try:
                    df = fetch_chart_data(row["Ticker"], pm[pl])
                    if df.empty: continue
                    cs = _close_series(df); pct = (cs / float(cs.iloc[0]) - 1) * 100
                    fig.add_trace(go.Scatter(x=df["Date"], y=pct, name=row["Ticker"],
                        line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2.5),
                        hovertemplate="%{y:.2f}%<extra>"+row["Ticker"]+"</extra>"))
                except: pass
            try:
                sp = fetch_chart_data(BENCHMARK, pm[pl]); cs = _close_series(sp)
                pct = (cs / float(cs.iloc[0]) - 1) * 100
                fig.add_trace(go.Scatter(x=sp["Date"], y=pct, name="S&P 500",
                    line=dict(color="#5a6b85", width=1.5, dash="dot"),
                    hovertemplate="%{y:.2f}%<extra>S&P 500</extra>"))
            except: pass
            fig.add_hline(y=0, line_color=C_BORDER, line_width=1)
            lay = base_layout(340); lay["yaxis"]["ticksuffix"] = "%"
            fig.update_layout(**lay); st.plotly_chart(fig, use_container_width=True)
            st.caption("Each line shows % change over the period, starting from 0. The dotted line is the S&P 500.")
        else:
            info_box("Add your holdings (sidebar → ➕ Add Existing Holding) to see performance here.")
    with right:
        st.markdown("## Allocation")
        if stats["rows"]:
            labels = [r["Ticker"] for r in stats["rows"]] + ["Dollars"]
            values = [r["Value"] for r in stats["rows"]] + [portfolio.cash]
            cols2 = (CHART_COLORS + ["#3a4a66"])[:len(labels)]
            fig2 = go.Figure(go.Pie(labels=labels, values=values, hole=0.52,
                marker=dict(colors=cols2, line=dict(color=C_BG, width=2)),
                textinfo="label+percent",
                textfont=dict(family="Share Tech Mono, monospace", size=12, color=C_TEXT),
                hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>"))
            lay2 = base_layout(300); lay2["showlegend"] = False
            fig2.update_layout(**lay2); st.plotly_chart(fig2, use_container_width=True)
            st.caption("How your money is split across holdings — the same view a bank or broker shows you.")
        else:
            info_box("No holdings yet.")

# ── SCREEN: Browse ───────────────────────────────────────────
elif screen == "Browse":
    crt_boot("Browse // scan the market")
    col_s, col_p = st.columns([3, 1])
    with col_s:
        lookup = st.text_input("Ticker symbol", placeholder="e.g. TSLA, META, AMZN", key="lookup").upper().strip()
    with col_p:
        pm2 = {"1m":"1mo","3m":"3mo","6m":"6mo","1y":"1y","2y":"2y","5y":"5y"}
        lp_label = st.selectbox("Period", list(pm2.keys()), index=3, key="lu_period")
    if lookup:
        try:
            lu_price = fetch_price(lookup); lu_info = fetch_ticker_info(lookup)
            lu_df = fetch_chart_data(lookup, pm2[lp_label])
            h1, h2, _ = st.columns([2, 1, 1])
            with h1:
                st.markdown(f'<span class="ticker-badge">{lookup}</span>&nbsp;&nbsp;'
                            f'<span style="color:{C_MUTED};font-size:0.95rem">{lu_info.get("name", lookup)}</span>',
                            unsafe_allow_html=True)
                if lu_info.get("sector"): st.caption(lu_info["sector"])
            with h2:
                prev = lu_info.get("prev_close") or lu_price
                chg = lu_price - prev; chg_pct = chg/prev*100 if prev else 0
                sign = "+" if chg >= 0 else ""; cls = "price-up" if chg >= 0 else "price-down"
                st.markdown(f'<p class="price-big">${lu_price:,.2f}</p>'
                            f'<p class="{cls}">{sign}{chg:.2f} ({sign}{chg_pct:.2f}%) today</p>', unsafe_allow_html=True)
            s1, s2, s3, s4 = st.columns(4)
            mc = lu_info.get("market_cap")
            mc_s = (f"${mc/1e12:.2f}T" if mc and mc>1e12 else f"${mc/1e9:.1f}B" if mc else "—")
            s1.metric("Market Cap", mc_s)
            s2.metric("P/E Ratio", f"{lu_info['pe']:.1f}" if lu_info.get("pe") else "—")
            s3.metric("52W High", f"${lu_info['52w_high']:,.2f}" if lu_info.get("52w_high") else "—")
            s4.metric("52W Low", f"${lu_info['52w_low']:,.2f}" if lu_info.get("52w_low") else "—")
            if not lu_df.empty:
                fig3 = go.Figure()
                fig3.add_trace(go.Candlestick(x=lu_df["Date"],
                    open=lu_df["Open"].squeeze(), high=lu_df["High"].squeeze(),
                    low=lu_df["Low"].squeeze(), close=lu_df["Close"].squeeze(),
                    increasing_line_color=C_GREEN_LIGHT, decreasing_line_color=C_RED_LIGHT, name=lookup))
                fig3.add_trace(go.Bar(x=lu_df["Date"], y=lu_df["Volume"].squeeze(),
                    marker_color=C_CYAN, name="Volume", yaxis="y2", opacity=0.2))
                lay3 = base_layout(380)
                lay3["xaxis"]["rangeslider_visible"] = False; lay3["xaxis"]["showgrid"] = False
                lay3["yaxis2"] = dict(overlaying="y", side="left", showgrid=False, showticklabels=False)
                fig3.update_layout(**lay3); st.plotly_chart(fig3, use_container_width=True)
            st.markdown("## ◉ Bram's Take")
            disclaimer()
            sig = compute_signals(lookup)
            if sig.get("ok"):
                lean = sig["lean"]
                lean_cls = ("read-lean-bull" if lean=="Bullish-leaning" else
                            "read-lean-bear" if lean=="Bearish-leaning" else "read-lean-neutral")
                lines = "".join(f'<div class="signal-line">• {o}</div>' for o in sig["obs"])
                st.markdown(f'<div class="read-card"><div class="signal-line" style="color:#d7fbff;font-size:1rem;margin-bottom:8px">'
                            f'"{keeper_read_line(lean, lookup)}"</div>'
                            f'<div>Overall: <span class="{lean_cls}">{lean}</span></div>'
                            f'<div style="margin-top:8px">{lines}</div></div>', unsafe_allow_html=True)
            else:
                info_box("Not enough price history to read this one.")
            st.markdown("## Trade This Stock")
            qt_shares = st.number_input("Shares", min_value=0.0001, step=1.0, value=1.0, key="lu_shares")
            st.caption(f"Estimated value: ${qt_shares * lu_price:,.2f}")
            b1, b2, _ = st.columns([1, 1, 2])
            with b1:
                st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
                if st.button(f"▲ BUY {lookup}", key="lu_buy"):
                    set_pending("BUY", lookup, qt_shares, lu_price); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with b2:
                st.markdown('<div class="sell-btn">', unsafe_allow_html=True)
                if st.button(f"▼ SELL {lookup}", key="lu_sell"):
                    set_pending("SELL", lookup, qt_shares, lu_price); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Couldn't load data for **{lookup}**: {e}")
    else:
        info_box("Enter a ticker above to see price data, charts, and Bram's read.")

# ── SCREEN: Holdings ─────────────────────────────────────────
elif screen == "Holdings":
    crt_boot("Holdings // your positions")
    if stats["rows"]:
        df_hold = pd.DataFrame(stats["rows"]).sort_values("Value", ascending=False)
        fmt = df_hold.copy()
        fmt["Avg Cost"] = fmt["Avg Cost"].map("${:,.2f}".format)
        fmt["Price"]    = fmt["Price"].map("${:,.2f}".format)
        fmt["Value"]    = fmt["Value"].map("${:,.2f}".format)
        fmt["P&L ($)"]  = fmt["P&L ($)"].map(lambda x: f"+${x:,.2f}" if x>=0 else f"-${abs(x):,.2f}")
        fmt["P&L (%)"]  = fmt["P&L (%)"].map(lambda x: f"+{x:.2f}%" if x>=0 else f"{x:.2f}%")
        fmt["Weight"]   = fmt["Weight"].map("{:.1f}%".format)
        fmt["Shares"]   = fmt["Shares"].map("{:.4f}".format)
        st.dataframe(fmt, use_container_width=True, hide_index=True,
                     column_config={"Weight": st.column_config.TextColumn("% of Portfolio")})
        st.caption("**Avg Cost** = what you paid per share · **P&L** = gain/loss in $ and % · "
                   "**% of Portfolio** = how much of your total this holding makes up.")
        st.markdown("---")
        st.markdown("## Gain/Loss by Position")
        df_bar = pd.DataFrame(stats["rows"])
        fig4 = go.Figure(go.Bar(x=df_bar["Ticker"], y=df_bar["P&L ($)"],
            marker_color=[C_GREEN_LIGHT if x>=0 else C_RED_LIGHT for x in df_bar["P&L ($)"]],
            text=df_bar.apply(lambda r: (f"+${r['P&L ($)']:,.0f}" if r['P&L ($)']>=0
                                         else f"-${abs(r['P&L ($)']):,.0f}") + f"<br>{r['P&L (%)']:+.1f}%", axis=1),
            textposition="outside",
            textfont=dict(family="Share Tech Mono, monospace", size=11, color=C_TEXT)))
        fig4.add_hline(y=0, line_color=C_BORDER, line_width=1.5)
        lay4 = base_layout(300); lay4["xaxis"]["showgrid"] = False
        lay4["yaxis"]["tickprefix"] = "$"; lay4["showlegend"] = False
        fig4.update_layout(**lay4); st.plotly_chart(fig4, use_container_width=True)
    else:
        info_box("No holdings yet. In the sidebar, open <b>➕ Add Existing Holding</b> to enter stocks "
                 "you already own, or use <b>⚡ Trade at Market</b> to buy new ones.")

# ── SCREEN: Bram's Take ──────────────────────────────────────
elif screen == "Bram's Take":
    crt_boot("Bram's Take // the broker reads your shelf")
    disclaimer()
    if stats["rows"]:
        for row in stats["rows"]:
            t = row["Ticker"]
            try:
                sig = compute_signals(t)
                if not sig.get("ok"):
                    st.markdown(f'<div class="read-card"><b>{t}</b> — not enough history to read.</div>', unsafe_allow_html=True); continue
                lean = sig["lean"]
                lean_cls = ("read-lean-bull" if lean=="Bullish-leaning" else
                            "read-lean-bear" if lean=="Bearish-leaning" else "read-lean-neutral")
                pl_sign = "+" if row["P&L (%)"] >= 0 else ""
                lines = "".join(f'<div class="signal-line">• {o}</div>' for o in sig["obs"])
                st.markdown(f'<div class="read-card"><span class="ticker-badge">{t}</span> &nbsp;'
                            f'<span style="color:{C_MUTED}">your P&L: {pl_sign}{row["P&L (%)"]:.1f}% '
                            f'· {row["Weight"]:.1f}% of portfolio</span><br>'
                            f'<div class="signal-line" style="color:#d7fbff;font-size:1rem;margin:8px 0">"{keeper_read_line(lean, t)}"</div>'
                            f'<div>Overall: <span class="{lean_cls}">{lean}</span></div>'
                            f'<div style="margin-top:6px">{lines}</div></div>', unsafe_allow_html=True)
            except Exception:
                st.markdown(f'<div class="read-card"><b>{t}</b> — couldn\'t read right now.</div>', unsafe_allow_html=True)
    else:
        info_box("Once you've got stocks on your shelf, Bram will read each one here.")
    st.markdown("#### What do these mean?")
    st.caption("**RSI** measures how fast a price has moved recently (under 30 = fell hard/\"oversold\", "
               "over 70 = ran up fast/\"overbought\"). **Moving averages** smooth the price to show the trend. "
               "**Distance from highs/lows** shows where today's price sits in its yearly range. "
               "None of these predict the future — they just describe the past.")

# ── SCREEN: Ledger ───────────────────────────────────────────
elif screen == "Ledger":
    crt_boot("Ledger // the machine remembers")
    if portfolio.transactions:
        tx_rows = [{"Time": tx.timestamp, "Type": tx.action, "Item": tx.ticker, "Shares": tx.shares,
                    "Price": tx.price, "Amount": tx.total, "Balance After": tx.cash_after, "Notes": tx.notes}
                   for tx in reversed(portfolio.transactions)]
        df_tx = pd.DataFrame(tx_rows)
        def colour_type(val):
            c = {"BUY": C_GREEN_LIGHT, "SELL": C_RED_LIGHT, "INCOME": C_GREEN_LIGHT,
                 "EXPENSE": C_RED_LIGHT, "IMPORT": C_GOLD}.get(val, C_MUTED)
            return f"color: {c}; font-weight: 700"
        sty = df_tx.style
        sty = (sty.map if hasattr(sty, "map") else sty.applymap)(colour_type, subset=["Type"])
        sty = sty.format("${:,.2f}", subset=["Price", "Amount", "Balance After"]).format("{:.4f}", subset=["Shares"])
        st.dataframe(sty, use_container_width=True, hide_index=True)
        st.caption("**BUY/SELL** trade stock and move dollars · **INCOME/EXPENSE** adjust dollars "
                   "(dividends, allowance, fees) · **IMPORT** = an existing holding you already owned (no change).")
        st.markdown("---")
        st.markdown("## Dollars Over Time")
        df_cash = pd.DataFrame([{"Time": r["Time"], "Cash": r["Balance After"]} for r in reversed(tx_rows)])
        df_cash["Time"] = pd.to_datetime(df_cash["Time"])
        fig5 = go.Figure(go.Scatter(x=df_cash["Time"], y=df_cash["Cash"],
            fill="tozeroy", fillcolor="rgba(47,230,255,0.10)",
            line=dict(color=C_CYAN, width=2.5), hovertemplate="$%{y:,.2f}<extra>Dollars</extra>"))
        lay5 = base_layout(240); lay5["yaxis"]["tickprefix"] = "$"
        fig5.update_layout(**lay5); st.plotly_chart(fig5, use_container_width=True)
    else:
        info_box("No entries yet. Your ledger fills as you add holdings and trade.")


# ── Auto-save to the browser after any change (one write per action) ──
if HAS_BROWSER_SAVE and portfolio is not None and st.session_state.get("_browser_dirty"):
    browser_save(portfolio)
    st.session_state["_browser_dirty"] = False
