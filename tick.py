"""Ejecución "sin estado" para la nube (GitHub Actions).

Cada ejecución (una por hora):
  1. Carga el estado persistente (cash, posiciones, historial, paradas de riesgo)
  2. Reconstruye los indicadores con las últimas 300 velas de cada símbolo
  3. Procesa SOLO las velas nuevas cerradas desde la última ejecución
  4. Guarda el estado y el JSON del dashboard (docs/state.json)

Uso:  python tick.py
"""
import datetime as dt
import json
import os

from bus import MessageBus, CANDLE, FILL, REJECT
from config import SYMBOLS, INTERVAL, INITIAL_CAPITAL, BASE_DIR, DATA_DIR
from data_feed import fetch_klines, INTERVAL_MS
from portfolio import Portfolio
from regime import RegimeFilter
from risk import RiskAgent
from execution import ExecutionAgent
from strategies import ALL_STRATEGIES
from universe import get_universe_data

LIVE_STATE = os.path.join(DATA_DIR, "live_state.json")
DOCS_STATE = os.path.join(BASE_DIR, "docs", "state.json")


def load_state():
    if not os.path.exists(LIVE_STATE):
        return None
    with open(LIVE_STATE) as f:
        return json.load(f)


def restore(portfolio, risk, state):
    portfolio.cash = state["cash"]
    portfolio.positions = {
        tuple(k.split("|")): v for k, v in state["positions"].items()
    }
    portfolio.trades = state["trades"]
    portfolio.equity_curve = [tuple(x) for x in state["equity_curve"]]
    portfolio.last_prices = state.get("last_prices", {})
    r = state.get("risk", {})
    risk.current_day = r.get("current_day")
    risk.current_month = r.get("current_month")
    risk.day_start_equity = r.get("day_start_equity")
    risk.month_peak_equity = r.get("month_peak_equity")
    risk.halted_until_day = r.get("halted_until_day")
    risk.halted_until_month = r.get("halted_until_month")
    return state["last_seen"], state.get("events", [])


def save_state(portfolio, risk, last_seen, events, universe=None, watchlist=None):
    os.makedirs(DATA_DIR, exist_ok=True)
    state = {
        "cash": portfolio.cash,
        "positions": {f"{k[0]}|{k[1]}": v for k, v in portfolio.positions.items()},
        "trades": portfolio.trades,
        "equity_curve": portfolio.equity_curve[-2000:],
        "last_prices": portfolio.last_prices,
        "last_seen": last_seen,
        "events": events[-100:],
        "risk": {
            "current_day": risk.current_day,
            "current_month": risk.current_month,
            "day_start_equity": risk.day_start_equity,
            "month_peak_equity": risk.month_peak_equity,
            "halted_until_day": risk.halted_until_day,
            "halted_until_month": risk.halted_until_month,
        },
    }
    with open(LIVE_STATE, "w") as f:
        json.dump(state, f, indent=1, default=str)

    # estado para el dashboard público
    dashboard = {
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "stats": portfolio.stats(),
        "monthly": portfolio.monthly_returns(),
        "recent_trades": portfolio.trades[-20:],
        "recent_events": events[-30:],
        "halts": {"daily": risk.halted_until_day, "monthly": risk.halted_until_month},
        "equity_curve": portfolio.equity_curve[-500:],
        "regime_risk_on": None,
        "universe_size": len(universe) if universe else None,
        "universe": universe or [],
        "watchlist": watchlist or [],
    }
    os.makedirs(os.path.dirname(DOCS_STATE), exist_ok=True)
    with open(DOCS_STATE, "w") as f:
        json.dump(dashboard, f, indent=1, default=str)


def main():
    bus = MessageBus()
    portfolio = Portfolio(bus, persist=False)
    regime = RegimeFilter.fetch()
    risk = RiskAgent(bus, portfolio, regime=regime)
    ExecutionAgent(bus, portfolio)
    strategies = [S(bus, portfolio) for S in ALL_STRATEGIES]

    events = []
    bus.subscribe(FILL, lambda f: events.append(
        f"{dt.datetime.fromtimestamp(f['ts']/1000, dt.timezone.utc):%m-%d %H:%M} "
        f"FILL {f['side']} {f['symbol']} {f['qty']:.6f} @ {f['fill_price']:.4f} "
        f"[{f['strategy']}] {f.get('reason', '')}"))
    bus.subscribe(REJECT, lambda r: events.append(
        f"RECHAZO {r['signal']['symbol']} [{r['signal'].get('strategy', '?')}]: {r['reason']}"))

    state = load_state()
    step = INTERVAL_MS[INTERVAL]
    now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)

    if state:
        last_seen, prev_events = restore(portfolio, risk, state)
        events[:0] = prev_events
        print(f"Estado cargado: equity {portfolio.equity():,.2f}, "
              f"{len(portfolio.positions)} posiciones abiertas")
    else:
        last_seen = {}
        print(f"Primera ejecución: capital inicial {INITIAL_CAPITAL:,.0f} USDT (ficticio)")

    # Universo dinámico: top por volumen + símbolos con posición abierta
    # (una moneda que salga del top sigue gestionándose hasta cerrar la posición)
    try:
        watchlist = get_universe_data()
        symbols = [d["symbol"] for d in watchlist]
    except Exception as e:
        print(f"Universo dinámico no disponible ({e}); usando lista fija")
        watchlist = []
        symbols = list(SYMBOLS)
    held = {sym for (_, sym) in portfolio.positions}
    symbols = list(dict.fromkeys(symbols + sorted(held)))
    print(f"Universo: {len(symbols)} símbolos")

    new_candles = []
    for sym in symbols:
        candles = fetch_klines(sym, INTERVAL, limit=300)
        closed = [c for c in candles if c["ts"] + step <= now_ms]
        if not closed:
            continue
        seen = last_seen.get(sym, closed[-2]["ts"] if len(closed) > 1 else 0)
        # reconstruir indicadores con el histórico SIN operar (carga directa)
        for strat in strategies:
            for c in closed:
                if c["ts"] <= seen:
                    strat.candles[sym].append(c)
        # las velas posteriores a 'seen' se procesan de verdad (por el bus)
        new_candles.extend(c for c in closed if c["ts"] > seen)
        last_seen[sym] = closed[-1]["ts"]

    new_candles.sort(key=lambda c: c["ts"])
    for c in new_candles:
        portfolio.mark(c["symbol"], c["close"], c["ts"])
        bus.publish(CANDLE, c)

    risk_on = regime.risk_on(now_ms)
    print(f"Velas nuevas procesadas: {len(new_candles)} | "
          f"régimen: {'ALCISTA (opera)' if risk_on else 'BAJISTA (solo cash)'}")
    print(f"Equity: {portfolio.equity():,.2f} USDT | "
          f"posiciones: {len(portfolio.positions)} | trades cerrados: {len(portfolio.trades)}")

    save_state(portfolio, risk, last_seen, events, universe=symbols, watchlist=watchlist)
    # añadir el régimen al json del dashboard
    with open(DOCS_STATE) as f:
        d = json.load(f)
    d["regime_risk_on"] = risk_on
    with open(DOCS_STATE, "w") as f:
        json.dump(d, f, indent=1, default=str)
    print("Estado guardado.")


if __name__ == "__main__":
    main()
