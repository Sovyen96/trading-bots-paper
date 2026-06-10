"""Bot 1 — Momentum: cruce de EMAs con filtro de tendencia.

Compra cuando la EMA rápida (12) cruza por encima de la lenta (48) y el precio
está sobre la EMA(200) (tendencia alcista de fondo). Sale con el cruce inverso
o por stop basado en ATR.
"""
from .base import StrategyAgent


class MomentumAgent(StrategyAgent):
    name = "momentum"
    lookback = 260

    FAST, SLOW, TREND = 12, 48, 200

    def evaluate(self, symbol):
        cs = list(self.candles[symbol])
        if len(cs) < self.TREND + 2:
            return None
        closes = [c["close"] for c in cs]
        price = closes[-1]
        ts = cs[-1]["ts"]

        fast_now = self.ema(closes, self.FAST)
        slow_now = self.ema(closes, self.SLOW)
        fast_prev = self.ema(closes[:-1], self.FAST)
        slow_prev = self.ema(closes[:-1], self.SLOW)
        trend = self.ema(closes, self.TREND)
        atr = self.atr(cs)
        if None in (fast_now, slow_now, fast_prev, slow_prev, trend, atr):
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
