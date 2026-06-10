"""Cartera de paper trading: lleva el dinero ficticio, posiciones y métricas.

Persiste cada operación en SQLite para que el historial sobreviva reinicios.
"""
import datetime as dt
import os
import sqlite3

from bus import FILL
from config import DB_PATH, INITIAL_CAPITAL


class Portfolio:
    def __init__(self, bus, persist=True):
        self.cash = INITIAL_CAPITAL
        self.positions = {}   # (strategy, symbol) -> {qty, entry, stop, ts}
        self.trades = []      # operaciones cerradas
        self.equity_curve = []  # [(ts, equity)]
        self.last_prices = {}
        self.persist = persist
        bus.subscribe(FILL, self.on_fill)
        if persist:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            self._db = sqlite3.connect(DB_PATH)
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS trades (
                    ts INTEGER, strategy TEXT, symbol TEXT, side TEXT,
                    qty REAL, price REAL, fee REAL, pnl REAL
                )"""
            )
            self._db.commit()

    # --- estado ---
    def position(self, strategy, symbol):
        return self.positions.get((strategy, symbol))

    def open_position_count(self):
        return len(self.positions)

    def equity(self):
        total = self.cash
        for (strategy, symbol), pos in self.positions.items():
            price = self.last_prices.get(symbol, pos["entry"])
            total += pos["qty"] * price
        return total

    def mark(self, symbol, price, ts):
        self.last_prices[symbol] = price
        self.equity_curve.append((ts, self.equity()))

    # --- ejecuciones ---
    def on_fill(self, fill):
        key = (fill["strategy"], fill["symbol"])
        if fill["side"] == "BUY":
            cost = fill["qty"] * fill["fill_price"] + fill["fee"]
            self.cash -= cost
            self.positions[key] = {
                "qty": fill["qty"],
                "entry": fill["fill_price"],
                "stop": fill.get("stop"),
                "ts": fill["ts"],
            }
            self._log(fill, pnl=None)
        else:  # SELL: cierra la posición completa
            pos = self.positions.pop(key, None)
            if pos is None:
                return
            proceeds = fill["qty"] * fill["fill_price"] - fill["fee"]
            self.cash += proceeds
            entry_cost = pos["qty"] * pos["entry"]
            pnl = proceeds - entry_cost
            self.trades.append({
                "strategy": fill["strategy"], "symbol": fill["symbol"],
                "entry": pos["entry"], "exit": fill["fill_price"],
                "qty": fill["qty"], "pnl": pnl,
                "open_ts": pos["ts"], "close_ts": fill["ts"],
            })
            self._log(fill, pnl=pnl)

    def _log(self, fill, pnl):
        if not self.persist:
            return
        self._db.execute(
            "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?)",
            (fill["ts"], fill["strategy"], fill["symbol"], fill["side"],
             fill["qty"], fill["fill_price"], fill["fee"], pnl),
        )
        self._db.commit()

    # --- métricas ---
    def stats(self):
        eq = self.equity()
        closed = self.trades
        wins = [t for t in closed if t["pnl"] > 0]
        total_pnl = sum(t["pnl"] for t in closed)
        max_dd = self._max_drawdown()
        return {
            "equity": round(eq, 2),
            "cash": round(self.cash, 2),
            "return_pct": round((eq / INITIAL_CAPITAL - 1) * 100, 2),
            "closed_trades": len(closed),
            "win_rate": round(100 * len(wins) / len(closed), 1) if closed else None,
            "total_pnl": round(total_pnl, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "open_positions": {
                f"{s}/{sym}": {"qty": p["qty"], "entry": p["entry"], "stop": p["stop"]}
                for (s, sym), p in self.positions.items()
            },
        }

    def monthly_returns(self):
        """Rendimiento por mes natural a partir de la curva de equity."""
        if not self.equity_curve:
            return {}
        months = {}
        for ts, eq in self.equity_curve:
            key = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).strftime("%Y-%m")
            months.setdefault(key, [eq, eq])
            months[key][1] = eq  # último valor del mes
        out, prev_close = {}, None
        for key in sorted(months):
            start = prev_close if prev_close is not None else months[key][0]
            close = months[key][1]
            out[key] = round((close / start - 1) * 100, 2)
            prev_close = close
        return out

    def _max_drawdown(self):
        peak, max_dd = 0.0, 0.0
        for _, eq in self.equity_curve:
            peak = max(peak, eq)
            if peak > 0:
                max_dd = max(max_dd, (peak - eq) / peak)
        return max_dd
