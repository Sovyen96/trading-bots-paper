"""Bot 3 — Breakout: ruptura del canal de Donchian.

Compra cuando el cierre supera el máximo de las últimas 48 velas (2 días en 1h),
señal clásica de inicio de impulso. Sale cuando el cierre pierde el mínimo de
las últimas 24 velas o por stop ATR.
"""
from .base import StrategyAgent


class BreakoutAgent(StrategyAgent):
    name = "breakout"
    lookback = 120

    ENTRY_N, EXIT_N = 48, 24

    def evaluate(self, symbol):
        cs = list(self.candles[symbol])
        if len(cs) < self.ENTRY_N + 2:
            return None
        price = cs[-1]["close"]
        ts = cs[-1]["ts"]
        atr = self.atr(cs)
        if atr is None:
            return None

        highest = max(c["high"] for c in cs[-self.ENTRY_N - 1:-1])
        lowest = min(c["low"] for c in cs[-self.EXIT_N - 1:-1])
        in_pos = self.has_position(symbol)

        if not in_pos and price > highest:
            return {
                "symbol": symbol, "side": "BUY", "ts": ts, "price": price,
                "stop": price - 2.5 * atr,
                "reason": f"ruptura del máximo de {self.ENTRY_N}h",
            }
        if in_pos and price < lowest:
            return {
                "symbol": symbol, "side": "SELL", "ts": ts, "price": price,
                "stop": None, "reason": f"pérdida del mínimo de {self.EXIT_N}h",
            }
        return None
