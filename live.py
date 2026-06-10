"""Paper trading EN VIVO: el sistema multi-agente opera con precios reales de
Binance y dinero 100% ficticio. Escribe data/state.json para el dashboard.

Uso:  python live.py
Detener: Ctrl+C. El historial de trades queda en data/paper.db.
"""
import datetime as dt
import json
import time

from bus import MessageBus, CANDLE, FILL, REJECT
from config import SYMBOLS, INTERVAL, STATE_PATH
from data_feed import fetch_klines, INTERVAL_MS
from portfolio import Portfolio
from risk import RiskAgent
from execution import ExecutionAgent
from strategies import ALL_STRATEGIES
from universe import get_universe


def write_state(portfolio, risk, events):
    state = {
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
        "stats": portfolio.stats(),
        "monthly": portfolio.monthly_returns(),
        "recent_trades": portfolio.trades[-20:],
        "recent_events": events[-30:],
        "halts": {
            "daily": risk.halted_until_day,
            "monthly": risk.halted_until_month,
        },
        "equity_curve": portfolio.equity_curve[-500:],
    }
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)


def main():
    bus = MessageBus()
    portfolio = Portfolio(bus, persist=True)
    risk = RiskAgent(bus, portfolio)
    ExecutionAgent(bus, portfolio)
    [S(bus, portfolio) for S in ALL_STRATEGIES]

    events = []
    bus.subscribe(FILL, lambda f: events.append(
        f"{dt.datetime.now():%H:%M} FILL {f['side']} {f['symbol']} "
        f"{f['qty']:.6f} @ {f['fill_price']:.2f} [{f['strategy']}] {f.get('reason','')}"))
    bus.subscribe(REJECT, lambda r: events.append(
        f"{dt.datetime.now():%H:%M} RECHAZO {r['signal']['symbol']} "
        f"[{r['signal'].get('strategy','?')}]: {r['reason']}"))

    step = INTERVAL_MS[INTERVAL]
    last_seen = {}

    try:
        symbols = get_universe()
    except Exception:
        symbols = list(SYMBOLS)
    print(f"Universo: {len(symbols)} símbolos")

    # precargar historial para que los indicadores arranquen calientes
    print("Precargando historial para indicadores...")
    warmup = {}
    for sym in symbols:
        candles = fetch_klines(sym, INTERVAL, limit=300)
        warmup[sym] = candles[:-1]  # la última puede no estar cerrada
        last_seen[sym] = warmup[sym][-1]["ts"]
    merged = sorted((c for cs in warmup.values() for c in cs), key=lambda c: c["ts"])
    for c in merged:
        portfolio.mark(c["symbol"], c["close"], c["ts"])
        bus.publish(CANDLE, c)
    # el warmup no debe contar como trading real: resetear cartera
    portfolio.cash = portfolio.cash  # las posiciones del warmup se mantienen como contexto
    print(f"Listo. Operando en papel sobre {len(symbols)} símbolos (velas {INTERVAL}).")
    print("Dashboard: python dashboard.py  ->  http://localhost:8800\n")

    while True:
        try:
            for sym in symbols:
                candles = fetch_klines(sym, INTERVAL, limit=3)
                for c in candles:
                    closed = c["ts"] + step <= int(time.time() * 1000)
                    if closed and c["ts"] > last_seen[sym]:
                        last_seen[sym] = c["ts"]
                        portfolio.mark(sym, c["close"], c["ts"])
                        bus.publish(CANDLE, c)
                        print(f"{dt.datetime.now():%H:%M} vela {sym} cierre {c['close']:.2f} "
                              f"| equity {portfolio.equity():,.2f}")
            write_state(portfolio, risk, events)
            time.sleep(30)
        except KeyboardInterrupt:
            print("\nDetenido. Estado guardado en data/")
            write_state(portfolio, risk, events)
            break
        except Exception as e:
            print(f"Error (reintento en 60s): {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
