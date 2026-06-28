"""
app.py  —  Streamlit Portfolio Tracker
=======================================
Run locally:  streamlit run app.py
Deploy free:  https://streamlit.io/cloud  (connect your GitHub repo)

pip install streamlit yfinance plotly pandas
"""

import json
import csv
import time
from pathlib import Path
from datetime import date, datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ─────────────────────────────────────────────────────────────
# Config & constants
# ─────────────────────────────────────────────────────────────
PORTFOLIO_FILE  = "portfolio.json"
TRANSACTION_FILE = "transactions.csv"
BENCHMARK       = "^GSPC"

st.set_page_config(
    page_title="Portfolio Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# Custom CSS  — dark terminal-inspired palette with a single
# neon-green accent; monospaced data, clean sans-serif labels.
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── fonts ── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── page background ── */
.stApp { background: #0d1117; color: #e6edf3; }

/* ── sidebar ── */
section[data-testid="stSidebar"] {
    background: #161b22;
    border-right: 1px solid #21262d;
}

/* ── metric cards ── */
[data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 16px 20px;
}
[data-testid="metric-container"] label { color: #8b949e !important; font-size: 0.72rem; letter-spacing: .06em; text-transform: uppercase; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; font-size: 1.45rem; color: #e6edf3; }
[data-testid="stMetricDelta"] svg { display: none; }

/* ── buttons ── */
div.stButton > button {
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    letter-spacing: .04em;
    padding: 8px 20px;
    transition: opacity .15s;
    border: none;
    width: 100%;
}
div.stButton > button:hover { opacity: .85; }

/* buy = green, sell = red  — applied via parent class set in Python */
.buy-btn  > div.stButton > button { background: #238636; color: #fff; }
.sell-btn > div.stButton > button { background: #da3633; color: #fff; }
.neutral-btn > div.stButton > button { background: #21262d; color: #e6edf3; border: 1px solid #30363d; }

/* ── data tables ── */
[data-testid="stDataFrame"] { background: #161b22; border-radius: 8px; }

/* ── inputs ── */
input, textarea, select,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    background: #21262d !important;
    border: 1px solid #30363d !important;
    color: #e6edf3 !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}

/* ── section headers ── */
h1 { font-family: 'IBM Plex Mono', monospace; color: #39d353; font-size: 1.6rem; }
h2 { color: #e6edf3; font-size: 1.1rem; font-weight: 600; border-bottom: 1px solid #21262d; padding-bottom: 6px; margin-top: 0; }
h3 { color: #8b949e; font-size: 0.85rem; text-transform: uppercase; letter-spacing: .08em; font-weight: 500; }

/* ── success / error / warning boxes ── */
[data-testid="stAlert"] { border-radius: 8px; }

/* ── tabs ── */
.stTabs [data-baseweb="tab-list"] { gap: 2px; background: #161b22; border-radius: 8px; padding: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 6px; color: #8b949e; font-weight: 500; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { background: #21262d; color: #e6edf3; }

/* ── divider ── */
hr { border-color: #21262d; }

/* ── selectbox ── */
[data-testid="stSelectbox"] > div > div {
    background: #21262d !important;
    border-color: #30363d !important;
    color: #e6edf3 !important;
}

/* ticker badge */
.ticker-badge {
    display: inline-block;
    background: #1f2937;
    border: 1px solid #39d353;
    color: #39d353;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
    letter-spacing: .05em;
}

.price-big {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 2rem;
    font-weight: 600;
    color: #e6edf3;
}
.price-change-pos { color: #39d353; font-size: 0.9rem; }
.price-change-neg { color: #f85149; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────
@dataclass
class Position:
    ticker:   str
    shares:   float
    avg_cost: float

    @property
    def cost_basis(self): return self.shares * self.avg_cost


@dataclass
class Transaction:
    timestamp: str
    action:    str
    ticker:    str
    shares:    float
    price:     float
    total:     float
    cash_after: float
    notes:     str = ""


@dataclass
class Portfolio:
    cash:         float
    positions:    dict = field(default_factory=dict)
    transactions: list = field(default_factory=list)
    inception_date: str = field(default_factory=lambda: date.today().isoformat())
    benchmark_start_price: Optional[float] = None


# ─────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────
def save_portfolio(p: Portfolio):
    data = {
        "cash": p.cash,
        "inception_date": p.inception_date,
        "benchmark_start_price": p.benchmark_start_price,
        "positions": {t: asdict(pos) for t, pos in p.positions.items()},
        "transactions": [asdict(tx) for tx in p.transactions],
    }
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_portfolio() -> Optional[Portfolio]:
    if not Path(PORTFOLIO_FILE).exists():
        return None
    with open(PORTFOLIO_FILE) as f:
        data = json.load(f)
    positions = {t: Position(**v) for t, v in data.get("positions", {}).items()}
    transactions = [Transaction(**tx) for tx in data.get("transactions", [])]
    return Portfolio(
        cash=data["cash"],
        positions=positions,
        transactions=transactions,
        inception_date=data.get("inception_date", date.today().isoformat()),
        benchmark_start_price=data.get("benchmark_start_price"),
    )


def load_holdings_csv(uploaded_file) -> dict:
    positions = {}
    content = uploaded_file.read().decode("utf-8").splitlines()
    reader = csv.DictReader(content)
    for row in reader:
        t = row["ticker"].strip().upper()
        positions[t] = Position(t, float(row["shares"]), float(row["avg_cost"]))
    return positions


def append_transaction_log(tx: Transaction):
    write_header = not Path(TRANSACTION_FILE).exists()
    with open(TRANSACTION_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(tx).keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(tx))


# ─────────────────────────────────────────────────────────────
# Market Data  (cached to avoid hammering yfinance)
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_price(ticker: str) -> float:
    info = yf.Ticker(ticker).fast_info
    p = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
    if not p:
        raise ValueError(f"No price found for {ticker}")
    return float(p)


@st.cache_data(ttl=60)
def fetch_prices(tickers: tuple) -> dict:
    if not tickers:
        return {}
    if len(tickers) == 1:
        return {tickers[0]: fetch_price(tickers[0])}
    raw = yf.download(list(tickers), period="1d", progress=False, auto_adjust=True)
    return {t: float(raw["Close"][t].iloc[-1]) for t in tickers if t in raw["Close"]}


@st.cache_data(ttl=300)
def fetch_chart_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    df.reset_index(inplace=True)
    return df


@st.cache_data(ttl=60)
def fetch_ticker_info(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        return {
            "name":    info.get("longName", ticker),
            "sector":  info.get("sector", "—"),
            "market_cap": info.get("marketCap"),
            "pe":      info.get("trailingPE"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low":  info.get("fiftyTwoWeekLow"),
            "volume":   info.get("volume"),
            "prev_close": info.get("previousClose"),
        }
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────
# Core Trading Logic
# ─────────────────────────────────────────────────────────────
def execute_buy(portfolio: Portfolio, ticker: str, shares: float,
                price: float = None, notes: str = "") -> tuple[bool, str]:
    try:
        if shares <= 0:
            return False, "Share quantity must be positive."
        market_price = price or fetch_price(ticker)
        total = round(shares * market_price, 4)
        if total > portfolio.cash:
            return False, f"Need ${total:,.2f} but only ${portfolio.cash:,.2f} cash available."
        if ticker in portfolio.positions:
            pos = portfolio.positions[ticker]
            new_shares = pos.shares + shares
            new_avg = (pos.cost_basis + total) / new_shares
            portfolio.positions[ticker] = Position(ticker, new_shares, new_avg)
        else:
            portfolio.positions[ticker] = Position(ticker, shares, market_price)
        portfolio.cash = round(portfolio.cash - total, 4)
        tx = Transaction(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action="BUY", ticker=ticker, shares=shares,
            price=market_price, total=total, cash_after=portfolio.cash, notes=notes,
        )
        portfolio.transactions.append(tx)
        append_transaction_log(tx)
        save_portfolio(portfolio)
        return True, f"Bought {shares} × {ticker} @ ${market_price:,.2f}"
    except Exception as e:
        return False, str(e)


def execute_sell(portfolio: Portfolio, ticker: str, shares: float,
                 price: float = None, notes: str = "") -> tuple[bool, str]:
    try:
        if shares <= 0:
            return False, "Share quantity must be positive."
        if ticker not in portfolio.positions:
            return False, f"No position in {ticker}."
        pos = portfolio.positions[ticker]
        if shares > pos.shares:
            return False, f"Only holding {pos.shares:.2f} shares of {ticker}."
        market_price = price or fetch_price(ticker)
        proceeds = round(shares * market_price, 4)
        remaining = round(pos.shares - shares, 8)
        if remaining < 1e-6:
            del portfolio.positions[ticker]
        else:
            portfolio.positions[ticker] = Position(ticker, remaining, pos.avg_cost)
        portfolio.cash = round(portfolio.cash + proceeds, 4)
        tx = Transaction(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action="SELL", ticker=ticker, shares=shares,
            price=market_price, total=proceeds, cash_after=portfolio.cash, notes=notes,
        )
        portfolio.transactions.append(tx)
        append_transaction_log(tx)
        save_portfolio(portfolio)
        return True, f"Sold {shares} × {ticker} @ ${market_price:,.2f}"
    except Exception as e:
        return False, str(e)


def get_portfolio_stats(portfolio: Portfolio):
    tickers = tuple(portfolio.positions.keys())
    live = fetch_prices(tickers)
    rows, total_mktval, total_cost = [], 0.0, 0.0
    for t, pos in portfolio.positions.items():
        lp  = live.get(t, pos.avg_cost)
        mv  = pos.shares * lp
        pnl = (lp - pos.avg_cost) * pos.shares
        pnl_pct = (lp - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost else 0
        rows.append({
            "Ticker": t, "Shares": pos.shares, "Avg Cost": pos.avg_cost,
            "Price": lp, "Mkt Value": mv, "P&L ($)": pnl, "P&L (%)": pnl_pct,
            "Weight (%)": 0,
        })
        total_mktval += mv
        total_cost   += pos.cost_basis
    total_val = portfolio.cash + total_mktval
    for r in rows:
        r["Weight (%)"] = r["Mkt Value"] / total_val * 100 if total_val else 0
    unrealised = total_mktval - total_cost
    port_ret   = (unrealised / total_cost * 100) if total_cost else 0
    spx_ret    = None
    if portfolio.benchmark_start_price:
        try:
            spx_now = fetch_price(BENCHMARK)
            spx_ret = (spx_now - portfolio.benchmark_start_price) / portfolio.benchmark_start_price * 100
        except Exception:
            pass
    return {
        "rows": rows, "total_val": total_val, "cash": portfolio.cash,
        "total_mktval": total_mktval, "unrealised": unrealised,
        "port_ret": port_ret, "spx_ret": spx_ret,
        "alpha": (port_ret - spx_ret) if spx_ret is not None else None,
    }


# ─────────────────────────────────────────────────────────────
# Session-state bootstrap
# ─────────────────────────────────────────────────────────────
if "portfolio" not in st.session_state:
    saved = load_portfolio()
    if saved:
        st.session_state.portfolio = saved
    else:
        st.session_state.portfolio = None

if "trade_msg" not in st.session_state:
    st.session_state.trade_msg = None

portfolio: Optional[Portfolio] = st.session_state.portfolio


# ─────────────────────────────────────────────────────────────
# ── SIDEBAR ─────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 Portfolio Tracker")
    st.markdown("---")

    # ── Setup ───────────────────────────────────────────────
    if portfolio is None:
        st.markdown("### Start fresh")
        init_cash = st.number_input("Starting cash ($)", value=10000.0,
                                    min_value=0.0, step=500.0)
        uploaded = st.file_uploader("Upload holdings CSV (optional)",
                                    type="csv",
                                    help="Format: ticker,shares,avg_cost")

        st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
        if st.button("Create Portfolio"):
            positions = {}
            if uploaded:
                positions = load_holdings_csv(uploaded)
            spx_price = None
            try:
                spx_price = fetch_price(BENCHMARK)
            except Exception:
                pass
            p = Portfolio(cash=init_cash, positions=positions,
                          benchmark_start_price=spx_price)
            save_portfolio(p)
            st.session_state.portfolio = p
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.caption("Or upload a previously saved portfolio.json:")
        json_upload = st.file_uploader("Restore portfolio.json", type="json",
                                        key="json_restore")
        if json_upload:
            data = json.load(json_upload)
            positions = {t: Position(**v) for t, v in data.get("positions", {}).items()}
            txs = [Transaction(**tx) for tx in data.get("transactions", [])]
            p = Portfolio(
                cash=data["cash"], positions=positions, transactions=txs,
                inception_date=data.get("inception_date", date.today().isoformat()),
                benchmark_start_price=data.get("benchmark_start_price"),
            )
            st.session_state.portfolio = p
            save_portfolio(p)
            st.rerun()

    else:
        # ── Quick-trade panel ──────────────────────────────
        st.markdown("### Quick Trade")
        trade_ticker = st.text_input("Ticker", placeholder="AAPL",
                                      key="trade_ticker").upper().strip()
        trade_shares = st.number_input("Shares", min_value=0.01,
                                        step=1.0, value=1.0, key="trade_shares")

        preview_price = None
        if trade_ticker:
            try:
                preview_price = fetch_price(trade_ticker)
                est = trade_shares * preview_price
                st.caption(f"~${preview_price:,.2f}/share · Est. ${est:,.2f}")
            except Exception:
                st.caption("⚠️ Could not fetch price")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
            if st.button("BUY", key="sidebar_buy"):
                if trade_ticker and trade_shares > 0:
                    ok, msg = execute_buy(portfolio, trade_ticker,
                                          trade_shares, preview_price)
                    st.session_state.trade_msg = ("success" if ok else "error", msg)
                    fetch_prices.clear()
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="sell-btn">', unsafe_allow_html=True)
            if st.button("SELL", key="sidebar_sell"):
                if trade_ticker and trade_shares > 0:
                    ok, msg = execute_sell(portfolio, trade_ticker,
                                           trade_shares, preview_price)
                    st.session_state.trade_msg = ("success" if ok else "error", msg)
                    fetch_prices.clear()
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")

        # ── Cash deposit ──────────────────────────────────
        st.markdown("### Add Cash")
        deposit = st.number_input("Amount ($)", min_value=0.0,
                                   step=100.0, value=0.0, key="deposit")
        st.markdown('<div class="neutral-btn">', unsafe_allow_html=True)
        if st.button("Deposit"):
            if deposit > 0:
                portfolio.cash = round(portfolio.cash + deposit, 2)
                save_portfolio(portfolio)
                st.session_state.trade_msg = ("success", f"Deposited ${deposit:,.2f}")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")

        # ── Export / Reset ─────────────────────────────────
        st.markdown("### Export")
        if Path(PORTFOLIO_FILE).exists():
            with open(PORTFOLIO_FILE) as f:
                st.download_button("⬇ portfolio.json", f.read(),
                                    file_name="portfolio.json", mime="application/json")
        if Path(TRANSACTION_FILE).exists():
            with open(TRANSACTION_FILE) as f:
                st.download_button("⬇ transactions.csv", f.read(),
                                    file_name="transactions.csv", mime="text/csv")

        st.markdown("---")
        if st.button("🗑 Reset portfolio"):
            st.session_state.portfolio = None
            for fp in [PORTFOLIO_FILE, TRANSACTION_FILE]:
                if Path(fp).exists():
                    Path(fp).unlink()
            st.rerun()


# ─────────────────────────────────────────────────────────────
# ── MAIN PANEL ──────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
if portfolio is None:
    st.markdown("# 📈 Portfolio Tracker")
    st.info("Create or restore a portfolio using the sidebar to get started.")
    st.stop()

# ── Trade confirmation message ─────────────────────────────
if st.session_state.trade_msg:
    kind, msg = st.session_state.trade_msg
    if kind == "success":
        st.success(f"✅ {msg}")
    else:
        st.error(f"❌ {msg}")
    st.session_state.trade_msg = None

# ── Stats ─────────────────────────────────────────────────
stats = get_portfolio_stats(portfolio)

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊  Overview", "🔍  Stock Lookup", "📋  Holdings", "🕒  Transactions"]
)


# ═══════════════════════════════════════════════════════════
# TAB 1 — Overview
# ═══════════════════════════════════════════════════════════
with tab1:
    # ── KPI row ──────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Portfolio Value",  f"${stats['total_val']:,.2f}")
    with k2:
        st.metric("Cash",             f"${stats['cash']:,.2f}")
    with k3:
        sign = "+" if stats['unrealised'] >= 0 else ""
        st.metric("Unrealised P&L",
                  f"{sign}${stats['unrealised']:,.2f}",
                  delta=f"{sign}{stats['port_ret']:.2f}%")
    with k4:
        spx_label = (f"{stats['spx_ret']:+.2f}%"
                     if stats['spx_ret'] is not None else "N/A")
        st.metric("S&P 500 (inception)", spx_label)
    with k5:
        alpha_label = (f"{stats['alpha']:+.2f}%"
                       if stats['alpha'] is not None else "N/A")
        alpha_delta = ("above" if stats['alpha'] and stats['alpha'] > 0 else "below")
        st.metric("Alpha", alpha_label,
                  delta=f"{alpha_delta} benchmark" if stats['alpha'] is not None else None)

    st.markdown("---")

    left, right = st.columns([3, 2])

    # ── Portfolio chart ───────────────────────────────────
    with left:
        st.markdown("## Holdings performance")
        if stats["rows"]:
            period_map = {"1 month": "1mo", "3 months": "3mo",
                          "6 months": "6mo", "1 year": "1y"}
            period_label = st.selectbox("Chart period", list(period_map.keys()),
                                         index=2, key="perf_period")
            chosen_period = period_map[period_label]

            fig = go.Figure()
            colors = ["#39d353", "#58a6ff", "#f78166", "#ffa657",
                      "#bc8cff", "#79c0ff", "#56d364", "#ff7b72"]
            for i, row in enumerate(stats["rows"]):
                try:
                    df = fetch_chart_data(row["Ticker"], chosen_period)
                    if df.empty:
                        continue
                    # normalise to % return from start of period
                    start = float(df["Close"].iloc[0])
                    df["pct"] = (df["Close"].astype(float) / start - 1) * 100
                    fig.add_trace(go.Scatter(
                        x=df["Date"], y=df["pct"],
                        name=row["Ticker"],
                        line=dict(color=colors[i % len(colors)], width=2),
                        hovertemplate="%{y:.2f}%<extra>"+row["Ticker"]+"</extra>",
                    ))
                except Exception:
                    pass
            # Add S&P 500 as grey baseline
            try:
                sp = fetch_chart_data(BENCHMARK, chosen_period)
                start = float(sp["Close"].iloc[0])
                sp["pct"] = (sp["Close"].astype(float) / start - 1) * 100
                fig.add_trace(go.Scatter(
                    x=sp["Date"], y=sp["pct"],
                    name="S&P 500",
                    line=dict(color="#484f58", width=1.5, dash="dot"),
                    hovertemplate="%{y:.2f}%<extra>S&P 500</extra>",
                ))
            except Exception:
                pass
            fig.add_hline(y=0, line_dash="solid", line_color="#21262d", line_width=1)
            fig.update_layout(
                paper_bgcolor="#161b22", plot_bgcolor="#161b22",
                font=dict(family="IBM Plex Mono", color="#8b949e", size=11),
                legend=dict(bgcolor="#0d1117", bordercolor="#21262d",
                            borderwidth=1, font=dict(size=11)),
                xaxis=dict(gridcolor="#21262d", showgrid=True, zeroline=False),
                yaxis=dict(gridcolor="#21262d", showgrid=True, zeroline=False,
                           ticksuffix="%"),
                hovermode="x unified",
                margin=dict(l=0, r=0, t=10, b=0),
                height=340,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Add holdings to see the performance chart.")

    # ── Allocation pie ────────────────────────────────────
    with right:
        st.markdown("## Allocation")
        if stats["rows"]:
            labels = [r["Ticker"] for r in stats["rows"]] + ["Cash"]
            values = [r["Mkt Value"] for r in stats["rows"]] + [portfolio.cash]
            colors_pie = ["#39d353", "#58a6ff", "#f78166", "#ffa657",
                          "#bc8cff", "#79c0ff", "#56d364", "#ff7b72",
                          "#484f58"]
            fig2 = go.Figure(go.Pie(
                labels=labels, values=values,
                hole=0.55,
                marker=dict(colors=colors_pie[:len(labels)],
                            line=dict(color="#0d1117", width=2)),
                textinfo="label+percent",
                textfont=dict(family="IBM Plex Mono", size=11, color="#e6edf3"),
                hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
            ))
            fig2.update_layout(
                paper_bgcolor="#161b22", plot_bgcolor="#161b22",
                font=dict(color="#8b949e"),
                showlegend=False,
                margin=dict(l=0, r=0, t=0, b=0),
                height=300,
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No positions yet.")


# ═══════════════════════════════════════════════════════════
# TAB 2 — Stock Lookup / Search
# ═══════════════════════════════════════════════════════════
with tab2:
    st.markdown("## Stock Lookup")
    col_search, col_period = st.columns([3, 1])
    with col_search:
        lookup = st.text_input("Search ticker", placeholder="e.g. TSLA, META, AMZN …",
                                key="lookup_ticker").upper().strip()
    with col_period:
        lu_period_map = {"1m": "1mo", "3m": "3mo", "6m": "6mo",
                          "1y": "1y", "2y": "2y", "5y": "5y"}
        lu_period_label = st.selectbox("Period", list(lu_period_map.keys()),
                                        index=3, key="lu_period")
        lu_period = lu_period_map[lu_period_label]

    if lookup:
        try:
            lu_price  = fetch_price(lookup)
            lu_info   = fetch_ticker_info(lookup)
            lu_df     = fetch_chart_data(lookup, lu_period)

            # ── Header row ──────────────────────────────
            h1, h2, h3 = st.columns([2, 1, 1])
            with h1:
                company = lu_info.get("name", lookup)
                sector  = lu_info.get("sector", "")
                st.markdown(f'<span class="ticker-badge">{lookup}</span> '
                            f'&nbsp;<span style="color:#8b949e;font-size:0.9rem">'
                            f'{company}</span>', unsafe_allow_html=True)
                if sector:
                    st.caption(sector)
            with h2:
                prev = lu_info.get("prev_close") or lu_price
                chg  = lu_price - prev
                chg_pct = chg / prev * 100 if prev else 0
                direction = "price-change-pos" if chg >= 0 else "price-change-neg"
                sign = "+" if chg >= 0 else ""
                st.markdown(
                    f'<p class="price-big">${lu_price:,.2f}</p>'
                    f'<p class="{direction}">{sign}{chg:.2f} ({sign}{chg_pct:.2f}%)</p>',
                    unsafe_allow_html=True
                )

            # ── Key stats ──────────────────────────────
            s1, s2, s3, s4 = st.columns(4)
            mc = lu_info.get("market_cap")
            mc_str = (f"${mc/1e12:.2f}T" if mc and mc > 1e12
                      else f"${mc/1e9:.1f}B" if mc else "—")
            s1.metric("Market Cap", mc_str)
            s2.metric("P/E Ratio", f"{lu_info.get('pe', 0):.1f}" if lu_info.get("pe") else "—")
            s3.metric("52W High", f"${lu_info.get('52w_high', 0):,.2f}" if lu_info.get("52w_high") else "—")
            s4.metric("52W Low",  f"${lu_info.get('52w_low',  0):,.2f}" if lu_info.get("52w_low")  else "—")

            # ── Candlestick chart ───────────────────────
            if not lu_df.empty:
                fig3 = go.Figure()
                fig3.add_trace(go.Candlestick(
                    x=lu_df["Date"],
                    open=lu_df["Open"].squeeze(),
                    high=lu_df["High"].squeeze(),
                    low=lu_df["Low"].squeeze(),
                    close=lu_df["Close"].squeeze(),
                    increasing_line_color="#39d353",
                    decreasing_line_color="#f85149",
                    name=lookup,
                ))
                # Volume bars
                fig3.add_trace(go.Bar(
                    x=lu_df["Date"],
                    y=lu_df["Volume"].squeeze(),
                    marker_color="#21262d",
                    name="Volume",
                    yaxis="y2",
                    opacity=0.5,
                ))
                fig3.update_layout(
                    paper_bgcolor="#161b22", plot_bgcolor="#161b22",
                    font=dict(family="IBM Plex Mono", color="#8b949e", size=11),
                    xaxis=dict(gridcolor="#21262d", rangeslider_visible=False,
                               showgrid=False),
                    yaxis=dict(gridcolor="#21262d", side="right"),
                    yaxis2=dict(overlaying="y", side="left",
                                showgrid=False, showticklabels=False),
                    legend=dict(bgcolor="#0d1117", bordercolor="#21262d",
                                borderwidth=1),
                    hovermode="x unified",
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=380,
                )
                st.plotly_chart(fig3, use_container_width=True)

            # ── Quick trade from lookup ─────────────────
            st.markdown("### Trade this stock")
            qt_shares = st.number_input("Shares", min_value=0.01, step=1.0,
                                         value=1.0, key="lu_shares")
            qt_est = qt_shares * lu_price
            st.caption(f"Estimated value: ${qt_est:,.2f}")
            b1, b2, _ = st.columns([1, 1, 3])
            with b1:
                st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
                if st.button(f"BUY {lookup}", key="lu_buy"):
                    ok, msg = execute_buy(portfolio, lookup, qt_shares, lu_price)
                    st.session_state.trade_msg = ("success" if ok else "error", msg)
                    fetch_prices.clear()
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with b2:
                st.markdown('<div class="sell-btn">', unsafe_allow_html=True)
                if st.button(f"SELL {lookup}", key="lu_sell"):
                    ok, msg = execute_sell(portfolio, lookup, qt_shares, lu_price)
                    st.session_state.trade_msg = ("success" if ok else "error", msg)
                    fetch_prices.clear()
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Could not load data for **{lookup}**: {e}")
    else:
        st.info("Enter a ticker symbol above to see price charts and details.")


# ═══════════════════════════════════════════════════════════
# TAB 3 — Holdings table
# ═══════════════════════════════════════════════════════════
with tab3:
    st.markdown("## Open Positions")
    if stats["rows"]:
        df_hold = pd.DataFrame(stats["rows"])
        df_hold = df_hold.sort_values("Mkt Value", ascending=False)

        # Format for display
        fmt_df = df_hold.copy()
        fmt_df["Avg Cost"]   = fmt_df["Avg Cost"].map("${:,.2f}".format)
        fmt_df["Price"]      = fmt_df["Price"].map("${:,.2f}".format)
        fmt_df["Mkt Value"]  = fmt_df["Mkt Value"].map("${:,.2f}".format)
        fmt_df["P&L ($)"]    = fmt_df["P&L ($)"].map(lambda x: f"+${x:,.2f}" if x >= 0 else f"-${abs(x):,.2f}")
        fmt_df["P&L (%)"]    = fmt_df["P&L (%)"].map(lambda x: f"+{x:.2f}%" if x >= 0 else f"{x:.2f}%")
        fmt_df["Weight (%)"] = fmt_df["Weight (%)"].map("{:.1f}%".format)
        fmt_df["Shares"]     = fmt_df["Shares"].map("{:.4f}".format)

        st.dataframe(
            fmt_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ticker": st.column_config.TextColumn("Ticker", width="small"),
            }
        )

        # ── P&L bar chart ─────────────────────────────
        st.markdown("## P&L by position")
        df_bar = df_hold.copy()
        df_bar["color"] = df_bar["P&L ($)"].apply(
            lambda x: "#39d353" if x >= 0 else "#f85149"
        )
        fig4 = go.Figure(go.Bar(
            x=df_bar["Ticker"],
            y=df_bar["P&L ($)"],
            marker_color=df_bar["color"],
            text=df_bar["P&L ($)"].map(lambda x: f"+${x:,.0f}" if x >= 0 else f"-${abs(x):,.0f}"),
            textposition="outside",
            textfont=dict(family="IBM Plex Mono", size=11, color="#e6edf3"),
        ))
        fig4.add_hline(y=0, line_color="#30363d")
        fig4.update_layout(
            paper_bgcolor="#161b22", plot_bgcolor="#161b22",
            font=dict(family="IBM Plex Mono", color="#8b949e", size=11),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="#21262d", tickprefix="$"),
            margin=dict(l=0, r=0, t=20, b=0),
            height=280,
            showlegend=False,
        )
        st.plotly_chart(fig4, use_container_width=True)

    else:
        st.info("No open positions. Use the sidebar or Stock Lookup tab to make your first trade.")


# ═══════════════════════════════════════════════════════════
# TAB 4 — Transaction history
# ═══════════════════════════════════════════════════════════
with tab4:
    st.markdown("## Transaction History")
    if portfolio.transactions:
        tx_rows = []
        for tx in reversed(portfolio.transactions):
            tx_rows.append({
                "Time":     tx.timestamp,
                "Action":   tx.action,
                "Ticker":   tx.ticker,
                "Shares":   tx.shares,
                "Price":    tx.price,
                "Total":    tx.total,
                "Cash After": tx.cash_after,
                "Notes":    tx.notes,
            })
        df_tx = pd.DataFrame(tx_rows)

        # Colour-code buy/sell in the action column
        def colour_action(val):
            color = "#39d353" if val == "BUY" else "#f85149"
            return f"color: {color}; font-weight: 600; font-family: 'IBM Plex Mono'"

        styled = df_tx.style.applymap(colour_action, subset=["Action"])
        for col in ["Price", "Total", "Cash After"]:
            styled = styled.format("${:,.2f}", subset=[col])
        styled = styled.format("{:.4f}", subset=["Shares"])

        st.dataframe(styled, use_container_width=True, hide_index=True)

        # ── Running cash balance chart ────────────────
        st.markdown("## Cash balance over time")
        df_cash = pd.DataFrame([
            {"Time": tx["Time"], "Cash": tx["Cash After"]} for tx in tx_rows[::-1]
        ])
        df_cash["Time"] = pd.to_datetime(df_cash["Time"])
        fig5 = go.Figure(go.Scatter(
            x=df_cash["Time"], y=df_cash["Cash"],
            fill="tozeroy", fillcolor="rgba(88,166,255,0.08)",
            line=dict(color="#58a6ff", width=2),
            hovertemplate="$%{y:,.2f}<extra>Cash</extra>",
        ))
        fig5.update_layout(
            paper_bgcolor="#161b22", plot_bgcolor="#161b22",
            font=dict(family="IBM Plex Mono", color="#8b949e", size=11),
            xaxis=dict(gridcolor="#21262d"),
            yaxis=dict(gridcolor="#21262d", tickprefix="$"),
            margin=dict(l=0, r=0, t=10, b=0),
            height=240,
        )
        st.plotly_chart(fig5, use_container_width=True)

    else:
        st.info("No transactions yet. Make your first trade using the sidebar or Stock Lookup.")
