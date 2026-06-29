"""
app.py — The Shop
RPG-style portfolio tracker with a shopkeeper, custom trade prices,
passive income/expense tracking, and educational stock "reads".

pip install streamlit yfinance plotly pandas
streamlit run app.py
"""
from __future__ import annotations
import json, csv, random
from pathlib import Path
from datetime import date, datetime, time as dtime
from dataclasses import dataclass, field, asdict
from typing import Optional

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# ── Files / constants ────────────────────────────────────────
PORTFOLIO_FILE   = "portfolio.json"
TRANSACTION_FILE = "transactions.csv"
BENCHMARK        = "^GSPC"

# Palette — dark RPG
C_BG, C_PANEL, C_CARD = "#13111a", "#1e1b2e", "#252040"
C_GOLD, C_TEXT, C_MUTED = "#d4a017", "#f0e6d3", "#9d8ec0"
C_GREEN, C_GREEN_LIGHT = "#2d6e3a", "#4caf50"
C_RED, C_RED_LIGHT = "#7a2828", "#e05252"
C_BORDER = "#d4a01745"
CHART_COLORS = ["#d4a017","#4caf50","#9d8ec0","#58a6ff",
                "#f44336","#ff9800","#e91e63","#00bcd4"]

# ── Shopkeeper ───────────────────────────────────────────────
KEEPER_NAME, KEEPER_ICON = "Aldric", "🧙"
KEEPER_LINES = {
    "greet":   ["Welcome. Take a look around.",
                "Good to see you. Markets are moving today.",
                "Shop's open. What'll it be?",
                "Back again? Anything catch your eye?"],
    "buy":     ["Nice pick. Added to your portfolio.",
                "Good choice. Hope it works out.",
                "Done deal. Keep an eye on it.",
                "Bought and logged. Good luck out there."],
    "sell":    ["Sold. Cash is back in your pocket.",
                "Done. Sometimes taking the money is the right call.",
                "Logged. You know what you're doing.",
                "Sold — hope the timing was right."],
    "deposit": ["Cash added. Ready to put it to work?",
                "More to work with now.",
                "Funds received. The market's waiting."],
    "income":  ["Coin in the pocket. Nice.",
                "Income logged. Steady earnings, I like it.",
                "Added to your balance."],
    "expense": ["Logged. Expenses are part of the trade.",
                "Noted. Every merchant has costs.",
                "Out it goes. Tracked and recorded."],
    "error":   ["Can't do that one, I'm afraid.",
                "That didn't go through — check the details.",
                "Something's off there."],
    "watch":   ["A couple of your holdings are flashing signals — check the Watch tab.",
                "The charts are restless today. Have a look at the Watch tab.",
                "I've got some reads for you over in the Watch tab."],
}
def keeper_says(key): return random.choice(KEEPER_LINES.get(key, KEEPER_LINES["greet"]))

def trader_rank(port_ret):
    if port_ret >= 30: return "🌟 Legendary Broker"
    if port_ret >= 15: return "⚔️ Master Merchant"
    if port_ret >= 5:  return "🛡️ Journeyman Trader"
    if port_ret >= 0:  return "📜 Apprentice Trader"
    return "🔰 Novice Trader"

