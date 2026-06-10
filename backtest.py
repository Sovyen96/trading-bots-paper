"""Backtest: ejecuta el sistema multi-agente completo sobre datos históricos
reales de Binance y reporta rendimiento mensual, drawdown y win rate.

Uso:  python backtest.py [días]   (por defecto 365)
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from bus import MessageBus, CANDLE
from config import SYMBOLS, INTERVAL, INITIAL_CAPITAL
from data_feed import fetch_history
from portfolio import Portfolio
from regime import RegimeFilter
from risk import RiskAgent
from execution import ExecutionAgent
from strategies import ALL_STRATEGIES
from universe import get_universe


def run(days=365, verbose=True):
    bus = MessageBus()
    portfolio = Portfolio(bus, persist=False)
    if verbose:
        print("Construyendo filtro de régimen (SMA200 diaria de BTC)...")
    regime = RegimeFilter.fetch(extra_days=days)
    risk = RiskAgent(bus, portfolio, regime=regime)
    ExecutionAgent(bus, portfolio)
    strategies = [S(bus, portfolio) for S in ALL_STRATEGIES]

    try:
        symbols = get_universe()
    except Exception as e:
        print(f"Universo dinámico no disponible ({e}); usando lista fija")
        symbols = SYMBOLS
    if verbose:
        print(f"Universo: {len(symbols)} símbolos -> {', '.join(symbols)}")
        print(f"Descargando {days} días de velas {INTERVAL} (en paralelo)...")
    all_candles = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for sym, candles in zip(symbols, pool.map(
                lambda s: fetch_history(s, INTERVAL, days), symbols)):
            if verbose:
                print(f"  {sym}: {len(candles)} velas")
            all_candles.extend(candles)
    all_candles.sort(key=lambda c: c["ts"])  # cronológico, intercalando símbolos

    for c in all_candles:
        portfolio.mark(c["symbol"], c["close"], c["ts"])
        bus.publish(CANDLE, c)

    # cerrar posiciones abiertas al final para valorar todo en cash
    stats = portfolio.stats()
    monthly = portfolio.monthly_returns()
    per_strategy = {}
    for t in portfolio.trades:
        s = per_strategy.setdefault(t["strategy"], {"trades": 0, "pnl": 0.0, "wins": 0})
        s["trades"] += 1
        s["pnl"] += t["pnl"]
        s["wins"] += 1 if t["pnl"] > 0 else 0

    if verbose:
        print("\n" + "=" * 60)
        print(f"RESULTADO BACKTEST ({days} días, capital inicial {INITIAL_CAPITAL:,.0f} USDT)")
        print("=" * 60)
        print(f"Equity final:        {stats['equity']:,.2f} USDT  ({stats['return_pct']:+.2f}%)")
        print(f"Trades cerrados:     {stats['closed_trades']}  |  Win rate: {stats['win_rate']}%")
        print(f"Drawdown máximo:     {stats['max_drawdown_pct']:.2f}%")
        print(f"Señales rechazadas por riesgo: {len(risk.rejections)}")
        print("\nRendimiento mensual:")
        for m, r in monthly.items():
            bar = "#" * min(int(abs(r) * 4), 40)
            print(f"  {m}: {r:+6.2f}%  {bar}")
        print("\nPor estrategia:")
        for name, s in per_strategy.items():
            wr = 100 * s["wins"] / s["trades"] if s["trades"] else 0
            print(f"  {name:16s} {s['trades']:3d} trades | PnL {s['pnl']:+10.2f} USDT | win {wr:.0f}%")

    return {"stats": stats, "monthly": monthly, "per_strategy": per_strategy}


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    result = run(days)
    with open("data/backtest_result.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
