"""Bot 1 — Momentum: cruce de EMAs con filtro de tendencia.

Compra cuando la EMA rápida (12) cruza por encima de la lenta (48) y el precio
está sobre la EMA(200) (tendencia alcista de fondo). Sale con el cruce inverso
o por stop basado en ATR.
"""
from .base import StrategyAgent


class MomentumAgent(StrategyAgent):
    name = "momentum"

    FAST, SLOW, TREND = 12, 48, 200
    WARMUP = 220  # velas antes de operar (convergencia de la EMA200)

    def evaluate(self, symbol, candle):
        price = candle["close"]
        ts = candle["ts"]

        fast_prev, fast_now = self.ema(symbol, self.FAST, price)
        slow_prev, slow_now = self.ema(symbol, self.SLOW, price)
        _, trend = self.ema(symbol, self.TREND, price)
        atr = self.atr(symbol, candle)

        if self.count[symbol] < self.WARMUP or None in (fast_prev, slow_prev, atr):
            return None

        in_pos = self.has_position(symbol)
        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now

        if not in_pos and crossed_up and price > trend:
            return {
                "symbol": symbol, "side": "BUY", "ts": ts, "price": price,
                "stop": price - 2.5 * atr,
                "reason": f"EMA{self.FAST}>{self.SLOW} cruce alcista sobre EMA{self.TREND}",
            }
        if in_pos and crossed_down:
            return {
                "symbol": symbol, "side": "SELL", "ts": ts, "price": price,
                "stop": None, "reason": "cruce bajista de EMAs",
            }
        return None