st.set_page_config(page_title="The Shop", page_icon="⚔️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Crimson+Text:ital@0;1&family=Rajdhani:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; font-size: 16px; }
.stApp { background-color: #13111a; color: #f0e6d3; }
section[data-testid="stSidebar"] { background: #1e1b2e !important; border-right: 2px solid #d4a01745; }
section[data-testid="stSidebar"] * { color: #f0e6d3 !important; }
section[data-testid="stSidebar"] label { color: #d4a017 !important; font-size: 0.78rem !important; letter-spacing:.07em !important; text-transform: uppercase !important; }
section[data-testid="stSidebar"] small { color: #9d8ec0 !important; }
[data-testid="metric-container"] { background: #252040; border: 1px solid #d4a01745; border-radius: 6px; padding: 14px 18px; }
[data-testid="metric-container"] label { color: #9d8ec0 !important; font-size: 0.68rem !important; letter-spacing:.09em !important; text-transform: uppercase !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-family: 'Cinzel', serif; font-size: 1.3rem; color: #f0e6d3; }
[data-testid="stMetricDelta"] svg { display: none; }
div.stButton > button { border-radius: 4px; font-weight: 700; font-size: 0.9rem; letter-spacing:.08em; padding: 9px 18px; transition: all .15s; width: 100%; }
div.stButton > button:hover { filter: brightness(1.15); transform: translateY(-1px); }
.buy-btn  > div.stButton > button { background:#2d6e3a; color:#f0e6d3; border:1px solid #4caf5080; }
.sell-btn > div.stButton > button { background:#7a2828; color:#f0e6d3; border:1px solid #e0525280; }
.neutral-btn > div.stButton > button { background:#2a2050; color:#f0e6d3; border:1px solid #d4a01745; }
input, textarea, [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input { background:#252040 !important; border:1px solid #d4a01760 !important; color:#f0e6d3 !important; border-radius:4px !important; font-size:1rem !important; }
h1 { font-family:'Cinzel',serif !important; color:#d4a017 !important; font-size:1.8rem !important; letter-spacing:.08em !important; }
h2 { font-family:'Cinzel',serif !important; color:#f0e6d3 !important; font-size:1rem !important; border-bottom:1px solid #d4a01740 !important; padding-bottom:6px !important; margin-top:0 !important; letter-spacing:.05em !important; }
h3 { color:#9d8ec0 !important; font-size:0.78rem !important; text-transform:uppercase !important; letter-spacing:.1em !important; font-weight:600 !important; }
.stTabs [data-baseweb="tab-list"] { background:#1e1b2e; border-radius:6px; padding:4px; gap:2px; }
.stTabs [data-baseweb="tab"] { color:#9d8ec0; font-size:0.86rem; letter-spacing:.04em; font-weight:600; border-radius:4px; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { background:#252040; color:#d4a017; }
[data-testid="stDataFrame"] { background:#1e1b2e; border:1px solid #d4a01740; border-radius:6px; }
[data-testid="stAlert"] { border-radius:6px; }
hr { border-color:#d4a01730; margin:12px 0; }
[data-testid="stSelectbox"] > div > div { background:#252040 !important; border-color:#d4a01760 !important; color:#f0e6d3 !important; }
[data-testid="stFileUploadDropzone"] { background:#252040 !important; border-color:#d4a01760 !important; }
[data-testid="stCaptionContainer"] p { color:#9d8ec0 !important; }
.stExpander { border:1px solid #d4a01740 !important; border-radius:6px !important; background:#1e1b2e !important; }
.dialogue-box { background:#252040; border:1px solid #d4a017; border-radius:6px; padding:14px 16px; margin:0 0 16px 0; }
.dialogue-name { font-family:'Cinzel',serif; color:#d4a017; font-size:0.76rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; margin-bottom:6px; }
.dialogue-text { font-family:'Crimson Text',Georgia,serif; color:#f0e6d3; font-size:1.05rem; line-height:1.45; font-style:italic; }
.dialogue-cursor { display:inline-block; width:8px; height:12px; background:#d4a017; margin-left:4px; animation:blink 1s step-end infinite; vertical-align:middle; }
@keyframes blink { 50% { opacity:0; } }
.rank-badge { display:inline-block; background:#2a2050; border:1px solid #d4a01760; border-radius:4px; padding:4px 10px; font-size:0.8rem; color:#d4a017; letter-spacing:.05em; font-weight:600; }
.ticker-badge { display:inline-block; background:#252040; border:1px solid #d4a017; color:#d4a017; font-family:'Cinzel',serif; font-size:0.85rem; font-weight:700; padding:3px 10px; border-radius:4px; letter-spacing:.08em; }
.price-big { font-family:'Cinzel',serif; font-size:1.9rem; font-weight:700; color:#f0e6d3; margin:0; }
.price-up { color:#4caf50; font-size:0.95rem; font-weight:600; }
.price-down { color:#e05252; font-size:0.95rem; font-weight:600; }
.info-box { background:#252040; border:1px solid #d4a01740; padding:12px 16px; border-radius:6px; color:#9d8ec0; font-size:0.95rem; }
.notif-success { background:#1a2e1a; border:1px solid #4caf5080; padding:12px 16px; border-radius:6px; color:#4caf50; font-size:0.95rem; font-weight:600; margin-bottom:12px; }
.notif-error { background:#2e1a1a; border:1px solid #e0525280; padding:12px 16px; border-radius:6px; color:#e05252; font-size:0.95rem; font-weight:600; margin-bottom:12px; }
.disclaimer { background:#2a230f; border:1px solid #d4a01770; border-left:4px solid #d4a017; padding:12px 16px; border-radius:6px; color:#e8d5a3; font-size:0.88rem; line-height:1.5; margin:8px 0 16px 0; }
.read-card { background:#252040; border:1px solid #d4a01740; border-radius:6px; padding:14px 16px; margin-bottom:10px; }
.read-lean-bull { color:#4caf50; font-weight:700; font-family:'Cinzel',serif; letter-spacing:.05em; }
.read-lean-bear { color:#e05252; font-weight:700; font-family:'Cinzel',serif; letter-spacing:.05em; }
.read-lean-neutral { color:#9d8ec0; font-weight:700; font-family:'Cinzel',serif; letter-spacing:.05em; }
.signal-line { color:#c9bfe0; font-size:0.92rem; margin:3px 0; }
</style>""", unsafe_allow_html=True)


def info_box(msg): st.markdown(f'<div class="info-box">{msg}</div>', unsafe_allow_html=True)
def disclaimer():
    st.markdown(
        '<div class="disclaimer">⚠️ <b>Aldric\'s reads are a game feature, not financial advice.</b> '
        'They\'re based on simple technical indicators (RSI, moving averages, price vs. recent highs/lows) '
        'that only describe <i>past</i> price behavior — they are frequently wrong about the future. '
        'Always do your own research and talk to a trusted adult before trading real money.</div>',
        unsafe_allow_html=True)

def base_layout(height=340):
    return dict(paper_bgcolor=C_CARD, plot_bgcolor=C_PANEL,
        font=dict(family="Rajdhani, sans-serif", color=C_MUTED, size=12),
        xaxis=dict(gridcolor="#2a2a4a", showgrid=True, zeroline=False, color=C_MUTED),
        yaxis=dict(gridcolor="#2a2a4a", showgrid=True, zeroline=False, color=C_MUTED),
        legend=dict(bgcolor=C_PANEL, bordercolor=C_BORDER, borderwidth=1,
                    font=dict(family="Rajdhani, sans-serif", size=12, color=C_TEXT)),
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
    recurring: list = field(default_factory=list)   # list of {label, amount, kind, cadence}


# ── Persistence ──────────────────────────────────────────────
def save_portfolio(p: Portfolio):
    data = {"cash": p.cash, "inception_date": p.inception_date,
            "benchmark_start_price": p.benchmark_start_price,
            "positions": {t: asdict(pos) for t, pos in p.positions.items()},
            "transactions": [asdict(tx) for tx in p.transactions],
            "recurring": p.recurring}
    with open(PORTFOLIO_FILE, "w") as f: json.dump(data, f, indent=2)

def load_portfolio() -> Optional[Portfolio]:
    if not Path(PORTFOLIO_FILE).exists(): return None
    with open(PORTFOLIO_FILE) as f: data = json.load(f)
    positions = {t: Position(**v) for t, v in data.get("positions", {}).items()}
    txs = [Transaction(**tx) for tx in data.get("transactions", [])]
    return Portfolio(cash=data["cash"], positions=positions, transactions=txs,
                     inception_date=data.get("inception_date", date.today().isoformat()),
                     benchmark_start_price=data.get("benchmark_start_price"),
                     recurring=data.get("recurring", []))

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
    return {t: float(raw["Close"][t].iloc[-1]) for t in tickers if t in raw["Close"]}

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
                "prev_close": i.get("previousClose"),
                "div_yield": i.get("dividendYield")}
    except: return {}

def _close_series(df) -> pd.Series:
    c = df["Close"]
    if isinstance(c, pd.DataFrame): c = c.iloc[:, 0]
    return c.astype(float).reset_index(drop=True)


# ── Technical "reads" (educational, not advice) ──────────────
def compute_rsi(close: pd.Series, period=14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=600)
def compute_signals(ticker: str) -> dict:
    """Returns simple, transparent indicators + plain-language observations."""
    df = fetch_chart_data(ticker, "1y")
    if df.empty or len(df) < 20:
        return {"ok": False}
    close = _close_series(df)
    price = float(close.iloc[-1])
    rsi = float(compute_rsi(close).iloc[-1])
    sma50  = float(close.rolling(50).mean().iloc[-1])  if len(close) >= 50  else None
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    hi, lo = float(close.max()), float(close.min())
    pct_from_high = (price - hi) / hi * 100
    pct_from_low  = (price - lo) / lo * 100

    obs, score = [], 0.0
    if rsi == rsi:  # not NaN
        if rsi < 30:
            obs.append(f"RSI is {rsi:.0f} — under 30, which traders often call \"oversold\" (it's fallen hard recently)."); score += 1
        elif rsi > 70:
            obs.append(f"RSI is {rsi:.0f} — over 70, often called \"overbought\" (it's run up fast recently)."); score -= 1
        else:
            obs.append(f"RSI is {rsi:.0f} — in the neutral middle zone.")
    if sma50 and sma200:
        if price > sma50 > sma200:
            obs.append("Price is above both its 50-day and 200-day average — a classic uptrend shape."); score += 1
        elif price < sma50 < sma200:
            obs.append("Price is below both its 50-day and 200-day average — a downtrend shape."); score -= 1
        else:
            obs.append("The 50-day and 200-day averages are tangled — no clear trend.")
    elif sma50:
        obs.append("Above its 50-day average." if price > sma50 else "Below its 50-day average.")
        score += 0.5 if price > sma50 else -0.5
    if pct_from_high <= -20:
        obs.append(f"It's {pct_from_high:.0f}% below its 1-year high."); score += 0.5
    elif pct_from_high >= -3:
        obs.append("It's hovering near its 1-year high."); score -= 0.25
    obs.append(f"Up {pct_from_low:.0f}% from its 1-year low.")

    if score >= 1:    lean = "Bullish-leaning"
    elif score <= -1: lean = "Bearish-leaning"
    else:             lean = "Neutral"
    return {"ok": True, "price": price, "rsi": rsi, "sma50": sma50, "sma200": sma200,
            "pct_from_high": pct_from_high, "pct_from_low": pct_from_low,
            "obs": obs, "lean": lean, "score": score}

def aldric_read_line(lean: str, ticker: str) -> str:
    if lean == "Bullish-leaning":
        return random.choice([
            f"The charts on {ticker} look perky to me — but charts lie half the time.",
            f"{ticker}'s got an interesting setup. Could be one to watch.",
            f"If I were a betting man I'd say {ticker} looks healthy — but don't bet on my say-so."])
    if lean == "Bearish-leaning":
        return random.choice([
            f"{ticker} looks tired on the charts. I'd be careful.",
            f"Something's draggin' on {ticker}. Watch it before you act.",
            f"I'd not rush into {ticker} right now — but that's just chart-reading."])
    return random.choice([
        f"{ticker}'s in no-man's-land — no strong signal either way.",
        f"Can't read {ticker} clearly today. Mixed signals.",
        f"{ticker} looks middling to me. Patience, maybe."])


# ── Trading / ledger logic ───────────────────────────────────
def _stamp(custom_date: Optional[date]) -> str:
    if custom_date:
        return datetime.combine(custom_date, dtime(12, 0)).strftime("%Y-%m-%d %H:%M:%S")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def execute_buy(p, ticker, shares, price=None, notes="", custom_date=None):
    try:
        if shares <= 0: return False, "Share quantity must be positive."
        mp = price if price else fetch_price(ticker)
        total = round(shares * mp, 4)
        if total > p.cash: return False, f"Not enough cash. Need ${total:,.2f}, you have ${p.cash:,.2f}."
        if ticker in p.positions:
            pos = p.positions[ticker]; ns = pos.shares + shares
            p.positions[ticker] = Position(ticker, ns, (pos.cost_basis + total) / ns)
        else:
            p.positions[ticker] = Position(ticker, shares, mp)
        p.cash = round(p.cash - total, 4)
        tx = Transaction(_stamp(custom_date), "BUY", ticker, shares, mp, total, p.cash, notes)
        p.transactions.append(tx); append_tx_log(tx); save_portfolio(p)
        return True, f"Bought {shares} × {ticker} @ ${mp:,.2f} = ${total:,.2f}"
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
        return True, f"Sold {shares} × {ticker} @ ${mp:,.2f} = ${proceeds:,.2f}"
    except Exception as e: return False, str(e)

def post_cashflow(p, kind, amount, label, custom_date=None):
    """kind = 'INCOME' or 'EXPENSE'. Adjusts cash and logs to history."""
    try:
        if amount <= 0: return False, "Amount must be positive."
        if kind == "INCOME":
            p.cash = round(p.cash + amount, 2)
        else:
            p.cash = round(p.cash - amount, 2)
        tx = Transaction(_stamp(custom_date), kind, label or kind.title(),
                         0.0, 0.0, round(amount, 2), p.cash, "")
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
if "trade_msg" not in st.session_state: st.session_state.trade_msg = None
if "dialogue"  not in st.session_state: st.session_state.dialogue  = keeper_says("greet")
portfolio: Optional[Portfolio] = st.session_state.portfolio


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        f'<div class="dialogue-box"><div class="dialogue-name">{KEEPER_ICON} {KEEPER_NAME}</div>'
        f'<div class="dialogue-text">"{st.session_state.dialogue}"'
        f'<span class="dialogue-cursor"></span></div></div>', unsafe_allow_html=True)

    if portfolio is None:
        st.markdown("### New Portfolio")
        init_cash = st.number_input("Starting Cash ($)", value=10000.0, min_value=0.0, step=500.0)
        uploaded = st.file_uploader("Import Holdings CSV", type="csv",
                                    help="Columns: ticker, shares, avg_cost")
        st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
        if st.button("⚔️  Open the Shop"):
            positions = load_holdings_csv(uploaded) if uploaded else {}
            spx = None
            try: spx = fetch_price(BENCHMARK)
            except: pass
            p = Portfolio(cash=init_cash, positions=positions, benchmark_start_price=spx)
            save_portfolio(p); st.session_state.portfolio = p
            st.session_state.dialogue = "Good. Let's get started. What are you looking to trade?"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("---")
        st.caption("Already have a save file?")
        jup = st.file_uploader("Restore portfolio.json", type="json", key="json_restore")
        if jup:
            data = json.load(jup)
            positions = {t: Position(**v) for t, v in data.get("positions", {}).items()}
            txs = [Transaction(**tx) for tx in data.get("transactions", [])]
            p = Portfolio(cash=data["cash"], positions=positions, transactions=txs,
                          inception_date=data.get("inception_date", date.today().isoformat()),
                          benchmark_start_price=data.get("benchmark_start_price"),
                          recurring=data.get("recurring", []))
            st.session_state.portfolio = p; save_portfolio(p)
            st.session_state.dialogue = "Ah, you're back. Let's see how things stand."
            st.rerun()
    else:
        if portfolio.positions:
            try:
                s0 = get_stats(portfolio)
                st.markdown(f'<div class="rank-badge">{trader_rank(s0["port_ret"])}</div>',
                            unsafe_allow_html=True)
                st.markdown("&nbsp;", unsafe_allow_html=True)
            except: pass

        st.markdown("### Trade")
        trade_ticker = st.text_input("Ticker", placeholder="e.g. AAPL", key="trade_ticker").upper().strip()
        trade_shares = st.number_input("Shares", min_value=0.0001, step=1.0, value=1.0, key="trade_shares")

        # Custom price / date for recording past trades
        use_custom = st.checkbox("I bought/sold at a different price or date")
        custom_price, custom_dt = None, None
        if use_custom:
            custom_price = st.number_input("Price per share ($)", min_value=0.0,
                                           step=1.0, value=0.0, key="custom_price")
            custom_price = custom_price if custom_price > 0 else None
            custom_dt = st.date_input("Trade date", value=date.today(),
                                      max_value=date.today(), key="custom_dt")
        preview_price = None
        if trade_ticker:
            try:
                live_p = fetch_price(trade_ticker)
                use_p = custom_price if custom_price else live_p
                preview_price = use_p
                est = trade_shares * use_p
                tag = " (your price)" if custom_price else " (live)"
                st.caption(f"${use_p:,.2f}/share{tag}  ·  est. ${est:,.2f}")
            except: st.caption("⚠ Can't find that ticker")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
            if st.button("▲ BUY", key="sb_buy") and trade_ticker:
                ok, msg = execute_buy(portfolio, trade_ticker, trade_shares,
                                      preview_price, custom_date=custom_dt)
                st.session_state.trade_msg = ("success" if ok else "error", msg)
                st.session_state.dialogue  = keeper_says("buy" if ok else "error")
                fetch_prices.clear(); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="sell-btn">', unsafe_allow_html=True)
            if st.button("▼ SELL", key="sb_sell") and trade_ticker:
                ok, msg = execute_sell(portfolio, trade_ticker, trade_shares,
                                       preview_price, custom_date=custom_dt)
                st.session_state.trade_msg = ("success" if ok else "error", msg)
                st.session_state.dialogue  = keeper_says("sell" if ok else "error")
                fetch_prices.clear(); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 💰 Income & Expenses")
        with st.expander("Log income or expense"):
            flow_kind  = st.radio("Type", ["Income", "Expense"], horizontal=True, key="flow_kind")
            flow_label = st.text_input("Label", placeholder="e.g. Dividend, Allowance, Fee", key="flow_label")
            flow_amt   = st.number_input("Amount ($)", min_value=0.0, step=10.0, value=0.0, key="flow_amt")
            flow_custom = st.checkbox("Use a past date", key="flow_custom")
            flow_dt = st.date_input("Date", value=date.today(), max_value=date.today(),
                                    key="flow_dt") if flow_custom else None
            st.markdown('<div class="neutral-btn">', unsafe_allow_html=True)
            if st.button("Log it"):
                kind = "INCOME" if flow_kind == "Income" else "EXPENSE"
                ok, msg = post_cashflow(portfolio, kind, flow_amt, flow_label, flow_dt)
                st.session_state.trade_msg = ("success" if ok else "error", msg)
                st.session_state.dialogue  = keeper_says("income" if (ok and kind=="INCOME") else
                                                         "expense" if ok else "error")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        with st.expander("Recurring reminders"):
            st.caption("Save a recurring item, then post it with one click whenever it's due. "
                       "(The app can't auto-charge — you post each one.)")
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
                st.markdown(f'<small>{sign}${item["amount"]:,.2f} · {item["label"]} '
                            f'({item["cadence"]})</small>', unsafe_allow_html=True)
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
        st.markdown("### Export")
        if Path(PORTFOLIO_FILE).exists():
            with open(PORTFOLIO_FILE) as f:
                st.download_button("⬇  portfolio.json", f.read(),
                                   file_name="portfolio.json", mime="application/json")
        if Path(TRANSACTION_FILE).exists():
            with open(TRANSACTION_FILE) as f:
                st.download_button("⬇  transactions.csv", f.read(),
                                   file_name="transactions.csv", mime="text/csv")
        st.markdown("---")
        if st.button("🗑  Reset Portfolio"):
            st.session_state.portfolio = None
            st.session_state.dialogue  = keeper_says("greet")
            for fp in [PORTFOLIO_FILE, TRANSACTION_FILE]:
                if Path(fp).exists(): Path(fp).unlink()
            st.rerun()


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if portfolio is None:
    st.markdown("# ⚔️  The Shop")
    st.markdown("---")
    info_box("Open a new portfolio using the sidebar to get started.")
    st.stop()

if st.session_state.trade_msg:
    kind, msg = st.session_state.trade_msg
    cls = "notif-success" if kind == "success" else "notif-error"
    icon = "✔" if kind == "success" else "✘"
    st.markdown(f'<div class="{cls}">{icon}  {msg}</div>', unsafe_allow_html=True)
    st.session_state.trade_msg = None

stats = get_stats(portfolio)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊  Overview", "🔍  Stock Search", "📋  Holdings", "🔮  Aldric's Watch", "🕒  History"])


# ── TAB 1: Overview ──────────────────────────────────────────
with tab1:
    st.markdown("## Your Portfolio")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: st.metric("Total Value", f"${stats['total_val']:,.2f}")
    with k2: st.metric("Cash", f"${stats['cash']:,.2f}",
                       delta=f"{stats['cash_weight']:.1f}% of total", delta_color="off")
    with k3:
        sign = "+" if stats['unrealised'] >= 0 else ""
        st.metric("Total Gain/Loss", f"{sign}${stats['unrealised']:,.2f}",
                  delta=f"{sign}{stats['port_ret']:.2f}%")
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
                    cs = _close_series(df)
                    pct = (cs / float(cs.iloc[0]) - 1) * 100
                    fig.add_trace(go.Scatter(x=df["Date"], y=pct, name=row["Ticker"],
                        line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2.5),
                        hovertemplate="%{y:.2f}%<extra>"+row["Ticker"]+"</extra>"))
                except: pass
            try:
                sp = fetch_chart_data(BENCHMARK, pm[pl]); cs = _close_series(sp)
                pct = (cs / float(cs.iloc[0]) - 1) * 100
                fig.add_trace(go.Scatter(x=sp["Date"], y=pct, name="S&P 500",
                    line=dict(color="#555577", width=1.5, dash="dot"),
                    hovertemplate="%{y:.2f}%<extra>S&P 500</extra>"))
            except: pass
            fig.add_hline(y=0, line_color=C_BORDER, line_width=1)
            lay = base_layout(340); lay["yaxis"]["ticksuffix"] = "%"
            fig.update_layout(**lay); st.plotly_chart(fig, use_container_width=True)
            st.caption("Each line shows % change over the period, starting from 0. The dotted line is the S&P 500.")
        else:
            info_box("Make your first trade to see performance charts here.")
    with right:
        st.markdown("## Allocation")
        if stats["rows"]:
            labels = [r["Ticker"] for r in stats["rows"]] + ["Cash"]
            values = [r["Value"] for r in stats["rows"]] + [portfolio.cash]
            cols = (CHART_COLORS + ["#3a3a5a"])[:len(labels)]
            fig2 = go.Figure(go.Pie(labels=labels, values=values, hole=0.52,
                marker=dict(colors=cols, line=dict(color=C_BG, width=2)),
                textinfo="label+percent",
                textfont=dict(family="Rajdhani, sans-serif", size=12, color=C_TEXT),
                hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>"))
            lay2 = base_layout(300); lay2["showlegend"] = False
            fig2.update_layout(**lay2); st.plotly_chart(fig2, use_container_width=True)
            st.caption("How your money is split across holdings — the same view a bank or broker shows you.")
        else:
            info_box("No positions yet.")


# ── TAB 2: Stock Search ──────────────────────────────────────
with tab2:
    st.markdown("## Stock Search")
    col_s, col_p = st.columns([3, 1])
    with col_s:
        lookup = st.text_input("Ticker symbol", placeholder="e.g. TSLA, META, AMZN", key="lookup").upper().strip()
    with col_p:
        pm2 = {"1m":"1mo","3m":"3mo","6m":"6mo","1y":"1y","2y":"2y","5y":"5y"}
        lp_label = st.selectbox("Period", list(pm2.keys()), index=3, key="lu_period")

    if lookup:
        try:
            lu_price = fetch_price(lookup)
            lu_info  = fetch_ticker_info(lookup)
            lu_df    = fetch_chart_data(lookup, pm2[lp_label])
            h1, h2, _ = st.columns([2, 1, 1])
            with h1:
                st.markdown(f'<span class="ticker-badge">{lookup}</span>&nbsp;&nbsp;'
                            f'<span style="color:{C_MUTED};font-size:0.95rem">{lu_info.get("name", lookup)}</span>',
                            unsafe_allow_html=True)
                if lu_info.get("sector"): st.caption(lu_info["sector"])
            with h2:
                prev = lu_info.get("prev_close") or lu_price
                chg = lu_price - prev; chg_pct = chg/prev*100 if prev else 0
                sign = "+" if chg >= 0 else ""
                cls = "price-up" if chg >= 0 else "price-down"
                st.markdown(f'<p class="price-big">${lu_price:,.2f}</p>'
                            f'<p class="{cls}">{sign}{chg:.2f} ({sign}{chg_pct:.2f}%) today</p>',
                            unsafe_allow_html=True)
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
                    marker_color=C_GOLD, name="Volume", yaxis="y2", opacity=0.25))
                lay3 = base_layout(380)
                lay3["xaxis"]["rangeslider_visible"] = False; lay3["xaxis"]["showgrid"] = False
                lay3["yaxis2"] = dict(overlaying="y", side="left", showgrid=False, showticklabels=False)
                fig3.update_layout(**lay3); st.plotly_chart(fig3, use_container_width=True)

            # Aldric's read
            st.markdown("## 🔮 Aldric's Read")
            disclaimer()
            sig = compute_signals(lookup)
            if sig.get("ok"):
                lean = sig["lean"]
                lean_cls = ("read-lean-bull" if lean=="Bullish-leaning"
                            else "read-lean-bear" if lean=="Bearish-leaning" else "read-lean-neutral")
                lines = "".join(f'<div class="signal-line">• {o}</div>' for o in sig["obs"])
                st.markdown(
                    f'<div class="read-card"><div class="dialogue-text" style="margin-bottom:8px">'
                    f'"{aldric_read_line(lean, lookup)}"</div>'
                    f'<div>Overall: <span class="{lean_cls}">{lean}</span></div>'
                    f'<div style="margin-top:8px">{lines}</div></div>', unsafe_allow_html=True)
            else:
                info_box("Not enough price history to read this one.")

            st.markdown("## Trade This Stock")
            qt_shares = st.number_input("Shares", min_value=0.0001, step=1.0, value=1.0, key="lu_shares")
            st.caption(f"Estimated value: ${qt_shares * lu_price:,.2f}")
            b1, b2, _ = st.columns([1, 1, 3])
            with b1:
                st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
                if st.button(f"▲ BUY {lookup}", key="lu_buy"):
                    ok, msg = execute_buy(portfolio, lookup, qt_shares, lu_price)
                    st.session_state.trade_msg = ("success" if ok else "error", msg)
                    st.session_state.dialogue  = keeper_says("buy" if ok else "error")
                    fetch_prices.clear(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with b2:
                st.markdown('<div class="sell-btn">', unsafe_allow_html=True)
                if st.button(f"▼ SELL {lookup}", key="lu_sell"):
                    ok, msg = execute_sell(portfolio, lookup, qt_shares, lu_price)
                    st.session_state.trade_msg = ("success" if ok else "error", msg)
                    st.session_state.dialogue  = keeper_says("sell" if ok else "error")
                    fetch_prices.clear(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Couldn't load data for **{lookup}**: {e}")
    else:
        info_box("Enter a ticker above to see price data, charts, and Aldric's read.")


# ── TAB 3: Holdings ──────────────────────────────────────────
with tab3:
    st.markdown("## Your Holdings")
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
        st.dataframe(fmt, use_container_width=True, hide_index=True, column_config={
            "Weight": st.column_config.TextColumn("% of Portfolio")})
        st.caption("**Avg Cost** = what you paid per share · **P&L** = gain/loss in $ and % · "
                   "**% of Portfolio** = how much of your total this holding makes up.")
        st.markdown("---")
        st.markdown("## Gain/Loss by Position")
        df_bar = pd.DataFrame(stats["rows"])
        fig4 = go.Figure(go.Bar(x=df_bar["Ticker"], y=df_bar["P&L ($)"],
            marker_color=[C_GREEN_LIGHT if x>=0 else C_RED_LIGHT for x in df_bar["P&L ($)"]],
            text=df_bar.apply(lambda r: (f"+${r['P&L ($)']:,.0f}" if r['P&L ($)']>=0
                                         else f"-${abs(r['P&L ($)']):,.0f}") + f"\n{r['P&L (%)']:+.1f}%", axis=1),
            textposition="outside",
            textfont=dict(family="Rajdhani, sans-serif", size=11, color=C_TEXT)))
        fig4.add_hline(y=0, line_color=C_BORDER, line_width=1.5)
        lay4 = base_layout(300); lay4["xaxis"]["showgrid"] = False
        lay4["yaxis"]["tickprefix"] = "$"; lay4["showlegend"] = False
        fig4.update_layout(**lay4); st.plotly_chart(fig4, use_container_width=True)
    else:
        info_box("You don't have any open positions. Use the sidebar or Stock Search to make a trade.")


# ── TAB 4: Aldric's Watch ────────────────────────────────────
with tab4:
    st.markdown("## 🔮 Aldric's Watch")
    st.markdown(f'<div class="dialogue-box"><div class="dialogue-name">{KEEPER_ICON} {KEEPER_NAME}</div>'
                f'<div class="dialogue-text">"Here\'s how I read each of your holdings. '
                f'Reminder: I\'m reading charts, not the future."</div></div>', unsafe_allow_html=True)
    disclaimer()
    if stats["rows"]:
        for row in stats["rows"]:
            t = row["Ticker"]
            try:
                sig = compute_signals(t)
                if not sig.get("ok"):
                    st.markdown(f'<div class="read-card"><b>{t}</b> — not enough history to read.</div>',
                                unsafe_allow_html=True); continue
                lean = sig["lean"]
                lean_cls = ("read-lean-bull" if lean=="Bullish-leaning"
                            else "read-lean-bear" if lean=="Bearish-leaning" else "read-lean-neutral")
                pl_sign = "+" if row["P&L (%)"] >= 0 else ""
                lines = "".join(f'<div class="signal-line">• {o}</div>' for o in sig["obs"])
                st.markdown(
                    f'<div class="read-card">'
                    f'<span class="ticker-badge">{t}</span> &nbsp;'
                    f'<span style="color:{C_MUTED}">your P&L: {pl_sign}{row["P&L (%)"]:.1f}% '
                    f'· {row["Weight"]:.1f}% of portfolio</span><br>'
                    f'<div class="dialogue-text" style="margin:8px 0">"{aldric_read_line(lean, t)}"</div>'
                    f'<div>Overall: <span class="{lean_cls}">{lean}</span></div>'
                    f'<div style="margin-top:6px">{lines}</div></div>', unsafe_allow_html=True)
            except Exception:
                st.markdown(f'<div class="read-card"><b>{t}</b> — couldn\'t read right now.</div>',
                            unsafe_allow_html=True)
    else:
        info_box("Once you own some stocks, Aldric will share his read on each of them here.")
    st.markdown("#### What do these mean?")
    st.caption("**RSI** measures how fast a price has moved recently (under 30 = fell hard/\"oversold\", "
               "over 70 = ran up fast/\"overbought\"). **Moving averages** smooth out the price to show "
               "the trend. **Distance from highs/lows** shows where today's price sits in its yearly range. "
               "None of these predict the future — they just describe the past.")


# ── TAB 5: History ───────────────────────────────────────────
with tab5:
    st.markdown("## Transaction History")
    if portfolio.transactions:
        tx_rows = []
        for tx in reversed(portfolio.transactions):
            tx_rows.append({"Time": tx.timestamp, "Type": tx.action, "Item": tx.ticker,
                            "Shares": tx.shares, "Price": tx.price, "Amount": tx.total,
                            "Balance After": tx.cash_after, "Notes": tx.notes})
        df_tx = pd.DataFrame(tx_rows)
        def colour_type(val):
            c = {"BUY": C_GREEN_LIGHT, "SELL": C_RED_LIGHT,
                 "INCOME": C_GREEN_LIGHT, "EXPENSE": C_RED_LIGHT}.get(val, C_MUTED)
            return f"color: {c}; font-weight: 700"
        styled = (df_tx.style.map(colour_type, subset=["Type"])
                  .format("${:,.2f}", subset=["Price", "Amount", "Balance After"])
                  .format("{:.4f}", subset=["Shares"]))
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.caption("BUY/SELL move stock · INCOME/EXPENSE adjust your cash (dividends, allowance, fees).")
        st.markdown("---")
        st.markdown("## Cash Balance Over Time")
        df_cash = pd.DataFrame([{"Time": r["Time"], "Cash": r["Balance After"]} for r in reversed(tx_rows)])
        df_cash["Time"] = pd.to_datetime(df_cash["Time"])
        fig5 = go.Figure(go.Scatter(x=df_cash["Time"], y=df_cash["Cash"],
            fill="tozeroy", fillcolor="rgba(212,160,23,0.08)",
            line=dict(color=C_GOLD, width=2.5), hovertemplate="$%{y:,.2f}<extra>Cash</extra>"))
        lay5 = base_layout(240); lay5["yaxis"]["tickprefix"] = "$"
        fig5.update_layout(**lay5); st.plotly_chart(fig5, use_container_width=True)
    else:
        info_box("No transactions yet. Your history will appear here.")
