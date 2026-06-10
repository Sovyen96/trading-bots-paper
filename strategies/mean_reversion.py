"""Bot 2 — Reversión a la media: RSI sobrevendido en tendencia alcista.

Compra cuando el RSI(14) cae por debajo de 30 mientras el precio sigue por
encima de la EMA(200) (corrección dentro de tendencia alcista, no cuchillo
cayendo). Sale cuando el RSI recupera 55 o por stop ATR.
"""
from .base import StrategyAgent


class MeanReversionAgent(StrategyAgent):
    name = "mean_reversion"
    lookback = 260

    RSI_BUY, RSI_EXIT, TREND = 30, 55, 200

    def evaluate(self, symbol):
        cs = list(self.candles[symbol])
        if len(cs) < self.TREND + 2:
            return None
        closes = [c["close"] for c in cs]
        price = closes[-1]
        ts = cs[-1]["ts"]

        rsi = self.rsi(closes)
        trend = self.ema(closes, self.TREND)
        atr = self.atr(cs)
        if None in (rsi, trend, atr):
            return None

        in_pos = self.has_position(symbol)

        if not in_pos and rsi < self.RSI_BUY and price > trend:
            return {
                "symbol": symbol, "side": "BUY", "ts": ts, "price": price,
                "stop": price - 2.0 * atr,
                "reason": f"RSI={rsi:.1f} sobrevendido sobre EMA{self.TREND}",
            }
        if in_pos and rsi > self.RSI_EXIT:
            return {
                "symbol": symbol, "side": "SELL", "ts": ts, "price": price,
                "stop": None, "reason": f"RSI={rsi:.1f} recuperado",
            }
        return None
